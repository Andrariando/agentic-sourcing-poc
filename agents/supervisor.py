"""
Supervisor Agent - Central coordinator managing case state and DTP stage transitions.
Only Supervisor can update case_summary and dtp_stage.

ARCHITECTURE: Supervisor is deterministic (no LLM calls).
"""
from typing import Dict, Any, Optional, Union
from utils.schemas import (
    CaseSummary, 
    StrategyRecommendation, 
    SupplierShortlist, 
    NegotiationPlan,
    DTPPolicyContext
)
from utils.state import PipelineState
from utils.rules import RuleEngine
from utils.data_loader import get_category
from datetime import datetime
from pydantic import BaseModel


def _policy_list(policy_context: Optional[Union[Dict[str, Any], BaseModel]], key: str) -> list:
    """Safely extract a list from policy_context whether dict or pydantic model."""
    if not policy_context:
        return []
    if isinstance(policy_context, dict):
        return policy_context.get(key, []) or []
    return getattr(policy_context, key, []) or []


class SupervisorAgent:
    """Supervisor Agent - manages case state transitions (deterministic, no LLM)"""
    
    def __init__(self):
        self.name = "Supervisor"
        self.rule_engine = RuleEngine()
    
    def validate_state(self, state: PipelineState) -> tuple[bool, Optional[str]]:
        """
        Validate state completeness and correctness.
        Returns (is_valid, error_message)
        """
        return self.rule_engine.validate_state(state)
    
    def update_case_summary(
        self,
        state: PipelineState,
        key_findings: list[str] = None,
        recommended_action: str = None
    ) -> CaseSummary:
        """Update case summary (only Supervisor can do this)"""
        current_summary = state["case_summary"]
        
        # Update summary
        updated_summary = CaseSummary(
            case_id=current_summary.case_id,
            category_id=current_summary.category_id,
            contract_id=current_summary.contract_id,
            supplier_id=current_summary.supplier_id,
            dtp_stage=current_summary.dtp_stage,
            trigger_source=current_summary.trigger_source,
            status=current_summary.status,
            created_date=current_summary.created_date,
            summary_text=current_summary.summary_text,
            key_findings=key_findings or current_summary.key_findings,
            recommended_action=recommended_action or current_summary.recommended_action
        )
        
        return updated_summary
    
    def advance_dtp_stage(
        self,
        current_stage: str,
        policy_context: Optional[Union[Dict[str, Any], BaseModel]]
    ) -> tuple[str, Optional[str]]:
        """
        Advance to next DTP stage using explicit transition policy.
        Returns (new_stage, error_message)
        """
        # Validate transition using rule engine
        allowed_transitions = {
            "DTP-01": ["DTP-02"],
            "DTP-02": ["DTP-03", "DTP-04"],
            "DTP-03": ["DTP-04"],
            "DTP-04": ["DTP-05"],
            "DTP-05": ["DTP-06"],
            "DTP-06": ["DTP-06"],  # Terminal
        }
        
        # Convert dict to DTPPolicyContext if needed
        if isinstance(policy_context, dict):
            policy_context = DTPPolicyContext(**policy_context) if policy_context else None
        
        # Get allowed transitions from policy or defaults
        stage_allowed = _policy_list(policy_context, "allowed_actions") or allowed_transitions.get(current_stage, [])
        
        if not stage_allowed:
            return current_stage, f"No allowed transitions from {current_stage}"
        
        # Pick the first allowed transition
        next_stage = stage_allowed[0]
        
        # Validate transition
        is_valid, error_msg = self.rule_engine.validate_dtp_transition(
            current_stage, next_stage, policy_context
        )
        
        if not is_valid:
            return current_stage, error_msg
        
        return next_stage, None
    
    def determine_next_agent(self, dtp_stage: str, latest_output: Any, policy_context: Optional[Union[Dict[str, Any], BaseModel]] = None) -> Optional[str]:
        """
        Determine which agent should run next based on DTP stage and agent outputs.
        This is the core allocation logic - Supervisor decides task allocation.
        """
        allowed_actions = _policy_list(policy_context, "allowed_actions")

        # If we just received supplier shortlist, check if negotiation is needed
        if latest_output and isinstance(latest_output, SupplierShortlist):
            if dtp_stage == "DTP-04" and latest_output.top_choice_supplier_id:
                return "NegotiationSupport"
        
        # If we just received strategy recommendation, determine next step
        if latest_output and isinstance(latest_output, StrategyRecommendation):
            if latest_output.recommended_strategy in ["RFx", "Renegotiate"]:
                return "SupplierEvaluation"
            elif latest_output.recommended_strategy == "Renew":
                return None  # Renewal doesn't need supplier evaluation
        
        # Route based on DTP stage
        if dtp_stage == "DTP-01":
            return "Strategy" if (not allowed_actions or "DTP-02" in allowed_actions) else None
        elif dtp_stage in ["DTP-03", "DTP-04"]:
            return "SupplierEvaluation"
        elif dtp_stage == "DTP-04":
            # If we're at negotiation stage and have supplier shortlist
            if latest_output and isinstance(latest_output, SupplierShortlist):
                return "NegotiationSupport"
        else:
            return None  # No agent needed
    
    def should_wait_for_human(
        self,
        dtp_stage: str,
        latest_output: Any,
        policy_context: Optional[Union[Dict[str, Any], BaseModel]]
    ) -> tuple[bool, str]:
        """
        Determine if we should wait for human decision using rule engine.
        Returns (requires_human, reason)
        
        IMPROVED: Checks policy + materiality instead of always returning True.
        """
        # Convert dict to DTPPolicyContext if needed
        if isinstance(policy_context, dict):
            policy_context = DTPPolicyContext(**policy_context) if policy_context else None
        
        # Use rule engine to determine if human approval required
        return self.rule_engine.should_require_human(latest_output, dtp_stage, policy_context)



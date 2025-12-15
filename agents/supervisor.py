"""
Supervisor Agent - Central coordinator managing case state and DTP stage transitions.
Only Supervisor can update case_summary and dtp_stage.
"""
from typing import Dict, Any, Optional, Union
from utils.schemas import (
    CaseSummary, 
    StrategyRecommendation, 
    SupplierShortlist, 
    NegotiationPlan
)
from utils.state import PipelineState
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
    """Supervisor Agent - manages case state transitions"""
    
    def __init__(self):
        self.name = "Supervisor"
    
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
    
    def advance_dtp_stage(self, current_stage: str, policy_context: Optional[Union[Dict[str, Any], BaseModel]]) -> str:
        """Advance to next DTP stage using explicit transition policy"""
        allowed_transitions = {
            "DTP-01": ["DTP-02"],
            "DTP-02": ["DTP-03", "DTP-04"],
            "DTP-03": ["DTP-04"],
            "DTP-04": ["DTP-05"],
            "DTP-05": ["DTP-06"],
            "DTP-06": ["DTP-06"],  # Terminal
        }
        stage_allowed = _policy_list(policy_context, "allowed_actions") or allowed_transitions.get(current_stage, [])
        # Pick the first allowed transition; if none, stay
        return stage_allowed[0] if stage_allowed else current_stage
    
    def determine_next_agent(self, dtp_stage: str, latest_output: Any, policy_context: Optional[Union[Dict[str, Any], BaseModel]] = None) -> str:
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
    
    def should_wait_for_human(self, dtp_stage: str, latest_output: Any, policy_context: Optional[Union[Dict[str, Any], BaseModel]]) -> bool:
        """
        Determine if we should wait for human decision with policy + materiality.
        Current rule: any agent output that changes direction requires human review.
        """
        if latest_output:
            return True  # Require explicit human approval for every agent recommendation
        return False



"""
Supervisor Agent - Central coordinator managing case state and DTP stage transitions.
Only Supervisor can update case_summary and dtp_stage.

ARCHITECTURE (NON‑NEGOTIABLE CONSTRAINTS):
- Supervisor is deterministic (no LLM calls).
- Supervisor is the **only orchestrator** of the LangGraph workflow.
- RuleEngine + PolicyLoader + Supervisor decide what is **allowed**.
- WAIT_FOR_HUMAN gates all human‑in‑the‑loop decisions.
- LLM‑powered agents **never** change case state directly; they only
  propose structured outputs which the Supervisor reviews.

ENHANCED CAPABILITIES (POC EXTENSIONS, STILL DETERMINISTIC):
- Proactive case initiation from CaseTrigger objects (system‑initiated DTP‑01).
- Confidence‑aware routing to either proceed, clarify, or wait for human.
- Capability registry for explicit out‑of‑scope detection.
- Integration with CaseClarifierAgent for collaborative questions.

GOVERNANCE STATEMENT:
    “The chatbot experience in the UI never decides what happens next; it only
    explains what the Supervisor + policies have already determined is allowed.”
"""
from typing import Dict, Any, Optional, Union, Literal, Tuple
from utils.schemas import (
    CaseSummary, 
    StrategyRecommendation, 
    SupplierShortlist, 
    NegotiationPlan,
    DTPPolicyContext,
    CaseTrigger,
    ClarificationRequest,
    OutOfScopeNotice,
    RFxDraft,
    ContractExtraction,
    RFxDraft,
    ContractExtraction,
    ImplementationPlan,
    AgentDialogue
)
from utils.state import PipelineState
from utils.rules import RuleEngine
from utils.data_loader import get_category
from utils.policy_loader import PolicyLoader
from datetime import datetime
from pydantic import BaseModel


def _policy_list(policy_context: Optional[Union[Dict[str, Any], BaseModel]], key: str) -> list:
    """Safely extract a list from policy_context whether dict or pydantic model."""
    if not policy_context:
        return []
    if isinstance(policy_context, dict):
        return policy_context.get(key, []) or []
    return getattr(policy_context, key, []) or []


# Agent Capability Registry - defines what each agent can do (Table 3 alignment)
AGENT_CAPABILITIES = {
    "Strategy": ["Renew", "Renegotiate", "RFx", "Terminate", "Monitor"],
    "SupplierEvaluation": ["SupplierShortlist"],  # Supplier Scoring Agent (Table 3)
    "RFxDraft": ["RFxDraft"],  # RFx Draft Agent (Table 3)
    "NegotiationSupport": ["NegotiationPlan"],
    "ContractSupport": ["ContractExtraction"],  # Contract Support Agent (Table 3)
    "Implementation": ["ImplementationPlan"],  # Implementation Agent (Table 3)
    "SignalInterpretation": ["SignalAssessment"],
    "CaseClarifier": ["ClarificationRequest"]
}


class SupervisorAgent:
    """Supervisor Agent - manages case state transitions (deterministic, no LLM)"""
    
    def __init__(self):
        self.name = "Supervisor"
        self.rule_engine = RuleEngine()
        self.policy_loader = PolicyLoader()
        self.confidence_threshold_low = 0.6
        self.confidence_threshold_medium = 0.8
        self.confidence_threshold_low = 0.6
        self.confidence_threshold_medium = 0.8
        
    def _check_output_type(self, output: Any, expected_type_name: str, key_field: str = None) -> bool:
        """Helper to check if output matches type (object or dict)."""
        if not output:
             return False
        # Check if object
        if type(output).__name__ == expected_type_name:
            return True
        # Check if dict
        if isinstance(output, dict):
            # Check for specific fields that identify the type
            if key_field and key_field in output:
                return True
            # Fallback (weak check)
            pass
        return False
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
    
    def determine_next_agent(
        self, 
        dtp_stage: str, 
        latest_output: Any, 
        policy_context: Optional[Union[Dict[str, Any], BaseModel]] = None,
        user_intent: str = ""
    ) -> Optional[str]:
        """
        Determine which agent should run next based on DTP stage, agent outputs, AND user intent.
        This is the core allocation logic - Supervisor decides task allocation.
        """
        allowed_actions = _policy_list(policy_context, "allowed_actions")

        # Intent-driven routing (overrides sequential logic if explicit)
        intent_lower = user_intent.lower()
        
        # 1. Status / Unclear -> CaseClarifier (handling StatusReportAgent fallback)
        if any(w in intent_lower for w in ["status", "progress", "update", "happening", "where are we"]):
            return "CaseClarifier"
            
        # 2. Risk / Compliance -> SignalInterpretation (or ContractSupport)
        if any(w in intent_lower for w in ["risk", "compliance", "flag", "regulatory", "audit"]):
            # If we have contract data, maybe ContractSupport? Defaulting to SignalInterpretation for general risk
            return "SignalInterpretation"
            
        # 3. Strategy / Recommendation -> Strategy
        if any(w in intent_lower for w in ["strategy", "recommend", "plan", "option", "path"]):
            return "Strategy"
            
        # 4. Compare / Suppliers -> SupplierEvaluation
        if any(w in intent_lower for w in ["compare", "supplier", "scorecard", "rank", "shortlist"]):
            return "SupplierEvaluation"

        # Table 3 routing logic: Route based on DTP stage and agent outputs
        
        # If we just received strategy recommendation (DTP-01 output), determine next step
        is_strategy = self._check_output_type(latest_output, "StrategyRecommendation", "recommended_strategy")
        if latest_output and is_strategy:
            strategy = getattr(latest_output, "recommended_strategy", None) or latest_output.get("recommended_strategy")
            if strategy in ["RFx", "Renegotiate"]:
                # DTP-02: Supplier Scoring Agent (Table 3: DTP-02/03)
                return "SupplierEvaluation"
            elif strategy == "Renew":
                return None  # Renewal path may not need supplier evaluation
        
        # If we just received supplier shortlist (DTP-02/03 output), route to RFx or Negotiation
        is_shortlist = self._check_output_type(latest_output, "SupplierShortlist", "shortlisted_suppliers")
        if latest_output and is_shortlist:
            if dtp_stage == "DTP-03":
                # DTP-03: RFx Draft Agent (Table 3: DTP-03)
                return "RFxDraft"
            elif dtp_stage == "DTP-04":
                # Only check top choice if we have it
                top_choice = getattr(latest_output, "top_choice_supplier_id", None) or latest_output.get("top_choice_supplier_id")
                if top_choice:
                    # DTP-04: Negotiation Support Agent (Table 3: DTP-04)
                    return "NegotiationSupport"
        
        # If we just received RFx draft (DTP-03 output), route to Negotiation
        is_rfx = self._check_output_type(latest_output, "RFxDraft", "rfx_sections")
        if latest_output and is_rfx:
            if dtp_stage == "DTP-03":
                # After RFx draft, proceed to supplier evaluation or negotiation
                return "SupplierEvaluation"  # Or could route to Negotiation if supplier already selected
        
        # If we just received negotiation plan (DTP-04 output), route to Contract Support
        if latest_output and isinstance(latest_output, NegotiationPlan):
            # DTP-04/05: Contract Support Agent (Table 3: DTP-04/05)
            return "ContractSupport"
        
        # If we just received contract extraction (DTP-04/05 output), route to Implementation
        if latest_output and isinstance(latest_output, ContractExtraction):
            # DTP-05/06: Implementation Agent (Table 3: DTP-05/06)
            return "Implementation"
        
        # Route based on DTP stage (initial task allocation)
        if dtp_stage == "DTP-01":
            return "Strategy" if (not allowed_actions or "DTP-02" in allowed_actions) else None
        elif dtp_stage == "DTP-02":
            # DTP-02: Supplier Scoring Agent (Table 3: DTP-02/03)
            return "SupplierEvaluation"
        elif dtp_stage == "DTP-03":
            # DTP-03: RFx Draft Agent or Supplier Evaluation (Table 3)
            # Check if we already have supplier shortlist - if so, route to RFx Draft
            if latest_output and isinstance(latest_output, SupplierShortlist):
                return "RFxDraft"
            else:
                return "SupplierEvaluation"  # Need supplier evaluation first
        elif dtp_stage == "DTP-04":
            # DTP-04: Negotiation Support Agent or Contract Support (Table 3)
            if latest_output and isinstance(latest_output, SupplierShortlist):
                return "NegotiationSupport"
            elif latest_output and isinstance(latest_output, NegotiationPlan):
                return "ContractSupport"
            else:
                return "NegotiationSupport"  # Default to negotiation
        elif dtp_stage == "DTP-05":
            # DTP-05: Contract Support Agent or Implementation Agent (Table 3)
            if latest_output and isinstance(latest_output, ContractExtraction):
                return "Implementation"
            else:
                return "ContractSupport"  # Need contract extraction first
        elif dtp_stage == "DTP-06":
            # DTP-06: Implementation Agent (Table 3: DTP-05/06)
            if not latest_output or not isinstance(latest_output, ImplementationPlan):
                return "Implementation"
            else:
                return None  # Implementation complete
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
    
    def create_case_from_trigger(
        self,
        trigger: CaseTrigger,
        existing_case_ids: list[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new case from a CaseTrigger (proactive case creation).
        Returns case creation payload or None if case already exists.
        """
        from utils.signal_aggregator import SignalAggregator
        aggregator = SignalAggregator()
        return aggregator.create_case_from_trigger(trigger, existing_case_ids)
    
    def check_agent_capability(
        self,
        agent_name: str,
        requested_action: str
    ) -> tuple[bool, Optional[OutOfScopeNotice]]:
        """
        Check if an agent can handle a requested action.
        Returns (is_capable, out_of_scope_notice)
        """
        agent_capabilities = AGENT_CAPABILITIES.get(agent_name, [])
        
        if requested_action in agent_capabilities:
            return True, None
        
        # Action is out of scope
        alternative_actions = []
        for agent, capabilities in AGENT_CAPABILITIES.items():
            if requested_action in capabilities:
                alternative_actions.append(f"{agent} can handle {requested_action}")
        
        notice = OutOfScopeNotice(
            requested_action=requested_action,
            reason=f"{agent_name} does not support action '{requested_action}'. Supported actions: {', '.join(agent_capabilities)}",
            suggested_next_steps=[
                f"Use {alternative_actions[0]}" if alternative_actions else "Contact system administrator",
                "Review agent capabilities registry",
                "Modify request to match agent capabilities"
            ],
            alternative_actions=alternative_actions if alternative_actions else None,
            external_action_required=len(alternative_actions) == 0
        )
        
        return False, notice
    
    def determine_next_agent_with_confidence(
        self,
        dtp_stage: str,
        latest_output: Any,
        policy_context: Optional[Union[Dict[str, Any], BaseModel]] = None,
        trigger_type: Optional[str] = None,
        user_intent: str = ""
    ) -> Tuple[Optional[str], Optional[str], Optional[ClarificationRequest]]:
        """
        Enhanced routing with confidence-aware logic.
        Returns (next_agent, routing_reason, clarification_request)
        
        Routing logic:
        - High confidence (>= 0.8) → continue workflow automatically
        - Medium confidence (0.6-0.8) → may request clarification or secondary agent
        - Low confidence (< 0.6) → pause and ask human for guidance
        """
        # First, check if action is out of scope
        if latest_output:
            output_type = type(latest_output).__name__
            if output_type == "StrategyRecommendation":
                strategy = latest_output.recommended_strategy
                is_capable, out_of_scope_notice = self.check_agent_capability("Strategy", strategy)
                if not is_capable:
                    # Return None to pause workflow, with out-of-scope notice
                    return None, "out_of_scope", None
        
                if not is_capable:
                    # Return None to pause workflow, with out-of-scope notice
                    return None, "out_of_scope", None
        
        # Check if output is AgentDialogue (Talking Back)
        if latest_output and (isinstance(latest_output, AgentDialogue) or (isinstance(latest_output, dict) and "status" in latest_output and "reasoning" in latest_output)):
            status = latest_output.status if hasattr(latest_output, "status") else latest_output.get("status")
            if status == "NeedClarification":
                return "CaseClarifier", "agent_requested_clarification", None
            elif status == "ConcernRaised":
                return "wait_for_human", "agent_raised_concern", None
            elif status == "SuggestAlternative":
                # For now, route to human to decide on alternative
                return "wait_for_human", "agent_suggested_alternative", None
            return None, "agent_dialogue_handled", None
        
        # Check confidence if output has it
        confidence = None
        if latest_output and hasattr(latest_output, 'confidence'):
            confidence = latest_output.confidence
        
        # Low confidence - need clarification
        if confidence is not None and confidence < self.confidence_threshold_low:
            return None, "low_confidence_clarification", None
        
        # Medium confidence - may need clarification
        if confidence is not None and self.confidence_threshold_low <= confidence < self.confidence_threshold_medium:
            # Check if policy allows auto-proceed
            if policy_context:
                policy = policy_context if isinstance(policy_context, DTPPolicyContext) else DTPPolicyContext(**policy_context)
                # If policy requires human for this stage, request clarification
                if dtp_stage in _policy_list(policy_context, "human_required_for"):
                    return None, "medium_confidence_policy_requires_human", None
        
        # High confidence or no confidence score - proceed with normal routing
        next_agent = self.determine_next_agent(dtp_stage, latest_output, policy_context, user_intent=user_intent)
        return next_agent, "normal_routing", None
    
    def should_request_clarification(
        self,
        case_summary: CaseSummary,
        latest_output: Any,
        confidence: Optional[float],
        missing_fields: list[str],
        policy_ambiguity: Optional[str] = None,
        multiple_paths: Optional[list[str]] = None
    ) -> bool:
        """
        Determine if clarification should be requested.
        Returns True if clarification is needed.
        """
        # Low confidence always requires clarification
        if confidence is not None and confidence < self.confidence_threshold_low:
            return True
        
        # Missing required fields
        if missing_fields:
            return True
        
        # Policy ambiguity
        if policy_ambiguity:
            return True
        
        # Multiple valid paths
        if multiple_paths and len(multiple_paths) > 1:
            return True
        
        return False



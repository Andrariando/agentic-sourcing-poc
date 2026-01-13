"""
Rule Engine - Deterministic policy rule enforcement.
Rules are applied BEFORE LLM calls to ensure deterministic behavior.

Priority: Rules > Analytics > Retrieval > LLM Narration
"""
from typing import Optional, Dict, Any, List
from utils.schemas import (
    StrategyRecommendation, DecisionImpact, DTPPolicyContext,
    CaseSummary
)
from utils.data_loader import get_contract, get_performance
from datetime import datetime, timedelta


class RuleEngine:
    """
    Deterministic rule engine for policy enforcement.
    All rules are encoded as code, not prompts.
    """
    
    def apply_strategy_rules(
        self,
        contract: Optional[Dict[str, Any]],
        performance: Optional[Dict[str, Any]],
        market: Optional[Dict[str, Any]],
        case_summary: CaseSummary
    ) -> Optional[str]:
        """
        Apply deterministic strategy rules.
        Returns strategy if rule matches, None if no rule applies.
        
        Rules are applied in priority order:
        1. Contract expiry + performance rules
        2. Performance decline rules
        3. Market opportunity rules
        """
        if not contract:
            return None  # No contract data, cannot apply rules
        
        expiry_days = contract.get("expiry_days", 999)
        contract_value = contract.get("annual_value_usd", 0)
        
        # Rule 1: Contract expires <= 60 days + declining/stable-low performance → RFx
        if expiry_days <= 60:
            if performance:
                perf_trend = performance.get("trend", "")
                perf_score = performance.get("overall_score", 0)
                
                if perf_trend == "declining" or (perf_trend == "stable" and perf_score < 6.0):
                    return "RFx"
                elif perf_trend == "stable" and perf_score >= 6.0:
                    return "Renegotiate"
                else:
                    return "RFx"  # Default for near-expiry
            else:
                return "RFx"  # No performance data, assume RFx for near-expiry
        
        # Rule 2: Contract expires > 180 days + stable-good performance → Renew
        if expiry_days > 180:
            if performance:
                perf_trend = performance.get("trend", "")
                perf_score = performance.get("overall_score", 0)
                
                if perf_trend == "stable" and perf_score >= 7.0:
                    return "Renew"
                elif perf_trend == "improving" and perf_score >= 6.5:
                    return "Renew"
        
        # Rule 3: High-value contract (>$1M) + performance issues → RFx
        if contract_value > 1_000_000:
            if performance:
                perf_score = performance.get("overall_score", 0)
                incidents = performance.get("incidents", [])
                
                if perf_score < 6.0 or len(incidents) > 2:
                    return "RFx"
        
        # Rule 4: Contract expires 61-180 days + performance decline → Renegotiate
        if 61 <= expiry_days <= 180:
            if performance:
                perf_trend = performance.get("trend", "")
                if perf_trend == "declining":
                    return "Renegotiate"
        
        # No rule matched
        return None
    
    def validate_dtp_transition(
        self,
        current_stage: str,
        next_stage: str,
        policy_context: Optional[DTPPolicyContext]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate DTP stage transition against policy.
        Returns (is_valid, error_message)
        """
        # Define allowed transitions
        allowed_transitions = {
            "DTP-01": ["DTP-02"],
            "DTP-02": ["DTP-03", "DTP-04"],
            "DTP-03": ["DTP-04"],
            "DTP-04": ["DTP-05"],
            "DTP-05": ["DTP-06"],
            "DTP-06": ["DTP-06"],  # Terminal
        }
        
        # Check policy context first
        if policy_context:
            allowed_actions = policy_context.allowed_actions
            if allowed_actions and next_stage not in allowed_actions:
                return False, f"Transition to {next_stage} not allowed by policy. Allowed: {allowed_actions}"
        
        # Check default transitions
        if current_stage not in allowed_transitions:
            return False, f"Invalid current stage: {current_stage}"
        
        if next_stage not in allowed_transitions[current_stage]:
            return False, f"Invalid transition: {current_stage} → {next_stage}. Allowed: {allowed_transitions[current_stage]}"
        
        return True, None
    
    def should_require_human(
        self,
        output: Any,
        dtp_stage: str,
        policy_context: Optional[DTPPolicyContext]
    ) -> tuple[bool, str]:
        """
        Determine if human approval required based on materiality and policy.
        Returns (requires_human, reason)
        """
        # Check policy context first
        if policy_context:
            human_required_for = policy_context.human_required_for
            if dtp_stage in human_required_for:
                return True, f"DTP stage {dtp_stage} requires human approval per policy"
        
        # Check materiality (decision_impact)
        if output and hasattr(output, 'decision_impact'):
            if output.decision_impact == DecisionImpact.HIGH:
                return True, "High-impact decision requires human approval"
            elif output.decision_impact == DecisionImpact.MEDIUM:
                # Medium impact: check DTP stage
                if dtp_stage in ["DTP-04", "DTP-06"]:
                    return True, f"Medium-impact decision at {dtp_stage} requires human approval"
        
        # Check DTP stage requirements (explicit decision points)
        if dtp_stage == "DTP-04":  # Negotiation stage always requires human
            return True, "Negotiation stage requires human approval"
        
        if dtp_stage == "DTP-06":  # Execution stage always requires human
            return True, "Execution stage requires human approval"
        
        # Check for strategy recommendations (always require human at DTP-01)
        if dtp_stage == "DTP-01" and output and isinstance(output, StrategyRecommendation):
            return True, "Strategy recommendations require human approval"
        
        return False, "No human approval required"
    
    def validate_state(self, state: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate state completeness and correctness.
        Returns (is_valid, error_message)
        """
        # Check required fields
        required_fields = ["case_id", "dtp_stage", "case_summary", "trigger_source"]
        for field in required_fields:
            if field not in state or state[field] is None:
                return False, f"Missing required field: {field}"
        
        # Check DTP stage validity
        valid_stages = ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"]
        if state["dtp_stage"] not in valid_stages:
            return False, f"Invalid DTP stage: {state['dtp_stage']}. Must be one of {valid_stages}"
        
        # Check case_summary structure
        case_summary = state["case_summary"]
        if not isinstance(case_summary, CaseSummary):
            return False, "case_summary must be a CaseSummary instance"
        
        # Check trigger_source validity
        valid_sources = ["User", "Signal"]
        if state["trigger_source"] not in valid_sources:
            return False, f"Invalid trigger_source: {state['trigger_source']}. Must be one of {valid_sources}"
        
        return True, None
    
    def apply_supplier_scoring_rules(
        self,
        supplier: Dict[str, Any],
        performance: Optional[Dict[str, Any]],
        requirements: Optional[Dict[str, Any]]
    ) -> Optional[float]:
        """
        Apply deterministic supplier scoring rules.
        Returns score if rule-based, None if requires ML/analytics.
        """
        # Rule: Minimum performance threshold
        if performance:
            perf_score = performance.get("overall_score", 0)
            if perf_score < 5.0:
                return 0.0  # Below minimum threshold
        
        # Rule: Must-have requirements check
        if requirements:
            must_haves = requirements.get("must_have", [])
            supplier_capabilities = supplier.get("capabilities", [])
            
            missing_must_haves = [req for req in must_haves if req not in supplier_capabilities]
            if missing_must_haves:
                return 0.0  # Missing must-have requirements
        
        # No deterministic rule applies - requires ML/analytics
        return None
    
    def check_mandatory_checks(
        self,
        dtp_stage: str,
        policy_context: Optional[DTPPolicyContext],
        state: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        Check mandatory checks for DTP stage.
        Returns (all_checks_passed, failed_checks)
        """
        failed_checks = []
        
        if not policy_context:
            return True, []
        
        mandatory_checks = policy_context.mandatory_checks
        if not mandatory_checks:
            return True, []
        
        # DTP-01: Ensure category strategy exists
        if "Ensure category strategy exists" in mandatory_checks:
            category_id = state.get("case_summary", {}).category_id if isinstance(state.get("case_summary"), dict) else state.get("case_summary").category_id
            if not category_id:
                failed_checks.append("Category strategy missing")
        
        # DTP-02: FMV check, Market localization
        if "FMV check" in mandatory_checks:
            # Check if market data exists
            if not state.get("market_data"):
                failed_checks.append("FMV check not completed")
        
        # DTP-03: Supplier MCDM criteria defined
        if "Supplier MCDM criteria defined" in mandatory_checks:
            if not state.get("evaluation_criteria"):
                failed_checks.append("Supplier MCDM criteria not defined")
        
        # DTP-04: DDR/HCC flags resolved, Compliance approvals
        if "DDR/HCC flags resolved" in mandatory_checks:
            if state.get("ddr_flags") or state.get("hcc_flags"):
                failed_checks.append("DDR/HCC flags not resolved")
        
        # DTP-05: Contracting guardrails
        if "Contracting guardrails" in mandatory_checks:
            if not state.get("contract_guardrails_checked"):
                failed_checks.append("Contracting guardrails not checked")
        
        # DTP-06: Savings validation & reporting
        if "Savings validation & reporting" in mandatory_checks:
            if not state.get("savings_validated"):
                failed_checks.append("Savings not validated")
        
        return len(failed_checks) == 0, failed_checks












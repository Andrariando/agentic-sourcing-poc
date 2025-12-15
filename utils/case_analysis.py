"""
Case analysis utilities for decision signals and recommendations.
"""
from typing import Dict, Any, Optional, Tuple
from utils.data_loader import get_contract, get_performance, get_market_data
from utils.schemas import Case, StrategyRecommendation, SupplierShortlist, NegotiationPlan, SignalAssessment
from utils.dtp_stages import get_dtp_stage_display


def get_decision_signal(case: Case) -> Tuple[str, str, list[str]]:
    """
    Determine decision signal for a case.
    Returns (signal_type, signal_label, rationale_bullets)
    """
    contract = None
    if case.contract_id:
        contract = get_contract(case.contract_id)
    
    performance = None
    if case.supplier_id:
        performance = get_performance(case.supplier_id)
    
    # Check for contract expiry risk
    if contract and contract.get("expiry_days", 999) <= 30:
        bullets = [
            f"Contract expiry in {contract['expiry_days']} days",
        ]
        if performance and performance.get("trend") == "Declining":
            bullets.append("Supplier performance below category benchmark")
        if not case.latest_agent_output or (hasattr(case.latest_agent_output, "recommended_strategy") and 
                                           case.latest_agent_output.recommended_strategy not in ["RFx", "Renegotiate"]):
            bullets.append("No active RFx or renegotiation initiated")
        return ("renewal_at_risk", "Renewal at Risk", bullets)
    
    # Check for performance issues
    if performance and performance.get("trend") == "Declining":
        bullets = [
            f"Supplier performance trend: {performance.get('trend', 'Unknown')}",
            f"Overall score: {performance.get('overall_score', 'N/A')}/10"
        ]
        if contract and contract.get("expiry_days", 999) <= 90:
            bullets.append(f"Contract expiring in {contract['expiry_days']} days")
        return ("performance_alert", "Performance Alert", bullets)
    
    # Check for strategy recommendation pending
    if case.latest_agent_output and isinstance(case.latest_agent_output, StrategyRecommendation):
        if case.status == "Waiting for Human Decision":
            return ("action_required", "User Review Required", [
                f"Strategy recommendation: {case.latest_agent_output.recommended_strategy}",
                "Awaiting user approval to proceed"
            ])
    
    # Default signal
    return ("monitoring", "Under Review", [
        f"Case in {get_dtp_stage_display(case.dtp_stage)} stage",
        "No immediate action required"
    ])


def get_recommended_action(case: Case) -> Tuple[Optional[str], Optional[str], list[str]]:
    """
    Get recommended next action for a case.
    Returns (action_label, action_type, rationale_bullets)
    """
    if case.latest_agent_output:
        if isinstance(case.latest_agent_output, StrategyRecommendation):
            strategy = case.latest_agent_output.recommended_strategy
            if strategy == "RFx":
                return ("Initiate Market Scan", "market_scan", case.latest_agent_output.rationale[:3])
            elif strategy == "Renegotiate":
                return ("Launch Negotiation Workflow", "negotiation", case.latest_agent_output.rationale[:3])
            elif strategy == "Renew":
                return ("Proceed with Renewal", "renewal", case.latest_agent_output.rationale[:3])
        
        elif isinstance(case.latest_agent_output, SupplierShortlist):
            return ("Review Supplier Shortlist", "review_shortlist", [
                f"{len(case.latest_agent_output.shortlisted_suppliers)} suppliers evaluated",
                case.latest_agent_output.recommendation
            ])
        
        elif isinstance(case.latest_agent_output, NegotiationPlan):
            return ("Execute Negotiation Plan", "execute_negotiation", case.latest_agent_output.negotiation_objectives[:3])
    
    # Default recommendation based on DTP stage
    if case.dtp_stage == "DTP-01":
        return ("Request Strategy Analysis", "strategy_analysis", [
            "Case requires sourcing strategy definition",
            "AI can analyze contract, performance, and market data"
        ])
    elif case.dtp_stage == "DTP-03":
        return ("Initiate Supplier Evaluation", "supplier_evaluation", [
            "Ready for supplier identification and evaluation"
        ])
    
    return (None, None, [])


def get_case_urgency(case: Case) -> Tuple[str, str]:
    """
    Get urgency level and display for a case.
    Returns (urgency_level, display_text)
    """
    contract = None
    if case.contract_id:
        contract = get_contract(case.contract_id)
    
    if contract:
        expiry_days = contract.get("expiry_days", 999)
        if expiry_days <= 30:
            return ("high", f"🔴 {expiry_days} days to expiry")
        elif expiry_days <= 90:
            return ("medium", f"🟡 {expiry_days} days to expiry")
    
    if case.status == "Waiting for Human Decision":
        return ("high", "🔴 Action Required")
    
    performance = None
    if case.supplier_id:
        performance = get_performance(case.supplier_id)
        if performance and performance.get("trend") == "Declining":
            return ("medium", "🟡 Performance Alert")
    
    return ("low", "🟢 On Track")


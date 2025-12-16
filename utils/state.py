"""
LangGraph State definition for the agentic sourcing pipeline.
"""
from typing import TypedDict, Optional, List, Union, Dict, Any
from utils.schemas import (
    CaseSummary, HumanDecision, BudgetState, CacheMeta,
    AgentActionLog, SignalAssessment, StrategyRecommendation,
    SupplierShortlist, NegotiationPlan, DTPPolicyContext,
    SignalRegisterEntry, ClarificationRequest, OutOfScopeNotice
)


class PipelineState(TypedDict):
    """Central state object for LangGraph workflow"""
    case_id: str
    dtp_stage: str  # DTP-01 ... DTP-06
    trigger_source: str  # "User" | "Signal"
    user_intent: str  # Raw Copilot text
    case_summary: CaseSummary  # Maintained by Supervisor
    latest_agent_output: Optional[Union[
        StrategyRecommendation,
        SupplierShortlist,
        NegotiationPlan,
        SignalAssessment,
        ClarificationRequest,
        OutOfScopeNotice
    ]]
    latest_agent_name: Optional[str]
    activity_log: List[AgentActionLog]  # Current run
    human_decision: Optional[HumanDecision]
    budget_state: BudgetState
    cache_meta: CacheMeta
    error_state: Optional[Dict[str, Any]]
    waiting_for_human: bool  # Flag to indicate HIL pause
    use_tier_2: bool  # Flag for Tier 2 model usage
    visited_agents: List[str]  # Track which agents we've visited to prevent loops
    iteration_count: int  # Track number of Supervisor iterations
    dtp_policy_context: DTPPolicyContext  # Policy constraints per DTP stage
    signal_register: List[SignalRegisterEntry]  # Persistent signals driving decisions
    trigger_type: Optional[str]  # "Renewal" | "Savings" | "Risk" | "Monitoring" (from CaseTrigger)
    clarification_reason: Optional[str]  # Reason for clarification request
    missing_fields: Optional[List[str]]  # Fields missing that require clarification
    policy_ambiguity: Optional[str]  # Policy ambiguity requiring clarification
    multiple_paths: Optional[List[str]]  # Multiple valid paths requiring human choice


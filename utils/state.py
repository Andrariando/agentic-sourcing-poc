"""
LangGraph State definition for the agentic sourcing pipeline.
"""
from typing import TypedDict, Optional, List, Union, Dict, Any
from typing import TYPE_CHECKING
from utils.schemas import (
    CaseSummary, HumanDecision, BudgetState, CacheMeta,
    AgentActionLog, SignalAssessment, StrategyRecommendation,
    SupplierShortlist, NegotiationPlan, DTPPolicyContext,
    SignalRegisterEntry, ClarificationRequest, OutOfScopeNotice,
    RFxDraft, ContractExtraction, ImplementationPlan
)

if TYPE_CHECKING:
    from utils.case_memory import CaseMemory
    from utils.execution_constraints import ExecutionConstraints


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
        OutOfScopeNotice,
        RFxDraft,
        ContractExtraction,
        ImplementationPlan
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
    
    # PHASE 2 additions
    case_memory: Optional[Any]  # CaseMemory object for structured memory
    output_history: Optional[List[Dict[str, Any]]]  # History of agent outputs for contradiction detection
    detected_contradictions: Optional[List[str]]  # Contradictions detected in this run
    validation_violations: Optional[List[str]]  # Agent output validation violations
    validation_warnings: Optional[List[str]]  # Agent output validation warnings
    guardrail_events: Optional[List[str]]  # All guardrail events (validation, contradictions, etc.)
    
    # PHASE 3: Collaboration Mode - Execution Constraints
    # Binding constraints extracted from user collaboration inputs.
    # These MUST be consumed by all decision agents and override default logic.
    execution_constraints: Optional[Any]  # ExecutionConstraints object
    
    # PHASE 3: Constraint Compliance Enforcement
    # Tracks whether agent outputs properly address all active constraints.
    # INVARIANT: No output is valid unless it explicitly accounts for every constraint.
    constraint_compliance_status: Optional[str]  # "COMPLIANT" | "NON_COMPLIANT" | "NO_CONSTRAINTS"
    constraint_violations: Optional[List[str]]  # List of constraint violations detected
    constraint_reflection: Optional[str]  # Required acknowledgment text that MUST appear in response


"""
Pydantic schemas for the agentic sourcing pipeline system.
All agent outputs must reference IDs (CAT-xx, SUP-xxx, CON-xxx).
"""
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class DTPStage(str, Enum):
    """Dynamic Transaction Pipeline stages"""
    DTP_01 = "DTP-01"  # Strategy
    DTP_02 = "DTP-02"  # Planning
    DTP_03 = "DTP-03"  # Sourcing
    DTP_04 = "DTP-04"  # Negotiation
    DTP_05 = "DTP-05"  # Contracting
    DTP_06 = "DTP-06"  # Execution


class TriggerSource(str, Enum):
    USER = "User"
    SIGNAL = "Signal"
    SYSTEM = "System"  # Proactive system-initiated cases


class CaseStatus(str, Enum):
    IN_PROGRESS = "In Progress"
    WAITING_HUMAN = "Waiting for Human Decision"
    COMPLETED = "Completed"
    REJECTED = "Rejected"


class DecisionImpact(str, Enum):
    """Materiality of an agent recommendation"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class SignalRegisterEntry(BaseModel):
    """Persistent signal register entry"""
    signal_type: str  # ContractExpiry | PerformanceDecline | SpendSpike | ComplianceRisk
    severity: Literal["Low", "Medium", "High"]
    confidence: float
    source: Literal["system", "agent"]
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DTPPolicyContext(BaseModel):
    """Policy constraints injected into the Supervisor"""
    allowed_actions: List[str] = Field(default_factory=list)
    mandatory_checks: List[str] = Field(default_factory=list)
    human_required_for: List[str] = Field(default_factory=list)
    allowed_strategies: Optional[List[str]] = None  # For renewal constraints (e.g., ["Renew", "Renegotiate", "Terminate"])
    allow_rfx_for_renewals: bool = False  # Whether RFx is allowed for renewal cases


class CaseSummary(BaseModel):
    """Compact structured summary maintained by Supervisor"""
    case_id: str
    category_id: str
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    dtp_stage: str
    trigger_source: str
    status: str
    created_date: str
    summary_text: str
    key_findings: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class Signal(BaseModel):
    """Signal definition"""
    signal_id: str
    signal_type: str  # e.g., "Contract Expiry", "Performance Alert"
    category_id: str
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    severity: str  # "High", "Medium", "Low"
    description: str
    detected_date: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HumanDecision(BaseModel):
    """Human decision for HIL workflow"""
    decision: Literal["Approve", "Reject"]
    reason: Optional[str] = None
    edited_fields: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    user_id: Optional[str] = None


class BudgetState(BaseModel):
    """Token budget tracking"""
    tokens_used: int = 0
    tokens_remaining: int = 3000
    cost_usd: float = 0.0
    model_calls: int = 0
    tier_1_calls: int = 0
    tier_2_calls: int = 0


class CacheMeta(BaseModel):
    """Cache metadata"""
    cache_hit: bool = False
    cache_key: Optional[str] = None
    input_hash: Optional[str] = None
    schema_version: str = "1.0"


class AgentActionLog(BaseModel):
    """Detailed agent action log with LLM input/output"""
    timestamp: str
    case_id: str
    dtp_stage: str
    trigger_source: str
    agent_name: str
    task_name: str
    model_used: str
    token_input: int = 0
    token_output: int = 0
    token_total: int = 0
    estimated_cost_usd: float = 0.0
    cache_hit: bool = False
    cache_key: Optional[str] = None
    input_hash: Optional[str] = None
    llm_input_payload: Dict[str, Any] = Field(default_factory=dict)
    output_payload: Dict[str, Any] = Field(default_factory=dict)
    output_summary: str = ""
    guardrail_events: List[str] = Field(default_factory=list)


# DTP-01 Triage Schemas

class RequestType(str, Enum):
    """Classification of incoming sourcing requests"""
    DEMAND_BASED = "Demand-Based"  # PO-driven, no existing contract
    RENEWAL = "Renewal"  # Contract expiry triggered
    AD_HOC = "Ad-Hoc"  # Off-system or manual request
    FAST_PASS = "Fast-Pass"  # Low-risk, pre-approved supplier


class TriageStatus(str, Enum):
    """Outcome of DTP-01 Triage"""
    PROCEED_TO_STRATEGY = "Proceed to Strategy"  # No coverage, sourcing required
    REDIRECT_TO_CATALOG = "Redirect to Catalog"  # Existing coverage found
    REQUIRES_CLARIFICATION = "Requires Clarification"  # Ambiguous request


class TriageResult(BaseModel):
    """DTP-01 Triage Agent output - Gatekeeper decision"""
    case_id: str
    request_type: RequestType
    status: TriageStatus
    matched_contract_id: Optional[str] = None  # If coverage found
    matched_supplier_id: Optional[str] = None  # If supplier already approved
    coverage_rationale: str = ""  # Why request is/isn't covered
    category_strategy_card_id: Optional[str] = None  # Linked strategy card
    estimated_spend_usd: Optional[float] = None
    requires_3_bids: bool = False  # Based on $1.5M threshold
    recommended_payment_terms: str = "Net 90"


class CategoryStrategyCard(BaseModel):
    """Pre-defined category strategy defaults loaded during DTP-01"""
    category_id: str
    category_name: str
    sourcing_rules: Dict[str, Any] = Field(default_factory=dict)
    # e.g., {"spend_threshold_3_bids_usd": 1500000, "min_suppliers_above_threshold": 3}
    defaults: Dict[str, Any] = Field(default_factory=dict)
    # e.g., {"payment_terms": "Net 90", "contract_type": "MSA"}
    evaluation_criteria: List[str] = Field(default_factory=list)
    preferred_route: str = "RFP"  # Default sourcing route


# Agent Output Schemas

class SignalAssessment(BaseModel):
    """Signal Interpretation Agent output"""
    signal_id: str
    category_id: str
    assessment: str
    recommended_action: Literal["Renew", "Renegotiate", "RFx", "Monitor", "Terminate"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: List[str] = Field(default_factory=list)
    urgency_score: int = Field(ge=1, le=10)
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    decision_impact: DecisionImpact = DecisionImpact.MEDIUM


class StrategyRecommendation(BaseModel):
    """Strategy Agent output (DTP-01)"""
    case_id: str
    category_id: str
    recommended_strategy: Literal["Renew", "Renegotiate", "RFx", "Terminate", "Monitor"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: List[str] = Field(default_factory=list)
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    estimated_savings_potential: Optional[float] = None
    risk_assessment: str = ""
    timeline_recommendation: str = ""
    decision_impact: DecisionImpact = DecisionImpact.MEDIUM
    # PHASE 3: Constraint acknowledgments (mandatory when constraints exist)
    constraint_acknowledgments: List[str] = Field(default_factory=list, description="Explicit acknowledgments of user constraints that shaped this recommendation")


class SupplierShortlist(BaseModel):
    """Supplier Evaluation Agent output (DTP-03/04)"""
    case_id: str
    category_id: str
    shortlisted_suppliers: List[Dict[str, Any]] = Field(default_factory=list)
    # Each supplier dict must include supplier_id: "SUP-xxx"
    evaluation_criteria: List[str] = Field(default_factory=list)
    recommendation: str
    top_choice_supplier_id: Optional[str] = None
    comparison_summary: str = ""
    decision_impact: DecisionImpact = DecisionImpact.MEDIUM
    # PHASE 3: Constraint acknowledgments (mandatory when constraints exist)
    constraint_acknowledgments: List[str] = Field(default_factory=list, description="Explicit acknowledgments of user constraints that shaped this evaluation")


class NegotiationPlan(BaseModel):
    """Negotiation Support Agent output (DTP-04)"""
    case_id: str
    category_id: str
    supplier_id: str
    negotiation_objectives: List[str] = Field(default_factory=list)
    target_terms: Dict[str, Any] = Field(default_factory=dict)
    leverage_points: List[str] = Field(default_factory=list)
    fallback_positions: Dict[str, Any] = Field(default_factory=dict)
    timeline: str = ""
    risk_mitigation: List[str] = Field(default_factory=list)
    decision_impact: DecisionImpact = DecisionImpact.HIGH
    # PHASE 3: Constraint acknowledgments
    constraint_acknowledgments: List[str] = Field(default_factory=list, description="Explicit acknowledgments of user constraints that shaped this plan")


class RFxDraft(BaseModel):
    """RFx Draft Agent output (DTP-03) - Table 3 aligned"""
    case_id: str
    category_id: str
    rfx_sections: Dict[str, str] = Field(default_factory=dict)  # Overview, Requirements, Evaluation Criteria, Timeline, Terms & Conditions
    completeness_check: Dict[str, bool] = Field(default_factory=dict)  # Rule-based completeness checks
    template_source: str = ""  # Which template was used
    explanation: str = ""  # LLM explanation of intent and adaptations
    # PHASE 3: Constraint acknowledgments
    constraint_acknowledgments: List[str] = Field(default_factory=list, description="Explicit acknowledgments of user constraints that shaped this draft")


class ContractExtraction(BaseModel):
    """Contract Support Agent output (DTP-04/05) - Table 3 aligned"""
    case_id: str
    category_id: str
    supplier_id: str
    extracted_terms: Dict[str, Any] = Field(default_factory=dict)  # Template-guided extracted terms
    validation_results: Dict[str, bool] = Field(default_factory=dict)  # Rule-based field validation
    mapping_explanations: Dict[str, str] = Field(default_factory=dict)  # LLM explanations of term mappings
    inconsistencies: List[str] = Field(default_factory=list)  # Flagged inconsistencies
    template_guidance: str = ""  # Which template/clause library was used
    # PHASE 3: Constraint acknowledgments
    constraint_acknowledgments: List[str] = Field(default_factory=list, description="Explicit acknowledgments of user constraints that shaped this extraction")


class ImplementationPlan(BaseModel):
    """Implementation Agent output (DTP-05/06) - Table 3 aligned"""
    case_id: str
    category_id: str
    supplier_id: str
    rollout_steps: List[Dict[str, Any]] = Field(default_factory=list)  # Deterministic rollout steps
    projected_savings: Optional[float] = None  # Deterministic calculation
    service_impacts: Dict[str, Any] = Field(default_factory=dict)  # Structured service impact summary
    kpi_summary: Dict[str, Any] = Field(default_factory=dict)  # LLM-structured KPI explanation
    explanation: str = ""  # LLM explanation of impacts and KPIs
    playbook_source: str = ""  # Which rollout playbook was used
    # PHASE 3: Constraint acknowledgments
    constraint_acknowledgments: List[str] = Field(default_factory=list, description="Explicit acknowledgments of user constraints that shaped this plan")


class CaseTrigger(BaseModel):
    """Proactive case trigger from signal aggregation"""
    trigger_type: Literal["Renewal", "Savings", "Risk", "Monitoring"]
    category_id: str
    supplier_id: Optional[str] = None
    contract_id: Optional[str] = None
    urgency: Literal["Low", "Medium", "High"]
    triggering_signals: List[str] = Field(default_factory=list)
    recommended_entry_stage: Literal["DTP-01"] = "DTP-01"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClarificationRequest(BaseModel):
    """Case Clarifier Agent output - targeted questions for humans"""
    reason: str
    questions: List[str] = Field(default_factory=list)
    suggested_options: Optional[List[str]] = None
    missing_information: List[str] = Field(default_factory=list)
    context_summary: str = ""


class OutOfScopeNotice(BaseModel):
    """Notice when requested action is out of agent capabilities"""
    requested_action: str
    reason: str
    suggested_next_steps: List[str] = Field(default_factory=list)
    alternative_actions: Optional[List[str]] = None
    external_action_required: bool = False


class AgentDialogue(BaseModel):
    """Agent 'Talk Back' message for reasoning, clarification, or strategic pivots"""
    agent_name: str
    message: str  # The "Talk Back" content (Visible to User)
    reasoning: str # Internal reasoning trace (Visible in "Thought Process")
    status: Literal["NeedClarification", "ConcernRaised", "SuggestAlternative", "Success"]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """A single message in the conversation history"""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class Case(BaseModel):
    """Full case model"""
    case_id: str
    name: str
    category_id: str
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    dtp_stage: str
    trigger_source: str
    user_intent: Optional[str] = None
    created_date: str
    updated_date: str
    created_timestamp: str  # ISO format timestamp
    updated_timestamp: str  # ISO format timestamp
    status: str
    summary: CaseSummary
    latest_agent_output: Optional[Union[
        SignalAssessment, StrategyRecommendation, SupplierShortlist, NegotiationPlan,
        RFxDraft, ContractExtraction, ImplementationPlan,
        ClarificationRequest, OutOfScopeNotice, AgentDialogue
    ]] = None
    latest_agent_name: Optional[str] = None
    activity_log: List[AgentActionLog] = Field(default_factory=list)
    chat_history: List[ChatMessage] = Field(default_factory=list)  # Stored conversation history
    human_decision: Optional[HumanDecision] = None



"""
Shared Pydantic schemas for frontend-backend communication.
All API request/response models are defined here.
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from shared.constants import (
    UserIntent, DocumentType, DataType, CaseStatus, 
    TriggerSource, DecisionImpact
)


# ============================================================
# CASE SCHEMAS
# ============================================================

class CaseSummary(BaseModel):
    """Compact case summary for list views."""
    case_id: str
    name: str
    category_id: str
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    dtp_stage: str
    trigger_source: str
    status: str
    created_date: str
    updated_date: str
    summary_text: str
    key_findings: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class CaseDetail(BaseModel):
    """Full case details for detail view."""
    case_id: str
    name: str
    category_id: str
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    dtp_stage: str
    trigger_source: str
    status: str
    created_date: str
    updated_date: str
    created_timestamp: str
    updated_timestamp: str
    summary: CaseSummary
    latest_agent_output: Optional[Dict[str, Any]] = None
    latest_agent_name: Optional[str] = None
    activity_log: List[Dict[str, Any]] = Field(default_factory=list)
    human_decision: Optional[Dict[str, Any]] = None


class CaseListResponse(BaseModel):
    """Response for case list endpoint."""
    cases: List[CaseSummary]
    total_count: int
    filters_applied: Dict[str, Any] = Field(default_factory=dict)


class CreateCaseRequest(BaseModel):
    """Request to create a new case."""
    category_id: str
    trigger_source: str = "User"
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    name: Optional[str] = None


class CreateCaseResponse(BaseModel):
    """Response after creating a case."""
    case_id: str
    success: bool
    message: str


# ============================================================
# CHAT / COPILOT SCHEMAS
# ============================================================

class ChatRequest(BaseModel):
    """Request for chat/copilot interaction."""
    case_id: str
    user_message: str
    use_tier_2: bool = False


class ChatResponse(BaseModel):
    """Response from chat/copilot."""
    case_id: str
    user_message: str
    assistant_message: str
    intent_classified: str  # EXPLAIN, EXPLORE, DECIDE, STATUS
    agents_called: List[str] = Field(default_factory=list)
    tokens_used: int = 0
    dtp_stage: str
    waiting_for_human: bool = False
    workflow_summary: Optional[Dict[str, Any]] = None
    retrieval_context: Optional[Dict[str, Any]] = None  # What was retrieved
    timestamp: str


# ============================================================
# DECISION SCHEMAS
# ============================================================

class DecisionRequest(BaseModel):
    """Request for human decision."""
    case_id: str
    decision: str  # "Approve" or "Reject"
    reason: Optional[str] = None
    edited_fields: Dict[str, Any] = Field(default_factory=dict)


class DecisionResponse(BaseModel):
    """Response after processing decision."""
    case_id: str
    decision: str
    success: bool
    new_dtp_stage: Optional[str] = None
    message: str


# ============================================================
# DOCUMENT INGESTION SCHEMAS
# ============================================================

class DocumentMetadata(BaseModel):
    """Metadata for document ingestion."""
    document_type: str  # Contract, Performance Report, RFx, Policy
    supplier_id: Optional[str] = None
    category_id: Optional[str] = None
    region: Optional[str] = None
    dtp_relevance: List[str] = Field(default_factory=list)  # DTP stages
    case_id: Optional[str] = None
    description: Optional[str] = None


class DocumentIngestRequest(BaseModel):
    """Request for document ingestion (metadata only, file sent separately)."""
    filename: str
    metadata: DocumentMetadata


class DocumentIngestResponse(BaseModel):
    """Response after document ingestion."""
    document_id: str
    filename: str
    success: bool
    chunks_created: int
    message: str
    metadata: DocumentMetadata


class DocumentListItem(BaseModel):
    """Item in document list."""
    document_id: str
    filename: str
    document_type: str
    supplier_id: Optional[str] = None
    category_id: Optional[str] = None
    ingested_at: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    """Response for document list."""
    documents: List[DocumentListItem]
    total_count: int


# ============================================================
# STRUCTURED DATA INGESTION SCHEMAS
# ============================================================

class DataIngestMetadata(BaseModel):
    """Metadata for structured data ingestion."""
    data_type: str  # Supplier Performance, Spend Data, SLA Events
    supplier_id: Optional[str] = None
    category_id: Optional[str] = None
    time_period: Optional[str] = None
    description: Optional[str] = None


class DataIngestRequest(BaseModel):
    """Request for structured data ingestion."""
    filename: str
    metadata: DataIngestMetadata


class DataIngestResponse(BaseModel):
    """Response after data ingestion."""
    ingestion_id: str
    filename: str
    success: bool
    rows_ingested: int
    table_name: str
    message: str
    validation_warnings: List[str] = Field(default_factory=list)


class DataPreviewRequest(BaseModel):
    """Request to preview data before ingestion."""
    filename: str
    data_type: str


class DataPreviewResponse(BaseModel):
    """Response with data preview."""
    columns: List[str]
    sample_rows: List[Dict[str, Any]]
    total_rows: int
    schema_valid: bool
    validation_errors: List[str] = Field(default_factory=list)


# ============================================================
# RETRIEVAL SCHEMAS
# ============================================================

class RetrievalRequest(BaseModel):
    """Request for RAG retrieval (agent use only)."""
    query: str
    case_id: Optional[str] = None
    supplier_id: Optional[str] = None
    category_id: Optional[str] = None
    dtp_stage: Optional[str] = None
    document_types: Optional[List[str]] = None
    top_k: int = 5


class RetrievalChunk(BaseModel):
    """A single retrieved chunk."""
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class RetrievalResponse(BaseModel):
    """Response from RAG retrieval."""
    query: str
    chunks: List[RetrievalChunk]
    total_found: int
    filters_applied: Dict[str, Any]


class SupplierDataRequest(BaseModel):
    """Request for supplier performance data."""
    supplier_id: str
    data_type: str  # performance, spend, sla
    time_window: Optional[str] = None  # e.g., "last_12_months"


class SupplierDataResponse(BaseModel):
    """Response with supplier data."""
    supplier_id: str
    data_type: str
    records: List[Dict[str, Any]]
    summary: Optional[Dict[str, Any]] = None


# ============================================================
# AGENT OUTPUT SCHEMAS
# ============================================================

class StrategyRecommendation(BaseModel):
    """Strategy Agent output."""
    case_id: str
    category_id: str
    recommended_strategy: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: List[str] = Field(default_factory=list)
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    estimated_savings_potential: Optional[float] = None
    risk_assessment: str = ""
    timeline_recommendation: str = ""
    decision_impact: str = "Medium"
    grounded_in: Optional[List[str]] = None  # Document IDs used


class SupplierShortlist(BaseModel):
    """Supplier Evaluation Agent output."""
    case_id: str
    category_id: str
    shortlisted_suppliers: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation_criteria: List[str] = Field(default_factory=list)
    recommendation: str
    top_choice_supplier_id: Optional[str] = None
    comparison_summary: str = ""
    decision_impact: str = "Medium"
    grounded_in: Optional[List[str]] = None


class NegotiationPlan(BaseModel):
    """Negotiation Support Agent output."""
    case_id: str
    category_id: str
    supplier_id: str
    negotiation_objectives: List[str] = Field(default_factory=list)
    target_terms: Dict[str, Any] = Field(default_factory=dict)
    leverage_points: List[str] = Field(default_factory=list)
    fallback_positions: Dict[str, Any] = Field(default_factory=dict)
    timeline: str = ""
    risk_mitigation: List[str] = Field(default_factory=list)
    decision_impact: str = "High"
    grounded_in: Optional[List[str]] = None


class SignalAssessment(BaseModel):
    """Signal Interpretation Agent output."""
    signal_id: str
    category_id: str
    assessment: str
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: List[str] = Field(default_factory=list)
    urgency_score: int = Field(ge=1, le=10)
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    decision_impact: str = "Medium"
    grounded_in: Optional[List[str]] = None


# ============================================================
# ACTIVITY LOG SCHEMAS
# ============================================================

class AgentActionLog(BaseModel):
    """Log entry for agent action."""
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
    retrieval_used: bool = False
    documents_retrieved: List[str] = Field(default_factory=list)
    output_summary: str = ""
    guardrail_events: List[str] = Field(default_factory=list)


# ============================================================
# HEALTH CHECK
# ============================================================

class HealthCheckResponse(BaseModel):
    """Backend health check response."""
    status: str
    version: str
    components: Dict[str, str]  # component_name -> status




"""
SQLModel models for the data lake simulation.
Tables:
- supplier_performance: KPI data for suppliers
- spend_metrics: Spend data by category/supplier
- sla_events: SLA compliance events
- ingestion_log: Log of all data ingestion events
- document_records: Metadata for ingested documents (content in ChromaDB)
"""
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
from uuid import uuid4


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


class SupplierPerformance(SQLModel, table=True):
    """Supplier performance KPI data."""
    __tablename__ = "supplier_performance"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    record_id: str = Field(default_factory=generate_uuid, index=True)
    supplier_id: str = Field(index=True)
    supplier_name: Optional[str] = None
    category_id: Optional[str] = Field(default=None, index=True)
    
    # Performance metrics
    overall_score: float = Field(default=0.0)
    quality_score: float = Field(default=0.0)
    delivery_score: float = Field(default=0.0)
    cost_variance: float = Field(default=0.0)  # % variance from contract
    responsiveness_score: float = Field(default=0.0)
    
    # Trend and status
    trend: Optional[str] = None  # "improving", "stable", "declining"
    risk_level: Optional[str] = None  # "low", "medium", "high"
    
    # Time context
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    measurement_date: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Metadata
    ingestion_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SpendMetric(SQLModel, table=True):
    """Spend data by category and supplier."""
    __tablename__ = "spend_metrics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    record_id: str = Field(default_factory=generate_uuid, index=True)
    
    # Identifiers
    supplier_id: Optional[str] = Field(default=None, index=True)
    category_id: Optional[str] = Field(default=None, index=True)
    contract_id: Optional[str] = Field(default=None, index=True)
    
    # Spend data
    spend_amount: float = Field(default=0.0)
    currency: str = Field(default="USD")
    budget_amount: Optional[float] = None
    variance_amount: Optional[float] = None
    variance_percent: Optional[float] = None
    
    # Classification
    spend_type: Optional[str] = None  # "direct", "indirect"
    cost_center: Optional[str] = None
    
    # Time context
    period: Optional[str] = None  # e.g., "2024-Q1"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    
    # Metadata
    ingestion_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SLAEvent(SQLModel, table=True):
    """SLA compliance events."""
    __tablename__ = "sla_events"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: str = Field(default_factory=generate_uuid, index=True)
    
    # Identifiers
    supplier_id: str = Field(index=True)
    contract_id: Optional[str] = Field(default=None, index=True)
    category_id: Optional[str] = Field(default=None, index=True)
    
    # Event details
    event_type: str  # "breach", "warning", "compliance"
    sla_metric: str  # e.g., "delivery_time", "quality", "response_time"
    target_value: Optional[float] = None
    actual_value: Optional[float] = None
    variance: Optional[float] = None
    
    # Impact
    severity: str = Field(default="medium")  # "low", "medium", "high", "critical"
    financial_impact: Optional[float] = None
    
    # Status
    status: str = Field(default="open")  # "open", "acknowledged", "resolved"
    resolution: Optional[str] = None
    
    # Timestamps
    event_date: str
    detected_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None
    
    # Metadata
    ingestion_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class IngestionLog(SQLModel, table=True):
    """Log of all data ingestion events."""
    __tablename__ = "ingestion_log"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ingestion_id: str = Field(default_factory=generate_uuid, index=True)
    
    # Source information
    source_type: str  # "document", "structured_data"
    data_type: str  # "supplier_performance", "spend_data", "sla_events", "contract", etc.
    filename: str
    file_size_bytes: Optional[int] = None
    
    # Processing details
    status: str = Field(default="pending")  # "pending", "processing", "completed", "failed"
    rows_processed: int = Field(default=0)
    rows_failed: int = Field(default=0)
    chunks_created: int = Field(default=0)  # For documents
    
    # Metadata
    supplier_id: Optional[str] = None
    category_id: Optional[str] = None
    case_id: Optional[str] = None
    
    # Error tracking
    error_message: Optional[str] = None
    validation_warnings: Optional[str] = None  # JSON string
    
    # Timestamps
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    # User context
    uploaded_by: Optional[str] = None


class DocumentRecord(SQLModel, table=True):
    """Metadata for ingested documents (content stored in ChromaDB)."""
    __tablename__ = "document_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: str = Field(default_factory=generate_uuid, index=True)
    
    # File info
    filename: str
    file_type: str  # "pdf", "docx", "txt"
    file_size_bytes: Optional[int] = None
    
    # Document classification
    document_type: str  # "Contract", "Performance Report", "RFx", "Policy"
    
    # Associations
    supplier_id: Optional[str] = Field(default=None, index=True)
    category_id: Optional[str] = Field(default=None, index=True)
    contract_id: Optional[str] = Field(default=None, index=True)
    case_id: Optional[str] = Field(default=None, index=True)
    region: Optional[str] = None
    
    # DTP relevance
    dtp_relevance: Optional[str] = None  # JSON array of DTP stages
    
    # Processing status
    chunk_count: int = Field(default=0)
    embedding_model: Optional[str] = None
    
    # Timestamps
    ingested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Metadata
    description: Optional[str] = None
    ingestion_id: Optional[str] = None


class CaseState(SQLModel, table=True):
    """Persistent case state for supervisor governance."""
    __tablename__ = "case_states"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: str = Field(unique=True, index=True)
    
    # Core state
    dtp_stage: str = Field(default="DTP-01")
    status: str = Field(default="Open")
    
    # Identifiers
    category_id: str
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    
    # Summary
    name: str
    summary_text: str
    key_findings: Optional[str] = None  # JSON array
    recommended_action: Optional[str] = None
    
    # Latest agent output (JSON)
    latest_agent_output: Optional[str] = None
    latest_agent_name: Optional[str] = None
    
    # Latest artifact pack ID
    latest_artifact_pack_id: Optional[str] = None
    
    # Artifact index by type (JSON: {type: [artifact_ids]})
    artifact_index: Optional[str] = None
    
    # Next actions cache (JSON)
    next_actions_cache: Optional[str] = None
    
    # Human decision
    human_decision: Optional[str] = None  # JSON
    
    # Activity log reference
    activity_log: Optional[str] = None  # JSON array
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Trigger
    trigger_source: str = Field(default="User")


class Artifact(SQLModel, table=True):
    """Persistent storage for agent-produced artifacts."""
    __tablename__ = "artifacts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: str = Field(unique=True, index=True)
    
    # Case association
    case_id: str = Field(index=True)
    
    # Artifact metadata
    type: str = Field(index=True)  # ArtifactType value
    title: str
    
    # Content
    content_json: Optional[str] = None  # JSON dict
    content_text: Optional[str] = None  # Human-readable
    
    # Grounding (JSON array of GroundingReference)
    grounded_in_json: Optional[str] = None
    
    # Provenance
    created_by_agent: str
    created_by_task: str = ""
    
    # Verification
    verification_status: str = Field(default="VERIFIED")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ArtifactPack(SQLModel, table=True):
    """Bundle of artifacts produced in a single agent execution."""
    __tablename__ = "artifact_packs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    pack_id: str = Field(unique=True, index=True)
    
    # Case association
    case_id: str = Field(index=True)
    
    # Pack metadata
    agent_name: str
    tasks_executed: Optional[str] = None  # JSON array
    
    # Artifact IDs in this pack (JSON array)
    artifact_ids: Optional[str] = None
    
    # Next actions (JSON array)
    next_actions_json: Optional[str] = None
    
    # Risks (JSON array)
    risks_json: Optional[str] = None
    
    # Notes (JSON array)
    notes_json: Optional[str] = None
    
    # Execution metadata for audit trail (JSON)
    execution_metadata_json: Optional[str] = None
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())





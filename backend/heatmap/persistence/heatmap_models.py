from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlmodel import SQLModel, Field, Column, JSON


class Opportunity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: Optional[str] = Field(default=None, index=True) # None for New Requests
    request_id: Optional[str] = Field(default=None, index=True) # None for Existing Contracts
    supplier_id: Optional[str] = Field(default=None)
    supplier_name: Optional[str] = Field(default=None)
    category: str
    subcategory: Optional[str] = Field(default=None)
    
    # Core Scores
    eus_score: Optional[float] = Field(default=None) # Expiry Urgency
    ius_score: Optional[float] = Field(default=None) # Implement Urgency
    fis_score: Optional[float] = Field(default=None) # Financial Impact
    es_score: Optional[float] = Field(default=None)  # Estimated Spend
    rss_score: Optional[float] = Field(default=None) # Supplier Risk
    scs_score: Optional[float] = Field(default=None) # Spend Concentration
    csis_score: Optional[float] = Field(default=None) # Category Spend Imp.
    sas_score: Optional[float] = Field(default=None) # Strategic Alignment
    
    # Final Calculation
    weights_used_json: str = Field(default="{}") 
    total_score: float = Field(default=0.0)
    tier: str = Field(default="T4") # T1, T2, T3, T4
    rank: Optional[int] = Field(default=None)
    
    # Explanations & Meta
    recommended_action_window: Optional[str] = Field(default=None)
    justification_summary: Optional[str] = Field(default=None)
    confidence_level: str = Field(default="High")
    status: str = Field(default="Pending") # Pending, Approved, Rejected
    last_refresh_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # batch = CSV pipeline row; intake = POST /api/heatmap/intake
    source: str = Field(default="batch")
    estimated_spend_usd: Optional[float] = Field(default=None)
    implementation_timeline_months: Optional[float] = Field(default=None)
    request_title: Optional[str] = Field(default=None)
    preferred_supplier_status: Optional[str] = Field(default=None)


class OpportunitySignal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    opportunity_id: int = Field(foreign_key="opportunity.id")
    signal_name: str
    signal_value: float
    normalized_value: float
    weight: float
    contribution: float
    rule_triggered: Optional[str] = Field(default=None)
    evidence_pointer: str


class ReviewFeedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    opportunity_id: int = Field(foreign_key="opportunity.id")
    reviewer_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    adjustment_type: str # 'delta', 'override'
    adjustment_value: float
    reason_code: str
    comment_text: Optional[str] = Field(default=None)
    component_affected: str # e.g. 'total_score', 'rss_score'


class ScoringWeights(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    w_spend: float
    w_contract: float
    w_strategy: float
    w_risk: float
    is_suggested: bool = Field(default=False)
    accepted_by_user: bool = Field(default=False)


class ScoringRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(unique=True, index=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_opportunities: int
    weights_snapshot_json: str


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str # e.g., 'SCORE_OVERRIDE', 'CASE_APPROVED'
    entity_id: str
    old_value: Optional[str] = Field(default=None)
    new_value: Optional[str] = Field(default=None)
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

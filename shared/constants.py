"""
Shared constants for the agentic sourcing system.
"""
from enum import Enum

# DTP Stages
DTP_STAGES = ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"]

DTP_STAGE_NAMES = {
    "DTP-01": "Strategy",
    "DTP-02": "Planning", 
    "DTP-03": "Sourcing",
    "DTP-04": "Negotiation",
    "DTP-05": "Contracting",
    "DTP-06": "Execution"
}


# =============================================================================
# OFFICIAL AGENT NAMES (7 first-class agents)
# =============================================================================
class AgentName(str, Enum):
    SUPERVISOR = "SUPERVISOR"
    SOURCING_SIGNAL = "SOURCING_SIGNAL"
    SUPPLIER_SCORING = "SUPPLIER_SCORING"
    RFX_DRAFT = "RFX_DRAFT"
    NEGOTIATION_SUPPORT = "NEGOTIATION_SUPPORT"
    CONTRACT_SUPPORT = "CONTRACT_SUPPORT"
    IMPLEMENTATION = "IMPLEMENTATION"


# =============================================================================
# ARTIFACT TYPES (DTP-aligned work products)
# =============================================================================
class ArtifactType(str, Enum):
    # Sourcing Signal Agent outputs
    SIGNAL_REPORT = "SIGNAL_REPORT"
    SIGNAL_SUMMARY = "SIGNAL_SUMMARY"
    AUTOPREP_BUNDLE = "AUTOPREP_BUNDLE"
    
    # Supplier Scoring Agent outputs
    EVALUATION_SCORECARD = "EVALUATION_SCORECARD"
    SUPPLIER_SCORECARD = "SUPPLIER_SCORECARD"
    SUPPLIER_SHORTLIST = "SUPPLIER_SHORTLIST"
    
    # RFx Draft Agent outputs
    RFX_PATH = "RFX_PATH"
    RFX_DRAFT_PACK = "RFX_DRAFT_PACK"
    RFX_QA_TRACKER = "RFX_QA_TRACKER"
    
    # Negotiation Support Agent outputs
    NEGOTIATION_PLAN = "NEGOTIATION_PLAN"
    LEVERAGE_SUMMARY = "LEVERAGE_SUMMARY"
    TARGET_TERMS = "TARGET_TERMS"
    
    # Contract Support Agent outputs
    KEY_TERMS_EXTRACT = "KEY_TERMS_EXTRACT"
    TERM_VALIDATION_REPORT = "TERM_VALIDATION_REPORT"
    CONTRACT_HANDOFF_PACKET = "CONTRACT_HANDOFF_PACKET"
    
    # Implementation Agent outputs
    IMPLEMENTATION_CHECKLIST = "IMPLEMENTATION_CHECKLIST"
    EARLY_INDICATORS_REPORT = "EARLY_INDICATORS_REPORT"
    VALUE_CAPTURE_TEMPLATE = "VALUE_CAPTURE_TEMPLATE"
    
    # Supervisor outputs
    STATUS_SUMMARY = "STATUS_SUMMARY"
    NEXT_BEST_ACTIONS = "NEXT_BEST_ACTIONS"


# =============================================================================
# ARTIFACT PLACEMENT (UI section routing)
# =============================================================================
class ArtifactPlacement(str, Enum):
    """UI sections where artifacts can be placed."""
    DECISION_CONSOLE = "decision_console"
    RISK_PANEL = "risk_panel"
    SUPPLIER_COMPARE = "supplier_compare"
    CASE_SUMMARY = "case_summary"
    TIMELINE = "timeline"
    ACTIVITY_LOG = "activity_log"


# =============================================================================
# USER INTENT CLASSIFICATION (Two-level)
# =============================================================================
class UserGoal(str, Enum):
    """Primary user goal - what outcome they're looking for."""
    TRACK = "TRACK"           # Monitor / check status
    UNDERSTAND = "UNDERSTAND" # Learn / get explanation
    CREATE = "CREATE"         # Generate artifacts/drafts
    CHECK = "CHECK"           # Validate / verify compliance
    DECIDE = "DECIDE"         # Make a decision (requires approval)


class WorkType(str, Enum):
    """Secondary work type - what kind of work is needed."""
    ARTIFACT = "ARTIFACT"     # Generate work product
    DATA = "DATA"             # Retrieve/analyze data
    APPROVAL = "APPROVAL"     # Human decision required
    COMPLIANCE = "COMPLIANCE" # Policy/rule check
    VALUE = "VALUE"           # Value/savings analysis


# Legacy intent classification (kept for backward compatibility)
class UserIntent(str, Enum):
    EXPLAIN = "EXPLAIN"      # User wants explanation/information
    EXPLORE = "EXPLORE"      # User wants to explore alternatives (no state change)
    DECIDE = "DECIDE"        # User wants to make a decision (requires approval)
    STATUS = "STATUS"        # User wants status update
    UNKNOWN = "UNKNOWN"


# =============================================================================
# VERIFICATION STATUS
# =============================================================================
class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"       # Fully grounded in data
    UNVERIFIED = "UNVERIFIED"   # Missing grounding, needs human confirmation
    PARTIAL = "PARTIAL"         # Some grounding missing


# Document Types for RAG
class DocumentType(str, Enum):
    CONTRACT = "Contract"
    PERFORMANCE_REPORT = "Performance Report"
    RFX = "RFx"
    POLICY = "Policy"
    MARKET_REPORT = "Market Report"
    OTHER = "Other"


# Data Types for Structured Ingestion
class DataType(str, Enum):
    SUPPLIER_PERFORMANCE = "Supplier Performance"
    SPEND_DATA = "Spend Data"
    SLA_EVENTS = "SLA Events"


# Case Status
class CaseStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    WAITING_HUMAN = "Waiting for Human Decision"
    COMPLETED = "Completed"
    REJECTED = "Rejected"


# Trigger Sources
class TriggerSource(str, Enum):
    USER = "User"
    SIGNAL = "Signal"


# Decision Impact Levels
class DecisionImpact(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# API Endpoints
API_BASE_URL = "http://localhost:8000"
API_ENDPOINTS = {
    "cases": "/api/cases",
    "case_detail": "/api/cases/{case_id}",
    "chat": "/api/chat",
    "ingest_document": "/api/ingest/document",
    "ingest_data": "/api/ingest/data",
    "retrieve": "/api/retrieve",
    "approve_decision": "/api/decisions/approve",
    "reject_decision": "/api/decisions/reject",
}





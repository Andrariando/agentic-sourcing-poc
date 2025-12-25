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

# Intent Classification
class UserIntent(str, Enum):
    EXPLAIN = "EXPLAIN"      # User wants explanation/information
    EXPLORE = "EXPLORE"      # User wants to explore alternatives (no state change)
    DECIDE = "DECIDE"        # User wants to make a decision (requires approval)
    STATUS = "STATUS"        # User wants status update
    UNKNOWN = "UNKNOWN"


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




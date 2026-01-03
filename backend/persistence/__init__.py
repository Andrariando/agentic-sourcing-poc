"""Persistence layer - SQLite data lake simulation."""
from backend.persistence.database import get_engine, get_session, init_db
from backend.persistence.models import (
    SupplierPerformance, SpendMetric, SLAEvent, 
    IngestionLog, DocumentRecord
)





"""
Database connection and initialization for SQLite data lake.
"""
import os
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine
from typing import Generator

# Database path - in project root
DB_PATH = Path(__file__).parent.parent.parent / "data" / "datalake.db"
DB_URL = f"sqlite:///{DB_PATH}"

# Engine singleton
_engine = None


def get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        # Ensure data directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            DB_URL,
            echo=False,
            connect_args={"check_same_thread": False}
        )
    return _engine


def init_db():
    """Initialize database tables."""
    from backend.persistence.models import (
        SupplierPerformance, SpendMetric, SLAEvent,
        IngestionLog, DocumentRecord, CaseState
    )
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    engine = get_engine()
    with Session(engine) as session:
        yield session


def get_db_session() -> Session:
    """Get a database session (non-generator version)."""
    engine = get_engine()
    return Session(engine)


# Initialize on import
try:
    init_db()
except Exception:
    pass  # Will be initialized on first use


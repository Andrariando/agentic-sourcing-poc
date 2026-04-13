"""
Database connection and initialization for SQLite data lake.
"""
import os
import tempfile
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text
from typing import Generator

# Database path - use temp directory for Streamlit Cloud (read-only filesystem)
def _get_db_path() -> Path:
    """Get writable database path."""
    # Check if we're on Streamlit Cloud (read-only filesystem)
    cwd = os.getcwd()
    is_streamlit_cloud = "/mount/src/" in cwd or cwd.startswith("/mount/")
    
    if is_streamlit_cloud:
        # Use temp directory for Streamlit Cloud
        temp_dir = Path(tempfile.gettempdir()) / "agentic_sourcing"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir / "datalake.db"
    else:
        # Use project data directory for local development
        return Path(__file__).parent.parent.parent / "data" / "datalake.db"

DB_PATH = _get_db_path()
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


def _sqlite_add_column_if_missing(table: str, column: str, ddl: str) -> None:
    """Best-effort migration for existing SQLite files (create_all does not add columns)."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            names = {r[1] for r in rows}  # column name
            if column not in names:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                conn.commit()
    except Exception:
        pass


def init_db():
    """Initialize database tables."""
    from backend.persistence.models import (
        SupplierPerformance, SpendMetric, SLAEvent,
        IngestionLog, DocumentRecord, CaseState,
        Artifact, ArtifactPack, ChatMessage, S2CProcuraBotFeedback
    )
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _sqlite_add_column_if_missing("case_states", "working_documents_json", "working_documents_json TEXT")
    _sqlite_add_column_if_missing("case_states", "cancel_reason_code", "cancel_reason_code TEXT")
    _sqlite_add_column_if_missing("case_states", "cancel_reason_text", "cancel_reason_text TEXT")
    _sqlite_add_column_if_missing("case_states", "cancelled_at", "cancelled_at TEXT")


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


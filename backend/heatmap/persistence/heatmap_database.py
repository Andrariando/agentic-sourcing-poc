import os
import tempfile
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine
from typing import Generator
from backend.persistence.db_interface import DatabaseInterface


def _get_heatmap_db_path() -> Path:
    """Get writable database path for Heatmap."""
    cwd = os.getcwd()
    is_streamlit_cloud = "/mount/src/" in cwd or cwd.startswith("/mount/")
    
    if is_streamlit_cloud:
        temp_dir = Path(tempfile.gettempdir()) / "agentic_sourcing_heatmap"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir / "heatmap.db"
    else:
        return Path(__file__).parent.parent.parent.parent / "data" / "heatmap.db"

DB_PATH = _get_heatmap_db_path()
DB_URL = f"sqlite:///{DB_PATH}"

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            DB_URL,
            echo=False,
            connect_args={"check_same_thread": False}
        )
    return _engine


class HeatmapDatabase(DatabaseInterface):
    """
    SQLite implementation for the specific Heatmap database containing opportunities and feedback.
    """

    def init_db(self) -> None:
        from backend.heatmap.persistence.heatmap_models import (
            Opportunity, OpportunitySignal, ReviewFeedback, 
            ScoringWeights, ScoringRun, AuditLog
        )
        engine = get_engine()
        SQLModel.metadata.create_all(engine)

    def get_session(self) -> Generator[Session, None, None]:
        engine = get_engine()
        with Session(engine) as session:
            yield session

    def get_db_session(self) -> Session:
        engine = get_engine()
        return Session(engine)

heatmap_db = HeatmapDatabase()

# Initialize on import
try:
    heatmap_db.init_db()
except Exception:
    pass

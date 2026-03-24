from abc import ABC, abstractmethod
from typing import Generator
from sqlmodel import Session


class DatabaseInterface(ABC):
    """
    Abstract interface for database operations.
    Allows swapping between SQLite and cloud databases (e.g. Azure SQL)
    """
    
    @abstractmethod
    def init_db(self) -> None:
        """Initialize database tables."""
        pass

    @abstractmethod
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session generator (for FastAPI dependencies)."""
        pass

    @abstractmethod
    def get_db_session(self) -> Session:
        """Get a database session (non-generator)."""
        pass

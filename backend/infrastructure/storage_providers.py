"""
Central provider/factory layer for storage backends.

Use this module as the single import point for:
- app database (legacy DTP)
- heatmap database
- legacy vector store
- heatmap vector store

This keeps backend modules decoupled from concrete SQLite/Chroma implementations
and makes cloud migration (Azure SQL / Azure AI Search) a controlled swap.
"""
from __future__ import annotations

import os
from typing import Generator, Optional

from sqlmodel import Session

from backend.persistence.db_interface import DatabaseInterface
from backend.rag.vector_store_interface import VectorStoreInterface


class _SQLiteAppDatabase(DatabaseInterface):
    """Adapter that exposes the legacy SQLite app DB through DatabaseInterface."""

    def init_db(self) -> None:
        from backend.persistence.database import init_db

        init_db()

    def get_session(self) -> Generator[Session, None, None]:
        from backend.persistence.database import get_session

        return get_session()

    def get_db_session(self) -> Session:
        from backend.persistence.database import get_db_session

        return get_db_session()


class _AzureSqlDatabase(DatabaseInterface):
    """
    Azure SQL adapter scaffold.

    TODO:
    - Build SQLAlchemy engine from AZURE_SQL_CONNECTION_STRING.
    - Add migrations/bootstrap strategy (Alembic or startup migration runner).
    - Ensure parity for SQLModel metadata creation where needed.
    """

    def __init__(self, *, domain: str):
        self.domain = domain
        self.connection_string = _required_env("AZURE_SQL_CONNECTION_STRING")

    def init_db(self) -> None:
        raise NotImplementedError(
            f"Azure SQL init not implemented for domain '{self.domain}'. "
            "Wire engine + migrations in _AzureSqlDatabase.init_db()."
        )

    def get_session(self) -> Generator[Session, None, None]:
        raise NotImplementedError(
            f"Azure SQL session generator not implemented for domain '{self.domain}'."
        )

    def get_db_session(self) -> Session:
        raise NotImplementedError(
            f"Azure SQL session creation not implemented for domain '{self.domain}'."
        )


class _AzureAISearchVectorStore(VectorStoreInterface):
    """
    Azure AI Search vector adapter scaffold.

    TODO:
    - Implement chunk upsert/search/delete/count against Azure AI Search index.
    - Ensure metadata filters map to Azure Search filter syntax.
    - Use AZURE_OPENAI_EMBEDDING_DEPLOYMENT (or equivalent) for embeddings if needed.
    """

    def __init__(self, *, index_env: str):
        self.endpoint = _required_env("AZURE_SEARCH_ENDPOINT")
        self.api_key = _required_env("AZURE_SEARCH_API_KEY")
        self.index_name = _required_env(index_env)

    def add_chunks(self, chunks, document_id, metadata):
        raise NotImplementedError(
            f"Azure AI Search add_chunks not implemented for index '{self.index_name}'."
        )

    def search(self, query, n_results=5, where=None, where_document=None):
        raise NotImplementedError(
            f"Azure AI Search search not implemented for index '{self.index_name}'."
        )

    def delete_document(self, document_id: str) -> int:
        raise NotImplementedError(
            f"Azure AI Search delete_document not implemented for index '{self.index_name}'."
        )

    def count(self) -> int:
        raise NotImplementedError(
            f"Azure AI Search count not implemented for index '{self.index_name}'."
        )


_app_db_singleton: Optional[DatabaseInterface] = None
_heatmap_db_singleton: Optional[DatabaseInterface] = None
_legacy_vector_singleton: Optional[VectorStoreInterface] = None
_heatmap_vector_singleton: Optional[VectorStoreInterface] = None


def _norm(value: Optional[str], default: str) -> str:
    return (value or default).strip().lower()


def _required_env(key: str) -> str:
    val = (os.getenv(key) or "").strip()
    if not val:
        raise ValueError(f"Missing required environment variable: {key}")
    return val


def get_app_db() -> DatabaseInterface:
    """
    Returns the database provider for the legacy DTP app domain.

    Env:
    - APP_DB_BACKEND=sqlite|azure_sql
    """
    global _app_db_singleton
    if _app_db_singleton is not None:
        return _app_db_singleton

    backend = _norm(os.getenv("APP_DB_BACKEND"), "sqlite")
    if backend == "sqlite":
        _app_db_singleton = _SQLiteAppDatabase()
        return _app_db_singleton

    if backend == "azure_sql":
        _app_db_singleton = _AzureSqlDatabase(domain="app")
        return _app_db_singleton

    raise ValueError(f"Unsupported APP_DB_BACKEND: {backend}")


def get_heatmap_db() -> DatabaseInterface:
    """
    Returns the database provider for heatmap domain.

    Env:
    - HEATMAP_DB_BACKEND=sqlite|azure_sql
    """
    global _heatmap_db_singleton
    if _heatmap_db_singleton is not None:
        return _heatmap_db_singleton

    backend = _norm(os.getenv("HEATMAP_DB_BACKEND"), "sqlite")
    if backend == "sqlite":
        from backend.heatmap.persistence.heatmap_database import heatmap_db

        _heatmap_db_singleton = heatmap_db
        return _heatmap_db_singleton

    if backend == "azure_sql":
        _heatmap_db_singleton = _AzureSqlDatabase(domain="heatmap")
        return _heatmap_db_singleton

    raise ValueError(f"Unsupported HEATMAP_DB_BACKEND: {backend}")


def get_legacy_vector_store() -> VectorStoreInterface:
    """
    Returns vector store provider for legacy DTP retrieval.

    Env:
    - LEGACY_VECTOR_BACKEND=chroma|azure_ai_search
    """
    global _legacy_vector_singleton
    if _legacy_vector_singleton is not None:
        return _legacy_vector_singleton

    backend = _norm(os.getenv("LEGACY_VECTOR_BACKEND"), "chroma")
    if backend == "chroma":
        from backend.rag.vector_store import get_vector_store

        _legacy_vector_singleton = get_vector_store()
        return _legacy_vector_singleton

    if backend == "azure_ai_search":
        _legacy_vector_singleton = _AzureAISearchVectorStore(
            index_env="AZURE_SEARCH_INDEX_LEGACY"
        )
        return _legacy_vector_singleton

    raise ValueError(f"Unsupported LEGACY_VECTOR_BACKEND: {backend}")


def get_heatmap_vector_store() -> VectorStoreInterface:
    """
    Returns vector store provider for heatmap feedback/copilot memory.

    Env:
    - HEATMAP_VECTOR_BACKEND=chroma|azure_ai_search
    """
    global _heatmap_vector_singleton
    if _heatmap_vector_singleton is not None:
        return _heatmap_vector_singleton

    backend = _norm(os.getenv("HEATMAP_VECTOR_BACKEND"), "chroma")
    if backend == "chroma":
        from backend.heatmap.persistence.heatmap_vector_store import get_heatmap_vector_store

        _heatmap_vector_singleton = get_heatmap_vector_store()
        return _heatmap_vector_singleton

    if backend == "azure_ai_search":
        _heatmap_vector_singleton = _AzureAISearchVectorStore(
            index_env="AZURE_SEARCH_INDEX_HEATMAP"
        )
        return _heatmap_vector_singleton

    raise ValueError(f"Unsupported HEATMAP_VECTOR_BACKEND: {backend}")


def initialize_storage_backends() -> None:
    """Initialize both DB providers during app startup."""
    get_app_db().init_db()
    get_heatmap_db().init_db()

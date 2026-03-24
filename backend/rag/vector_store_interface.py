from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class VectorStoreInterface(ABC):
    """
    Abstract interface for vector store operations.
    Allows swapping between ChromaDB, Azure AI Search, etc.
    """
    
    @abstractmethod
    def add_chunks(
        self,
        chunks: List[str],
        document_id: str,
        metadata: Dict[str, Any]
    ) -> List[str]:
        """Add document chunks to vector store."""
        pass
        
    @abstractmethod
    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for relevant chunks."""
        pass
        
    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        """Delete all chunks for a document."""
        pass
        
    @abstractmethod
    def count(self) -> int:
        """Get total number of chunks."""
        pass

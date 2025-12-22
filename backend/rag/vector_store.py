"""
ChromaDB vector store for document embeddings.
"""
import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import uuid4
import chromadb
from chromadb.config import Settings

# Optional: OpenAI embeddings
try:
    from langchain_openai import OpenAIEmbeddings
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# Vector store path - use temp directory for Streamlit Cloud
def _get_chroma_path() -> Path:
    """Get writable ChromaDB path."""
    cwd = os.getcwd()
    is_streamlit_cloud = "/mount/src/" in cwd or cwd.startswith("/mount/")
    
    if is_streamlit_cloud:
        temp_dir = Path(tempfile.gettempdir()) / "agentic_sourcing" / "chromadb"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    else:
        return Path(__file__).parent.parent.parent / "data" / "chromadb"

CHROMA_PATH = _get_chroma_path()
COLLECTION_NAME = "sourcing_documents"


class VectorStore:
    """
    ChromaDB vector store for document chunks.
    
    Each chunk has:
    - id: unique chunk ID
    - document: text content
    - embedding: vector representation
    - metadata: document_id, document_type, supplier_id, category_id, dtp_relevance, etc.
    """
    
    def __init__(self):
        """Initialize ChromaDB client and collection."""
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Sourcing documents for RAG"}
        )
        
        # Initialize embedding function
        self._embedding_fn = None
        if HAS_OPENAI and os.getenv("OPENAI_API_KEY"):
            try:
                self._embedding_fn = OpenAIEmbeddings(
                    model="text-embedding-3-small"
                )
            except Exception:
                pass
    
    def add_chunks(
        self,
        chunks: List[str],
        document_id: str,
        metadata: Dict[str, Any]
    ) -> List[str]:
        """
        Add document chunks to vector store.
        
        Args:
            chunks: List of text chunks
            document_id: Parent document ID
            metadata: Document metadata (document_type, supplier_id, category_id, etc.)
            
        Returns:
            List of chunk IDs
        """
        if not chunks:
            return []
        
        chunk_ids = []
        documents = []
        metadatas = []
        embeddings = None
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            chunk_ids.append(chunk_id)
            documents.append(chunk)
            
            # Build chunk metadata
            chunk_meta = {
                "document_id": document_id,
                "chunk_index": i,
                "chunk_count": len(chunks),
                **{k: v for k, v in metadata.items() if v is not None}
            }
            
            # Handle list fields (ChromaDB doesn't support lists directly)
            if "dtp_relevance" in chunk_meta and isinstance(chunk_meta["dtp_relevance"], list):
                chunk_meta["dtp_relevance"] = json.dumps(chunk_meta["dtp_relevance"])
            
            metadatas.append(chunk_meta)
        
        # Generate embeddings if available
        if self._embedding_fn:
            try:
                embeddings = self._embedding_fn.embed_documents(documents)
            except Exception:
                embeddings = None
        
        # Add to collection
        if embeddings:
            self.collection.add(
                ids=chunk_ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
        else:
            # Let ChromaDB use default embeddings
            self.collection.add(
                ids=chunk_ids,
                documents=documents,
                metadatas=metadatas
            )
        
        return chunk_ids
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for relevant chunks.
        
        Args:
            query: Search query
            n_results: Number of results to return
            where: Metadata filter (e.g., {"supplier_id": "SUP-001"})
            where_document: Document content filter
            
        Returns:
            Dict with ids, documents, metadatas, distances
        """
        # Generate query embedding if available
        query_embedding = None
        if self._embedding_fn:
            try:
                query_embedding = self._embedding_fn.embed_query(query)
            except Exception:
                pass
        
        # Build query kwargs
        kwargs = {
            "n_results": n_results,
        }
        
        if query_embedding:
            kwargs["query_embeddings"] = [query_embedding]
        else:
            kwargs["query_texts"] = [query]
        
        if where:
            kwargs["where"] = where
        
        if where_document:
            kwargs["where_document"] = where_document
        
        results = self.collection.query(**kwargs)
        
        return results
    
    def delete_document(self, document_id: str) -> int:
        """
        Delete all chunks for a document.
        
        Returns:
            Number of chunks deleted
        """
        # Get all chunks for this document
        results = self.collection.get(
            where={"document_id": document_id}
        )
        
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])
        
        return 0
    
    def get_document_chunks(self, document_id: str) -> Dict[str, Any]:
        """Get all chunks for a document."""
        return self.collection.get(
            where={"document_id": document_id}
        )
    
    def count(self) -> int:
        """Get total number of chunks."""
        return self.collection.count()
    
    def reset(self):
        """Delete all data (use with caution)."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Sourcing documents for RAG"}
        )


# Singleton instance
_vector_store = None


def get_vector_store() -> VectorStore:
    """Get or create vector store singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


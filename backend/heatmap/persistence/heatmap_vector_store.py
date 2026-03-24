import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from backend.rag.vector_store_interface import VectorStoreInterface

try:
    from langchain_openai import OpenAIEmbeddings
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def _get_chroma_path() -> Path:
    cwd = os.getcwd()
    is_streamlit_cloud = "/mount/src/" in cwd or cwd.startswith("/mount/")
    
    if is_streamlit_cloud:
        temp_dir = Path(tempfile.gettempdir()) / "agentic_sourcing_heatmap" / "chromadb"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    else:
        return Path(__file__).parent.parent.parent.parent / "data" / "chromadb"

CHROMA_PATH = _get_chroma_path()
COLLECTION_NAME = "heatmap_documents"


class HeatmapVectorStore(VectorStoreInterface):
    """
    ChromaDB vector store specifically for heatmap feedback and opportunity documents.
    """
    
    def __init__(self):
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Feedback and knowledge for the Heatmap agentic loops"}
        )
        
        self._embedding_fn = None
        if HAS_OPENAI and os.getenv("OPENAI_API_KEY"):
            try:
                self._embedding_fn = OpenAIEmbeddings(
                    model="text-embedding-3-small"
                )
            except Exception:
                pass
    
    def add_chunks(self, chunks: List[str], document_id: str, metadata: Dict[str, Any]) -> List[str]:
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
            
            chunk_meta = {
                "document_id": document_id,
                "chunk_index": i,
                "chunk_count": len(chunks),
                **{k: v for k, v in metadata.items() if v is not None}
            }
            
            for k, v in chunk_meta.items():
                if isinstance(v, list) or isinstance(v, dict):
                    chunk_meta[k] = json.dumps(v)
            
            metadatas.append(chunk_meta)
        
        if self._embedding_fn:
            try:
                embeddings = self._embedding_fn.embed_documents(documents)
            except Exception:
                pass
                
        if embeddings:
            self.collection.add(ids=chunk_ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        else:
            self.collection.add(ids=chunk_ids, documents=documents, metadatas=metadatas)
        
        return chunk_ids
    
    def search(self, query: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None, where_document: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query_embedding = None
        if self._embedding_fn:
            try:
                query_embedding = self._embedding_fn.embed_query(query)
            except Exception:
                pass
                
        kwargs = {"n_results": n_results}
        
        if query_embedding:
            kwargs["query_embeddings"] = [query_embedding]
        else:
            kwargs["query_texts"] = [query]
            
        if where:
            kwargs["where"] = where
        if where_document:
            kwargs["where_document"] = where_document
            
        return self.collection.query(**kwargs)
    
    def delete_document(self, document_id: str) -> int:
        results = self.collection.get(where={"document_id": document_id})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0
        
    def count(self) -> int:
        return self.collection.count()


_heatmap_vector_store = None

def get_heatmap_vector_store() -> HeatmapVectorStore:
    global _heatmap_vector_store
    if _heatmap_vector_store is None:
        _heatmap_vector_store = HeatmapVectorStore()
    return _heatmap_vector_store

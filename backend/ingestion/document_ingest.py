"""
Document ingestion pipeline for RAG.
Parses PDF, DOCX, TXT files, chunks text, and stores in ChromaDB.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO
from uuid import uuid4
from datetime import datetime

# Document parsing libraries
try:
    import PyPDF2
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    from docx import Document as DocxDocument
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

from backend.rag.vector_store import get_vector_store
from backend.persistence.database import get_db_session
from backend.persistence.models import DocumentRecord, IngestionLog


class DocumentIngester:
    """
    Document ingestion pipeline.
    
    Flow:
    1. Accept uploaded file + metadata
    2. Parse text content
    3. Chunk into semantic units
    4. Store chunks in ChromaDB with metadata
    5. Store document record in SQLite
    6. Log ingestion event
    """
    
    # Chunk configuration
    CHUNK_SIZE = 1000  # characters
    CHUNK_OVERLAP = 200  # characters
    
    def __init__(self):
        self.vector_store = get_vector_store()
    
    def ingest(
        self,
        file_content: bytes,
        filename: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ingest a document into the RAG system.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            metadata: Document metadata (document_type, supplier_id, etc.)
            
        Returns:
            Dict with document_id, success, chunks_created, message
        """
        document_id = str(uuid4())
        ingestion_id = str(uuid4())
        
        # Start ingestion log
        session = get_db_session()
        log = IngestionLog(
            ingestion_id=ingestion_id,
            source_type="document",
            data_type=metadata.get("document_type", "Unknown"),
            filename=filename,
            file_size_bytes=len(file_content),
            status="processing",
            supplier_id=metadata.get("supplier_id"),
            category_id=metadata.get("category_id"),
            case_id=metadata.get("case_id")
        )
        session.add(log)
        session.commit()
        
        try:
            # 1. Determine file type and parse
            file_ext = Path(filename).suffix.lower()
            text_content = self._parse_file(file_content, file_ext)
            
            if not text_content or not text_content.strip():
                raise ValueError("No text content extracted from document")
            
            # 2. Chunk the text
            chunks = self._chunk_text(text_content)
            
            if not chunks:
                raise ValueError("No chunks created from document")
            
            # 3. Store chunks in vector store
            chunk_ids = self.vector_store.add_chunks(
                chunks=chunks,
                document_id=document_id,
                metadata={
                    "document_type": metadata.get("document_type"),
                    "supplier_id": metadata.get("supplier_id"),
                    "category_id": metadata.get("category_id"),
                    "region": metadata.get("region"),
                    "dtp_relevance": metadata.get("dtp_relevance", []),
                    "case_id": metadata.get("case_id"),
                    "filename": filename
                }
            )
            
            # 4. Store document record
            doc_record = DocumentRecord(
                document_id=document_id,
                filename=filename,
                file_type=file_ext.lstrip("."),
                file_size_bytes=len(file_content),
                document_type=metadata.get("document_type", "Other"),
                supplier_id=metadata.get("supplier_id"),
                category_id=metadata.get("category_id"),
                contract_id=metadata.get("contract_id"),
                case_id=metadata.get("case_id"),
                region=metadata.get("region"),
                dtp_relevance=json.dumps(metadata.get("dtp_relevance", [])),
                chunk_count=len(chunks),
                embedding_model="text-embedding-3-small",
                description=metadata.get("description"),
                ingestion_id=ingestion_id
            )
            session.add(doc_record)
            
            # 5. Update ingestion log
            log.status = "completed"
            log.chunks_created = len(chunks)
            log.completed_at = datetime.now().isoformat()
            session.commit()
            
            return {
                "document_id": document_id,
                "filename": filename,
                "success": True,
                "chunks_created": len(chunks),
                "message": f"Successfully ingested {filename} with {len(chunks)} chunks",
                "metadata": metadata
            }
            
        except Exception as e:
            # Update log with error
            log.status = "failed"
            log.error_message = str(e)
            log.completed_at = datetime.now().isoformat()
            session.commit()
            session.close()
            
            return {
                "document_id": document_id,
                "filename": filename,
                "success": False,
                "chunks_created": 0,
                "message": f"Failed to ingest {filename}: {str(e)}",
                "metadata": metadata
            }
        finally:
            session.close()
    
    def _parse_file(self, content: bytes, file_ext: str) -> str:
        """Parse file content based on type."""
        if file_ext == ".pdf":
            return self._parse_pdf(content)
        elif file_ext == ".docx":
            return self._parse_docx(content)
        elif file_ext in [".txt", ".text"]:
            return content.decode("utf-8", errors="ignore")
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    def _parse_pdf(self, content: bytes) -> str:
        """Extract text from PDF."""
        if not HAS_PYPDF:
            raise ImportError("PyPDF2 not installed. Run: pip install PyPDF2")
        
        import io
        text_parts = []
        
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        
        return "\n\n".join(text_parts)
    
    def _parse_docx(self, content: bytes) -> str:
        """Extract text from DOCX."""
        if not HAS_DOCX:
            raise ImportError("python-docx not installed. Run: pip install python-docx")
        
        import io
        doc = DocxDocument(io.BytesIO(content))
        
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        
        return "\n\n".join(text_parts)
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Chunk text into semantic units.
        
        Uses simple character-based chunking with overlap.
        For production, consider semantic chunking based on paragraphs/sections.
        """
        chunks = []
        
        # Clean text
        text = text.strip()
        if not text:
            return chunks
        
        # Simple chunking with overlap
        start = 0
        while start < len(text):
            end = start + self.CHUNK_SIZE
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end near chunk boundary
                for i in range(min(100, end - start)):
                    if text[end - i] in ".!?\n":
                        end = end - i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.CHUNK_OVERLAP
            if start < 0:
                break
        
        return chunks
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks."""
        # Delete from vector store
        chunks_deleted = self.vector_store.delete_document(document_id)
        
        # Delete from database
        session = get_db_session()
        doc = session.exec(
            select(DocumentRecord).where(DocumentRecord.document_id == document_id)
        ).first()
        
        if doc:
            session.delete(doc)
            session.commit()
        
        session.close()
        return chunks_deleted > 0
    
    def list_documents(
        self,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List ingested documents with optional filters."""
        from sqlmodel import select
        
        session = get_db_session()
        query = select(DocumentRecord)
        
        if supplier_id:
            query = query.where(DocumentRecord.supplier_id == supplier_id)
        if category_id:
            query = query.where(DocumentRecord.category_id == category_id)
        if document_type:
            query = query.where(DocumentRecord.document_type == document_type)
        
        results = session.exec(query).all()
        session.close()
        
        return [
            {
                "document_id": d.document_id,
                "filename": d.filename,
                "document_type": d.document_type,
                "supplier_id": d.supplier_id,
                "category_id": d.category_id,
                "chunk_count": d.chunk_count,
                "ingested_at": d.ingested_at
            }
            for d in results
        ]


# Import for delete_document
from sqlmodel import select


# Singleton instance
_ingester = None


def get_document_ingester() -> DocumentIngester:
    """Get or create document ingester singleton."""
    global _ingester
    if _ingester is None:
        _ingester = DocumentIngester()
    return _ingester






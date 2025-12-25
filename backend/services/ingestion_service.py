"""
Ingestion service for documents and structured data.
"""
from typing import Dict, Any, List, Optional

from backend.ingestion.document_ingest import get_document_ingester
from backend.ingestion.data_ingest import get_data_ingester
from shared.schemas import (
    DocumentIngestResponse, DataIngestResponse,
    DocumentListResponse, DocumentListItem,
    DataPreviewResponse
)


class IngestionService:
    """
    Service for document and data ingestion.
    
    Exposes ingestion functionality to the API layer.
    """
    
    def __init__(self):
        self.document_ingester = get_document_ingester()
        self.data_ingester = get_data_ingester()
    
    # ==================== DOCUMENT INGESTION ====================
    
    def ingest_document(
        self,
        file_content: bytes,
        filename: str,
        document_type: str,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        region: Optional[str] = None,
        dtp_relevance: Optional[List[str]] = None,
        case_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> DocumentIngestResponse:
        """Ingest a document into the RAG system."""
        metadata = {
            "document_type": document_type,
            "supplier_id": supplier_id,
            "category_id": category_id,
            "region": region,
            "dtp_relevance": dtp_relevance or [],
            "case_id": case_id,
            "description": description
        }
        
        result = self.document_ingester.ingest(
            file_content=file_content,
            filename=filename,
            metadata=metadata
        )
        
        return DocumentIngestResponse(
            document_id=result["document_id"],
            filename=result["filename"],
            success=result["success"],
            chunks_created=result["chunks_created"],
            message=result["message"],
            metadata=result.get("metadata", metadata)
        )
    
    def list_documents(
        self,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> DocumentListResponse:
        """List ingested documents."""
        docs = self.document_ingester.list_documents(
            supplier_id=supplier_id,
            category_id=category_id,
            document_type=document_type
        )
        
        items = [
            DocumentListItem(
                document_id=d["document_id"],
                filename=d["filename"],
                document_type=d["document_type"],
                supplier_id=d.get("supplier_id"),
                category_id=d.get("category_id"),
                ingested_at=d["ingested_at"],
                chunk_count=d["chunk_count"]
            )
            for d in docs
        ]
        
        return DocumentListResponse(
            documents=items,
            total_count=len(items)
        )
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document."""
        return self.document_ingester.delete_document(document_id)
    
    # ==================== STRUCTURED DATA INGESTION ====================
    
    def preview_data(
        self,
        file_content: bytes,
        filename: str,
        data_type: str
    ) -> DataPreviewResponse:
        """Preview data before ingestion."""
        result = self.data_ingester.preview(
            file_content=file_content,
            filename=filename,
            data_type=data_type
        )
        
        return DataPreviewResponse(
            columns=result["columns"],
            sample_rows=result["sample_rows"],
            total_rows=result["total_rows"],
            schema_valid=result["schema_valid"],
            validation_errors=result.get("validation_errors", [])
        )
    
    def ingest_data(
        self,
        file_content: bytes,
        filename: str,
        data_type: str,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        time_period: Optional[str] = None,
        description: Optional[str] = None
    ) -> DataIngestResponse:
        """Ingest structured data."""
        metadata = {
            "data_type": data_type,
            "supplier_id": supplier_id,
            "category_id": category_id,
            "time_period": time_period,
            "description": description
        }
        
        result = self.data_ingester.ingest(
            file_content=file_content,
            filename=filename,
            metadata=metadata
        )
        
        return DataIngestResponse(
            ingestion_id=result.get("ingestion_id", ""),
            filename=result["filename"],
            success=result["success"],
            rows_ingested=result["rows_ingested"],
            table_name=result["table_name"],
            message=result["message"],
            validation_warnings=result.get("validation_warnings", [])
        )
    
    def get_ingestion_history(
        self,
        data_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get ingestion history."""
        return self.data_ingester.get_ingestion_history(
            data_type=data_type,
            limit=limit
        )


# Singleton
_ingestion_service = None


def get_ingestion_service() -> IngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service




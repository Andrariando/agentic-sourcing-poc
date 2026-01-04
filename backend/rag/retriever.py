"""
Document retriever for agent-controlled RAG.
Implements filtered retrieval with governance checks.
"""
import json
from typing import List, Dict, Any, Optional
from backend.rag.vector_store import get_vector_store
from backend.persistence.database import get_db_session
from backend.persistence.models import DocumentRecord, SupplierPerformance, SpendMetric, SLAEvent
from sqlmodel import select


class DocumentRetriever:
    """
    Retriever for RAG with metadata filtering.
    
    Agents use this to retrieve documents with governance constraints:
    - Filter by supplier_id
    - Filter by category_id
    - Filter by DTP stage relevance
    - Filter by document type
    """
    
    def __init__(self):
        self.vector_store = get_vector_store()
    
    def retrieve_documents(
        self,
        query: str,
        case_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        dtp_stage: Optional[str] = None,
        document_types: Optional[List[str]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve relevant document chunks with filtering.
        
        This is the primary retrieval method for agents.
        All filters are optional but should be used for governance.
        
        Returns:
            Dict with:
            - chunks: List of chunk dicts with content and metadata
            - total_found: Total matching chunks
            - filters_applied: What filters were used
        """
        # Build metadata filter
        where = {}
        
        if supplier_id:
            where["supplier_id"] = supplier_id
        
        if category_id:
            where["category_id"] = category_id
        
        if document_types and len(document_types) == 1:
            where["document_type"] = document_types[0]
        
        # DTP stage filtering is more complex (stored as JSON string)
        # We'll filter post-retrieval for now
        
        # Execute search
        where_filter = where if where else None
        results = self.vector_store.search(
            query=query,
            n_results=top_k * 2,  # Get more, filter down
            where=where_filter
        )
        
        # Process results
        chunks = []
        if results and results.get("ids") and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                chunk_data = {
                    "chunk_id": chunk_id,
                    "content": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "score": 1.0 - (results["distances"][0][i] if results.get("distances") else 0)
                }
                
                # Apply DTP stage filter if specified
                if dtp_stage:
                    chunk_dtp = chunk_data["metadata"].get("dtp_relevance", "[]")
                    if isinstance(chunk_dtp, str):
                        try:
                            chunk_dtp = json.loads(chunk_dtp)
                        except:
                            chunk_dtp = []
                    
                    # Include if DTP stage matches or if no DTP specified for chunk
                    if chunk_dtp and dtp_stage not in chunk_dtp:
                        continue
                
                # Apply document type filter if multiple types
                if document_types and len(document_types) > 1:
                    doc_type = chunk_data["metadata"].get("document_type")
                    if doc_type and doc_type not in document_types:
                        continue
                
                chunks.append(chunk_data)
                
                if len(chunks) >= top_k:
                    break
        
        return {
            "query": query,
            "chunks": chunks,
            "total_found": len(chunks),
            "filters_applied": {
                "supplier_id": supplier_id,
                "category_id": category_id,
                "dtp_stage": dtp_stage,
                "document_types": document_types
            }
        }
    
    def get_supplier_performance(
        self,
        supplier_id: str,
        time_window: Optional[str] = None,
        category_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get supplier performance data from structured data store.
        
        Args:
            supplier_id: Supplier ID
            time_window: Optional time filter (e.g., "last_12_months")
            category_id: Optional category filter
            
        Returns:
            Dict with performance records and summary
        """
        session = get_db_session()
        
        query = select(SupplierPerformance).where(
            SupplierPerformance.supplier_id == supplier_id
        )
        
        if category_id:
            query = query.where(SupplierPerformance.category_id == category_id)
        
        # Order by date descending
        query = query.order_by(SupplierPerformance.measurement_date.desc())
        
        results = session.exec(query).all()
        session.close()
        
        records = []
        for r in results:
            records.append({
                "record_id": r.record_id,
                "supplier_id": r.supplier_id,
                "category_id": r.category_id,
                "overall_score": r.overall_score,
                "quality_score": r.quality_score,
                "delivery_score": r.delivery_score,
                "cost_variance": r.cost_variance,
                "trend": r.trend,
                "risk_level": r.risk_level,
                "measurement_date": r.measurement_date
            })
        
        # Build summary
        summary = None
        if records:
            latest = records[0]
            summary = {
                "latest_score": latest["overall_score"],
                "trend": latest["trend"],
                "risk_level": latest["risk_level"],
                "record_count": len(records)
            }
        
        return {
            "supplier_id": supplier_id,
            "data_type": "performance",
            "records": records,
            "summary": summary
        }
    
    def get_supplier_spend(
        self,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        time_window: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get spend data for supplier or category."""
        session = get_db_session()
        
        query = select(SpendMetric)
        
        if supplier_id:
            query = query.where(SpendMetric.supplier_id == supplier_id)
        
        if category_id:
            query = query.where(SpendMetric.category_id == category_id)
        
        results = session.exec(query).all()
        session.close()
        
        records = []
        total_spend = 0.0
        for r in results:
            records.append({
                "record_id": r.record_id,
                "supplier_id": r.supplier_id,
                "category_id": r.category_id,
                "contract_id": r.contract_id,
                "spend_amount": r.spend_amount,
                "currency": r.currency,
                "period": r.period
            })
            total_spend += r.spend_amount
        
        return {
            "supplier_id": supplier_id,
            "category_id": category_id,
            "data_type": "spend",
            "records": records,
            "summary": {
                "total_spend": total_spend,
                "record_count": len(records)
            }
        }
    
    def get_sla_events(
        self,
        supplier_id: str,
        severity: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get SLA events for a supplier."""
        session = get_db_session()
        
        query = select(SLAEvent).where(SLAEvent.supplier_id == supplier_id)
        
        if severity:
            query = query.where(SLAEvent.severity == severity)
        
        if status:
            query = query.where(SLAEvent.status == status)
        
        query = query.order_by(SLAEvent.event_date.desc())
        
        results = session.exec(query).all()
        session.close()
        
        records = []
        for r in results:
            records.append({
                "event_id": r.event_id,
                "supplier_id": r.supplier_id,
                "event_type": r.event_type,
                "sla_metric": r.sla_metric,
                "severity": r.severity,
                "status": r.status,
                "event_date": r.event_date
            })
        
        return {
            "supplier_id": supplier_id,
            "data_type": "sla_events",
            "records": records,
            "summary": {
                "total_events": len(records),
                "open_events": len([r for r in records if r["status"] == "open"]),
                "high_severity": len([r for r in records if r["severity"] in ["high", "critical"]])
            }
        }


# Singleton instance
_retriever = None


def get_retriever() -> DocumentRetriever:
    """Get or create retriever singleton."""
    global _retriever
    if _retriever is None:
        _retriever = DocumentRetriever()
    return _retriever






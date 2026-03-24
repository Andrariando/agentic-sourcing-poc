from datetime import datetime
from uuid import uuid4
from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import ReviewFeedback, AuditLog
from backend.heatmap.persistence.heatmap_vector_store import get_heatmap_vector_store


class FeedbackService:
    """
    Handles human-in-the-loop feedback for the Heatmap scoring system.
    Stores adjustments in SQLite and embeds written feedback into ChromaDB
    for the agentic learning loop.
    """
    
    def submit_feedback(self, opportunity_id: int, reviewer_id: str, 
                        adj_type: str, adj_val: float, reason: str, 
                        comment: str, component: str) -> bool:
        session = heatmap_db.get_db_session()
        
        try:
            # 1. Save structurally to SQLite
            feedback = ReviewFeedback(
                opportunity_id=opportunity_id,
                reviewer_id=reviewer_id,
                adjustment_type=adj_type,
                adjustment_value=adj_val,
                reason_code=reason,
                comment_text=comment,
                component_affected=component
            )
            session.add(feedback)
            
            audit = AuditLog(
                event_type="SCORE_OVERRIDE",
                entity_id=str(opportunity_id),
                user_id=reviewer_id,
                new_value=f"{component} {adj_type} {adj_val}"
            )
            session.add(audit)
            session.commit()
            
            # Refresh to get auto-generated ID
            session.refresh(feedback)
            
            # 2. Embed written feedback into Vector Store for AI Learning Memory
            if comment:
                vs = get_heatmap_vector_store()
                metadata = {
                    "opportunity_id": str(opportunity_id),
                    "reason_code": reason,
                    "reviewer_id": reviewer_id,
                    "component": component
                }
                chunk_text = (
                    f"Reviewer {reviewer_id} adjusted {component} by {adj_val} "
                    f"because: {comment}"
                )
                # Use a stable unique ID for the vector store document
                doc_id = f"feedback_{feedback.id or uuid4().hex}"
                vs.add_chunks([chunk_text], doc_id, metadata)
            
            return True
        finally:
            session.close()


def get_feedback_service() -> FeedbackService:
    return FeedbackService()

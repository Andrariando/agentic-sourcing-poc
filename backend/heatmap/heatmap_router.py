from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel import select

from backend.heatmap.services.feedback_service import get_feedback_service
from backend.heatmap.services.case_bridge import get_case_bridge_service
from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import Opportunity

heatmap_router = APIRouter()

class FeedbackRequest(BaseModel):
    opportunity_id: int
    reviewer_id: str
    adjustment_type: str
    adjustment_value: float
    reason_code: str
    comment_text: str = ""
    component_affected: str

class ApprovalRequest(BaseModel):
    opportunity_ids: List[int]
    approver_id: str

@heatmap_router.get("/opportunities")
def list_opportunities():
    session = heatmap_db.get_db_session()
    try:
        statement = select(Opportunity)
        results = session.exec(statement).all()
        return {"opportunities": [opt.model_dump() for opt in results]}
    finally:
        session.close()

@heatmap_router.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    svc = get_feedback_service()
    success = svc.submit_feedback(
        req.opportunity_id, req.reviewer_id, 
        req.adjustment_type, req.adjustment_value, 
        req.reason_code, req.comment_text, req.component_affected
    )
    return {"success": success}

@heatmap_router.post("/approve")
def approve_opportunities(req: ApprovalRequest):
    svc = get_case_bridge_service()
    count = svc.approve_opportunities(req.opportunity_ids, req.approver_id)
    return {"success": True, "approved_count": count}

@heatmap_router.post("/run")
def run_pipeline():
    # In a real impl, this triggers the LangGraph via asyncio.create_task or similar
    # For now, it's just a placeholder to show the API structure.
    return {"success": True, "message": "Scoring pipeline triggered asynchronously."}

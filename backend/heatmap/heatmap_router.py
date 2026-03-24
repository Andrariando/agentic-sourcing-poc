from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel import select
import threading
import time

from backend.heatmap.services.feedback_service import get_feedback_service
from backend.heatmap.services.case_bridge import get_case_bridge_service
from backend.heatmap.run_pipeline_init import run_init
from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import Opportunity

heatmap_router = APIRouter()
_pipeline_lock = threading.Lock()
_pipeline_status = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_success": None,
    "last_error": None,
    "opportunity_count": None,
}

class FeedbackRequest(BaseModel):
    opportunity_id: int
    reviewer_id: Optional[str] = None
    adjustment_type: Optional[str] = None
    adjustment_value: Optional[float] = None
    reason_code: Optional[str] = None
    comment_text: str = ""
    component_affected: Optional[str] = None
    # Backward compatibility for current Next.js payload
    user_id: Optional[str] = None
    original_tier: Optional[str] = None
    suggested_tier: Optional[str] = None
    feedback_notes: Optional[str] = None

class ApprovalRequest(BaseModel):
    opportunity_ids: List[int]
    approver_id: str


class ApproveOpportunitiesResponse(BaseModel):
    success: bool
    approved_count: int
    cases: dict[str, str]

class PipelineStatusResponse(BaseModel):
    running: bool
    last_started_at: Optional[float] = None
    last_finished_at: Optional[float] = None
    last_success: Optional[bool] = None
    last_error: Optional[str] = None
    opportunity_count: Optional[int] = None

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
    reviewer_id = req.reviewer_id or req.user_id or "human-reviewer"
    comment_text = req.comment_text or req.feedback_notes or ""
    component_affected = req.component_affected or "tier"
    reason_code = req.reason_code or "HUMAN_OVERRIDE"
    adjustment_type = req.adjustment_type
    adjustment_value = req.adjustment_value

    # Translate legacy UI payload (tier override) to structured feedback format
    if req.suggested_tier:
        adjustment_type = adjustment_type or "override"
        tier_to_score = {"T1": 1.0, "T2": 2.0, "T3": 3.0, "T4": 4.0}
        adjustment_value = adjustment_value if adjustment_value is not None else tier_to_score.get(req.suggested_tier, 4.0)
        component_affected = "tier"
        reason_code = reason_code or f"TIER_OVERRIDE_{req.original_tier or 'UNKNOWN'}_TO_{req.suggested_tier}"

    if adjustment_type is None:
        adjustment_type = "override"
    if adjustment_value is None:
        adjustment_value = 0.0

    svc = get_feedback_service()
    success = svc.submit_feedback(
        req.opportunity_id,
        reviewer_id,
        adjustment_type,
        adjustment_value,
        reason_code,
        comment_text,
        component_affected,
    )
    return {"success": success}

@heatmap_router.post("/approve", response_model=ApproveOpportunitiesResponse)
def approve_opportunities(req: ApprovalRequest):
    svc = get_case_bridge_service()
    count, case_map = svc.approve_opportunities(req.opportunity_ids, req.approver_id)
    # JSON object keys must be strings
    cases_str = {str(k): v for k, v in case_map.items()}
    return ApproveOpportunitiesResponse(
        success=True, approved_count=count, cases=cases_str
    )

@heatmap_router.post("/run")
def run_pipeline():
    # Lightweight mode for low-memory hosts (e.g. Render 512MB):
    # run scoring in background and return immediately.
    if _pipeline_status["running"]:
        return {
            "success": True,
            "queued": False,
            "running": True,
            "message": "Pipeline already running. Reuse current job.",
        }

    started = _pipeline_lock.acquire(blocking=False)
    if not started:
        return {
            "success": True,
            "queued": False,
            "running": True,
            "message": "Pipeline lock busy. Reuse current job.",
        }

    def _run_job():
        try:
            _pipeline_status["running"] = True
            _pipeline_status["last_started_at"] = time.time()
            _pipeline_status["last_error"] = None
            run_init()

            session = heatmap_db.get_db_session()
            try:
                _pipeline_status["opportunity_count"] = len(session.exec(select(Opportunity)).all())
            finally:
                session.close()

            _pipeline_status["last_success"] = True
        except Exception as e:
            _pipeline_status["last_success"] = False
            _pipeline_status["last_error"] = str(e)
        finally:
            _pipeline_status["running"] = False
            _pipeline_status["last_finished_at"] = time.time()
            _pipeline_lock.release()

    threading.Thread(target=_run_job, daemon=True).start()
    return {
        "success": True,
        "queued": True,
        "running": True,
        "message": "Scoring pipeline started in background.",
    }

@heatmap_router.get("/run/status", response_model=PipelineStatusResponse)
def run_pipeline_status():
    return PipelineStatusResponse(**_pipeline_status)

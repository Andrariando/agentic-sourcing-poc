from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from sqlmodel import select, func
import json
import threading
import time
from uuid import uuid4

from backend.heatmap.services.feedback_service import get_feedback_service
from backend.heatmap.services.case_bridge import get_case_bridge_service
from backend.heatmap.run_pipeline_init import run_init
from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import (
    Opportunity,
    ReviewFeedback,
    AuditLog,
    HeatmapCopilotFeedback,
)
from backend.heatmap.context_builder import (
    load_category_cards,
    category_cards_fingerprint,
    iter_category_card_names,
)
from backend.heatmap.services.opportunity_enrichment import enrich_opportunity_dict
from backend.heatmap.services.intake_scoring import score_intake_payload, persist_intake_opportunity
from backend.heatmap.services.heatmap_copilot import (
    answer_heatmap_question,
    assist_category_card_edit,
    assist_category_card_from_unstructured,
    check_feedback_vs_policy,
)
from backend.heatmap.services.category_cards_store import apply_category_cards_patch

heatmap_router = APIRouter()
_pipeline_lock = threading.Lock()
_pipeline_status = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_success": None,
    "last_error": None,
    "opportunity_count": None,
    "last_duration_sec": None,
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
    # Optional: absolute weight edits (normalized server-side per PS_new / PS_contract group)
    scoring_weight_overrides: Optional[Dict[str, float]] = None
    weight_adjustments: Optional[Dict[str, float]] = None


class ScoringWeightsResponse(BaseModel):
    weights: Dict[str, float]
    defaults: Dict[str, float]


class ScoringWeightsUpdateRequest(BaseModel):
    weights: Optional[Dict[str, float]] = None
    deltas: Optional[Dict[str, float]] = None


class FeedbackHistoryItem(BaseModel):
    id: int
    reviewer_id: str
    timestamp: datetime
    adjustment_type: str
    adjustment_value: float
    reason_code: str
    comment_text: Optional[str]
    component_affected: str


class ApprovalRequest(BaseModel):
    opportunity_ids: List[int]
    approver_id: str


class ApproveOpportunitiesResponse(BaseModel):
    success: bool
    approved_count: int
    cases: dict[str, str]
    already_linked: dict[str, bool] = Field(default_factory=dict)

class PipelineStatusResponse(BaseModel):
    running: bool
    last_started_at: Optional[float] = None
    last_finished_at: Optional[float] = None
    last_success: Optional[bool] = None
    last_error: Optional[str] = None
    opportunity_count: Optional[int] = None
    last_duration_sec: Optional[float] = None


def _empty_str_to_none(v: Any) -> Any:
    if v == "":
        return None
    return v


class IntakeScoreFields(BaseModel):
    category: str = Field(min_length=1)
    subcategory: Optional[str] = None
    supplier_name: Optional[str] = None
    estimated_spend_usd: float = Field(ge=0)
    implementation_timeline_months: float = Field(gt=0, le=120)
    preferred_supplier_status: Optional[str] = None

    @field_validator("subcategory", "supplier_name", "preferred_supplier_status", mode="before")
    @classmethod
    def _coerce_optional(cls, v: Any) -> Any:
        return _empty_str_to_none(v)


class IntakePreviewRequest(IntakeScoreFields):
    pass


class IntakePreviewResponse(BaseModel):
    meta: Dict[str, Any]
    scores: Dict[str, Optional[float]]
    total_score: float
    tier: str
    justification: str


class IntakeSubmitRequest(IntakeScoreFields):
    request_title: Optional[str] = None
    justification_summary_text: Optional[str] = None

    @field_validator("request_title", "justification_summary_text", mode="before")
    @classmethod
    def _coerce_submit_optional(cls, v: Any) -> Any:
        return _empty_str_to_none(v)


class IntakeSubmitResponse(BaseModel):
    success: bool
    opportunity: Dict[str, Any]


class HeatmapQARequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)


class HeatmapQAResponse(BaseModel):
    answer: str
    used_llm: bool
    response_id: str


class HeatmapQAFeedbackRequest(BaseModel):
    response_id: str = Field(min_length=6, max_length=80)
    question: str = Field(min_length=3, max_length=4000)
    answer: str = Field(min_length=3, max_length=20000)
    vote: str = Field(pattern="^(up|down)$")
    user_id: str = Field(default="human-user", min_length=1, max_length=80)


class HeatmapQAFeedbackResponse(BaseModel):
    success: bool
    feedback_id: int


class PolicyCheckRequest(BaseModel):
    feedback_text: str = Field(min_length=5, max_length=8000)
    category: str = Field(min_length=1)
    supplier_name: Optional[str] = None
    current_tier: Optional[str] = None


class CategoryCardsAssistRequest(BaseModel):
    category: str = Field(min_length=1)
    instruction: str = Field(min_length=10, max_length=4000)


class CategoryCardsUnstructuredRequest(BaseModel):
    category: str = Field(min_length=1)
    raw_text: str = Field(min_length=20, max_length=50000)


class CategoryCardsApplyRequest(BaseModel):
    category: str = Field(min_length=1)
    proposed_patch: Dict[str, Any] = Field(default_factory=dict)


def _start_heatmap_pipeline_background() -> Dict[str, Any]:
    """Start batch scoring in a background thread; same behavior as POST /run."""
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
        t0 = time.time()
        try:
            _pipeline_status["running"] = True
            _pipeline_status["last_started_at"] = t0
            _pipeline_status["last_error"] = None
            run_init()

            session = heatmap_db.get_db_session()
            try:
                n = len(session.exec(select(Opportunity)).all())
                _pipeline_status["opportunity_count"] = n
                dur = time.time() - t0
                _pipeline_status["last_duration_sec"] = round(dur, 3)
            finally:
                session.close()

            _pipeline_status["last_success"] = True
        except Exception as e:
            _pipeline_status["last_success"] = False
            _pipeline_status["last_error"] = str(e)
            try:
                session = heatmap_db.get_db_session()
                try:
                    dur = time.time() - t0
                    audit = AuditLog(
                        event_type="HEATMAP_PIPELINE_RUN",
                        entity_id="batch",
                        new_value=json.dumps(
                            {
                                "duration_sec": round(dur, 3),
                                "opportunity_count": _pipeline_status.get("opportunity_count"),
                                "success": False,
                                "error": str(e),
                                "finished_at": time.time(),
                            }
                        ),
                        user_id="pipeline",
                    )
                    session.add(audit)
                    session.commit()
                finally:
                    session.close()
            except Exception:
                pass
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


@heatmap_router.post("/qa", response_model=HeatmapQAResponse)
def heatmap_qa(req: HeatmapQARequest):
    session = heatmap_db.get_db_session()
    try:
        answer, used_llm = answer_heatmap_question(session, req.question.strip())
        return HeatmapQAResponse(
            answer=answer,
            used_llm=used_llm,
            response_id=uuid4().hex,
        )
    finally:
        session.close()


@heatmap_router.post("/qa/feedback", response_model=HeatmapQAFeedbackResponse)
def heatmap_qa_feedback(req: HeatmapQAFeedbackRequest):
    session = heatmap_db.get_db_session()
    try:
        row = HeatmapCopilotFeedback(
            response_id=req.response_id.strip(),
            question=req.question.strip(),
            answer=req.answer.strip(),
            vote=req.vote.strip(),
            user_id=req.user_id.strip() or "human-user",
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return HeatmapQAFeedbackResponse(success=True, feedback_id=int(row.id or 0))
    finally:
        session.close()


@heatmap_router.post("/policy/check")
def heatmap_policy_check(req: PolicyCheckRequest):
    result, used_llm = check_feedback_vs_policy(
        feedback_text=req.feedback_text.strip(),
        category=req.category.strip(),
        supplier_name=req.supplier_name.strip() if req.supplier_name else None,
        current_tier=req.current_tier.strip() if req.current_tier else None,
    )
    return {"used_llm": used_llm, **result}


@heatmap_router.post("/category-cards/assist")
def heatmap_category_cards_assist(req: CategoryCardsAssistRequest):
    payload, used_llm = assist_category_card_edit(
        category=req.category.strip(),
        instruction=req.instruction.strip(),
    )
    return {"used_llm": used_llm, **payload}


@heatmap_router.post("/category-cards/extract")
def heatmap_category_cards_extract(req: CategoryCardsUnstructuredRequest):
    payload, used_llm = assist_category_card_from_unstructured(
        category=req.category.strip(),
        raw_text=req.raw_text.strip(),
    )
    return {"used_llm": used_llm, **payload}


_MAX_UPLOAD_BYTES = 500_000


@heatmap_router.post("/category-cards/extract-upload")
async def heatmap_category_cards_extract_upload(
    category: str = Form(...),
    file: UploadFile = File(...),
):
    """Read uploaded text file and run the same unstructured extract as /category-cards/extract."""
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500KB).")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    payload, used_llm = assist_category_card_from_unstructured(
        category=category.strip(),
        raw_text=text,
    )
    return {"used_llm": used_llm, **payload, "filename": file.filename or "upload"}


@heatmap_router.post("/category-cards/apply")
def heatmap_category_cards_apply(req: CategoryCardsApplyRequest):
    """Merge proposed_patch into data/heatmap/category_cards.json (human-approved demo step)."""
    try:
        result = apply_category_cards_patch(req.category.strip(), req.proposed_patch)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@heatmap_router.post("/category-cards/apply-and-rerun")
def heatmap_category_cards_apply_and_rerun(req: CategoryCardsApplyRequest):
    """Apply patch to category_cards.json, then start batch pipeline so opportunity scores refresh."""
    try:
        apply_result = apply_category_cards_patch(req.category.strip(), req.proposed_patch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    pipeline = _start_heatmap_pipeline_background()
    return {**apply_result, "pipeline": pipeline}


@heatmap_router.get("/intake/categories")
def intake_categories():
    cards = load_category_cards()
    return {
        "categories": iter_category_card_names(cards),
        "category_cards_meta": category_cards_fingerprint(),
    }


@heatmap_router.post("/intake/preview", response_model=IntakePreviewResponse)
def intake_preview(req: IntakePreviewRequest):
    session = heatmap_db.get_db_session()
    try:
        meta, scores, total_r, tier, justification = score_intake_payload(
            session,
            category=req.category.strip(),
            subcategory=req.subcategory,
            supplier_name=req.supplier_name,
            estimated_spend_usd=req.estimated_spend_usd,
            implementation_timeline_months=req.implementation_timeline_months,
            preferred_supplier_status=req.preferred_supplier_status,
        )
        return IntakePreviewResponse(
            meta=meta,
            scores=scores,
            total_score=total_r,
            tier=tier,
            justification=justification,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        session.close()


@heatmap_router.post("/intake", response_model=IntakeSubmitResponse)
def intake_submit(req: IntakeSubmitRequest):
    session = heatmap_db.get_db_session()
    try:
        opp = persist_intake_opportunity(
            session,
            request_title=req.request_title,
            category=req.category.strip(),
            subcategory=req.subcategory,
            supplier_name=req.supplier_name,
            estimated_spend_usd=req.estimated_spend_usd,
            implementation_timeline_months=req.implementation_timeline_months,
            preferred_supplier_status=req.preferred_supplier_status,
            justification_summary_text=req.justification_summary_text,
        )
        return IntakeSubmitResponse(success=True, opportunity=opp.model_dump())
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        session.close()


def _feedback_counts_by_opportunity(session) -> Dict[int, int]:
    rows = session.exec(
        select(ReviewFeedback.opportunity_id, func.count(ReviewFeedback.id)).group_by(
            ReviewFeedback.opportunity_id
        )
    ).all()
    return {int(r[0]): int(r[1]) for r in rows}


def _last_pipeline_audit_payload(session) -> Optional[Dict[str, Any]]:
    row = session.exec(
        select(AuditLog)
        .where(AuditLog.event_type == "HEATMAP_PIPELINE_RUN")
        .order_by(AuditLog.timestamp.desc())
    ).first()
    if not row or not row.new_value:
        return None
    try:
        return json.loads(row.new_value)
    except json.JSONDecodeError:
        return None


@heatmap_router.get("/opportunities")
def list_opportunities(
    enrich: bool = Query(
        True,
        description="Include data_quality_warnings and kli_metrics (feedback-derived).",
    ),
):
    session = heatmap_db.get_db_session()
    try:
        statement = select(Opportunity)
        results = session.exec(statement).all()
        cards = load_category_cards()
        cat_keys = iter_category_card_names(cards)
        fb_counts = _feedback_counts_by_opportunity(session) if enrich else {}
        pipe = _last_pipeline_audit_payload(session) or {}
        pipeline_meta = {
            "duration_sec": pipe.get("duration_sec"),
            "opportunity_count": pipe.get("opportunity_count"),
            "agents_run": pipe.get("agents_run", 5),
        }
        if _pipeline_status.get("last_duration_sec") is not None:
            pipeline_meta["duration_sec"] = _pipeline_status["last_duration_sec"]
        if _pipeline_status.get("opportunity_count") is not None:
            pipeline_meta["opportunity_count"] = _pipeline_status["opportunity_count"]

        out: List[Dict[str, Any]] = []
        for opt in results:
            d = opt.model_dump(mode="json")
            if enrich:
                oid = int(opt.id) if opt.id is not None else 0
                d = enrich_opportunity_dict(
                    d,
                    fb_counts.get(oid, 0),
                    cat_keys,
                    pipeline_meta,
                )
            out.append(d)
        return {"opportunities": out}
    finally:
        session.close()


@heatmap_router.get("/metrics/dashboard")
def heatmap_dashboard_metrics():
    """Aggregates for heatmap KPI rollups (feedback + pipeline audit + tier counts)."""
    session = heatmap_db.get_db_session()
    try:
        opps = session.exec(select(Opportunity)).all()
        fb_raw = session.exec(select(func.count(ReviewFeedback.id))).one()
        fb_total = int(fb_raw[0] if isinstance(fb_raw, (tuple, list)) else fb_raw)
        tier_counts: Dict[str, int] = {}
        pending = 0
        approved = 0
        ages: List[float] = []
        for o in opps:
            tier_counts[o.tier] = tier_counts.get(o.tier, 0) + 1
            if o.status == "Pending":
                pending += 1
            elif o.status == "Approved":
                approved += 1
            if o.record_created_at and o.status == "Pending":
                t = o.record_created_at
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                ages.append((datetime.now(timezone.utc) - t).total_seconds() / 86400.0)

        median_age = None
        if ages:
            s = sorted(ages)
            mid = len(s) // 2
            median_age = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0

        pipe = _last_pipeline_audit_payload(session)
        last_pipe = None
        if pipe:
            last_pipe = {
                "duration_sec": pipe.get("duration_sec"),
                "opportunity_count": pipe.get("opportunity_count"),
                "success": pipe.get("success"),
                "finished_at": pipe.get("finished_at"),
            }
        if _pipeline_status.get("last_finished_at"):
            last_pipe = last_pipe or {}
            last_pipe["finished_at_epoch"] = _pipeline_status["last_finished_at"]
            last_pipe["running"] = _pipeline_status.get("running")
            last_pipe["last_success"] = _pipeline_status.get("last_success")

        qa_vote_rows = session.exec(
            select(
                HeatmapCopilotFeedback.vote,
                func.count(HeatmapCopilotFeedback.id),
            ).group_by(HeatmapCopilotFeedback.vote)
        ).all()
        qa_vote_counts: Dict[str, int] = {}
        for vote, n in qa_vote_rows:
            qa_vote_counts[str(vote)] = int(n)
        qa_total = int(sum(qa_vote_counts.values()))
        qa_up = int(qa_vote_counts.get("up", 0))
        qa_signal_attr_accuracy = (qa_up / qa_total * 100.0) if qa_total else None

        n_opp = len(opps)
        avg_fb = (fb_total / n_opp) if n_opp else 0.0

        return {
            "opportunities_total": n_opp,
            "feedback_rows_total": fb_total,
            "pending_count": pending,
            "approved_count": approved,
            "tier_counts": tier_counts,
            "median_pending_age_days": round(median_age, 2) if median_age is not None else None,
            "feedback_per_opportunity_avg": round(avg_fb, 3),
            "last_pipeline": last_pipe,
            "pipeline_status": dict(_pipeline_status),
            "copilot_feedback": {
                "thumbs_up": qa_up,
                "thumbs_down": int(qa_vote_counts.get("down", 0)),
                "thumbs_total": qa_total,
                "signal_attribution_accuracy_pct": (
                    round(qa_signal_attr_accuracy, 2)
                    if qa_signal_attr_accuracy is not None
                    else None
                ),
            },
        }
    finally:
        session.close()


@heatmap_router.get("/feedback/history", response_model=List[FeedbackHistoryItem])
def heatmap_feedback_history(
    opportunity_id: int = Query(..., description="Opportunity id to fetch feedback for"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of feedback rows to return"),
):
    """
    Per-opportunity feedback history for the heatmap review modal.
    Returned in reverse chronological order (most recent first).
    """
    session = heatmap_db.get_db_session()
    try:
        stmt = (
            select(ReviewFeedback)
            .where(ReviewFeedback.opportunity_id == opportunity_id)
            .order_by(ReviewFeedback.timestamp.desc())
            .limit(limit)
        )
        rows = session.exec(stmt).all()
        out: List[FeedbackHistoryItem] = []
        for r in rows:
            out.append(
                FeedbackHistoryItem(
                    id=int(r.id),  # type: ignore[arg-type]
                    reviewer_id=r.reviewer_id,
                    timestamp=r.timestamp,
                    adjustment_type=r.adjustment_type,
                    adjustment_value=float(r.adjustment_value),
                    reason_code=r.reason_code,
                    comment_text=r.comment_text,
                    component_affected=r.component_affected,
                )
            )
        return out
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
    success, opp_snap = svc.submit_feedback(
        req.opportunity_id,
        reviewer_id,
        adjustment_type,
        adjustment_value,
        reason_code,
        comment_text,
        component_affected,
        suggested_tier=req.suggested_tier,
        weight_adjustments=req.weight_adjustments,
        scoring_weight_overrides=req.scoring_weight_overrides,
        tier_before=req.original_tier,
    )
    return {"success": success, "opportunity": opp_snap}


@heatmap_router.get("/scoring-weights", response_model=ScoringWeightsResponse)
def heatmap_scoring_weights_get():
    from backend.heatmap.services.learned_weights import (
        DEFAULT_WEIGHTS_FLAT,
        load_learned_weights,
        normalize_full,
    )

    session = heatmap_db.get_db_session()
    try:
        w = normalize_full(load_learned_weights(session))
        return ScoringWeightsResponse(weights=w, defaults=dict(DEFAULT_WEIGHTS_FLAT))
    finally:
        session.close()


@heatmap_router.put("/scoring-weights", response_model=ScoringWeightsResponse)
def heatmap_scoring_weights_put(req: ScoringWeightsUpdateRequest):
    from backend.heatmap.services.learned_weights import (
        DEFAULT_WEIGHTS_FLAT,
        load_learned_weights,
        merge_weight_edits,
        normalize_full,
        save_learned_weights,
    )

    session = heatmap_db.get_db_session()
    try:
        if req.weights is None and req.deltas is None:
            w = normalize_full(load_learned_weights(session))
            return ScoringWeightsResponse(weights=w, defaults=dict(DEFAULT_WEIGHTS_FLAT))
        if req.weights is not None:
            merged = normalize_full(req.weights)
        else:
            base = load_learned_weights(session)
            merged = merge_weight_edits(base, None, req.deltas)
        save_learned_weights(session, merged)
        session.commit()
        w = normalize_full(load_learned_weights(session))
        return ScoringWeightsResponse(weights=w, defaults=dict(DEFAULT_WEIGHTS_FLAT))
    finally:
        session.close()

@heatmap_router.post("/approve", response_model=ApproveOpportunitiesResponse)
def approve_opportunities(req: ApprovalRequest):
    svc = get_case_bridge_service()
    count, case_map, linked_flags = svc.approve_opportunities(req.opportunity_ids, req.approver_id)
    # JSON object keys must be strings
    cases_str = {str(k): v for k, v in case_map.items()}
    linked_str = {str(k): v for k, v in linked_flags.items()}
    return ApproveOpportunitiesResponse(
        success=True, approved_count=count, cases=cases_str, already_linked=linked_str
    )

@heatmap_router.post("/run")
def run_pipeline():
    # Lightweight mode for low-memory hosts (e.g. Render 512MB):
    # run scoring in background and return immediately.
    return _start_heatmap_pipeline_background()

@heatmap_router.get("/run/status", response_model=PipelineStatusResponse)
def run_pipeline_status():
    return PipelineStatusResponse(**_pipeline_status)

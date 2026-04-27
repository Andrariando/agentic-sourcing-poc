from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from sqlmodel import select, func
import json
import threading
import time
from uuid import uuid4
from pathlib import Path

from backend.heatmap.services.feedback_service import get_feedback_service
from backend.heatmap.services.case_bridge import get_case_bridge_service
from backend.heatmap.run_pipeline_init import run_init
from backend.infrastructure.storage_providers import get_heatmap_db
from backend.heatmap.persistence.heatmap_models import (
    Opportunity,
    ReviewFeedback,
    AuditLog,
    HeatmapProcuraBotFeedback,
    ScoringConfigVersion,
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
from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay
from backend.heatmap.scoring_framework import eus_from_months_to_expiry, ius_from_implementation_months
from backend.heatmap.services.learned_weights import load_learned_weights, normalize_full, recompute_total_and_tier
from backend.heatmap.services.scoring_config_registry import (
    ensure_default_scoring_config,
    extract_weight_overrides,
    parse_config_json,
    validate_scoring_config,
)

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

heatmap_db = get_heatmap_db()

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


class ScoringConfigVersionOut(BaseModel):
    id: int
    version: int
    status: str
    title: str
    config: Dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class ScoringConfigDraftRequest(BaseModel):
    title: str = Field(default="Scoring Config Draft", min_length=3, max_length=140)
    config: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default="human-manager", min_length=1, max_length=80)


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


class OpportunityDispositionUpdateRequest(BaseModel):
    opportunity_id: int
    disposition: str = Field(
        pattern="^(renewal_candidate|not_pursuing|supplier_exit_planned|deferred|new_request)$"
    )
    not_pursue_reason_code: Optional[str] = None
    comment_text: Optional[str] = ""
    updated_by: str = "human-manager"


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
        response_id = req.response_id.strip()
        user_id = req.user_id.strip() or "human-user"
        existing = session.exec(
            select(HeatmapProcuraBotFeedback)
            .where(HeatmapProcuraBotFeedback.response_id == response_id)
            .where(HeatmapProcuraBotFeedback.user_id == user_id)
        ).first()
        if existing:
            existing.question = req.question.strip()
            existing.answer = req.answer.strip()
            existing.vote = req.vote.strip()
            row = existing
        else:
            row = HeatmapProcuraBotFeedback(
                response_id=response_id,
                question=req.question.strip(),
                answer=req.answer.strip(),
                vote=req.vote.strip(),
                user_id=user_id,
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
    """Read uploaded file (.txt / .md / .docx) and run the same unstructured extract as /category-cards/extract."""
    from backend.heatmap.services.upload_plain_text import upload_bytes_to_plain_text

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500KB).")
    try:
        text = upload_bytes_to_plain_text(raw, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    payload, used_llm = assist_category_card_from_unstructured(
        category=category.strip(),
        raw_text=text,
    )
    return {
        "used_llm": used_llm,
        **payload,
        "filename": file.filename or "upload",
        "source_format": Path(file.filename or "").suffix.lower() or ".txt",
    }


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


def _safe_json_loads(raw: Any, fallback: Any):
    if raw is None:
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except Exception:
        return fallback


def _months_until(dt: Optional[datetime], now: datetime) -> Optional[float]:
    if dt is None:
        return None
    t = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return max(0.0, (t - now).total_seconds() / (86400.0 * 30.4375))


def _refresh_time_dependent_scores(session, opps: List[Opportunity]) -> None:
    if not opps:
        return
    cards = load_category_cards()
    global_weights = normalize_full(load_learned_weights(session))
    now = datetime.now(timezone.utc)
    changed = False
    for o in opps:
        is_new = o.contract_id is None
        if is_new:
            if o.implementation_timeline_months is None or o.record_created_at is None:
                continue
            created = (
                o.record_created_at
                if o.record_created_at.tzinfo is not None
                else o.record_created_at.replace(tzinfo=timezone.utc)
            )
            elapsed_months = max(0.0, (now - created).total_seconds() / (86400.0 * 30.4375))
            remaining = max(0.0, float(o.implementation_timeline_months) - elapsed_months)
            new_ius = round(float(ius_from_implementation_months(remaining)), 2)
            if abs(float(o.ius_score or 0.0) - new_ius) >= 0.01:
                o.ius_score = new_ius
                changed = True
        else:
            months = _months_until(o.contract_end_date, now)
            if months is None:
                continue
            new_eus = round(float(eus_from_months_to_expiry(months)), 2)
            if abs(float(o.eus_score or 0.0) - new_eus) >= 0.01:
                o.eus_score = new_eus
                changed = True

        raw_c = cards.get((o.category or "").strip()) or cards.get(o.category or "")
        ccard = raw_c if isinstance(raw_c, dict) else {}
        w_effective = apply_category_scoring_overlay(global_weights, ccard)
        new_total, new_tier = recompute_total_and_tier(o, w_effective)
        if abs(float(o.total_score or 0.0) - float(new_total)) >= 0.01:
            o.total_score = float(new_total)
            changed = True
        if str(o.tier or "") != str(new_tier):
            o.tier = new_tier
            changed = True
        session.add(o)
    if changed:
        session.commit()


@heatmap_router.get("/opportunities")
def list_opportunities(
    enrich: bool = Query(
        True,
        description="Include data_quality_warnings and kli_metrics (feedback-derived).",
    ),
    include_not_pursuing: bool = Query(
        True,
        description="When false, excludes opportunities marked not_pursuing/supplier_exit_planned.",
    ),
):
    session = heatmap_db.get_db_session()
    try:
        statement = select(Opportunity)
        if not include_not_pursuing:
            statement = statement.where(
                Opportunity.disposition.not_in(["not_pursuing", "supplier_exit_planned"])
            )
        results = session.exec(statement).all()
        _refresh_time_dependent_scores(session, results)
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
            provenance = _safe_json_loads(d.get("score_provenance_json"), {})
            warnings = _safe_json_loads(d.get("system1_warnings_json"), [])
            is_new_request = not bool(d.get("contract_id"))
            d["opportunity_type"] = "new_business" if is_new_request else "renewal"
            d["score_provenance"] = provenance if isinstance(provenance, dict) else {}
            d["supporting_artifacts"] = (
                d["score_provenance"].get("supporting_artifacts", [])
                if isinstance(d["score_provenance"], dict)
                else []
            )
            d["system1_warnings"] = warnings if isinstance(warnings, list) else []
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
                HeatmapProcuraBotFeedback.vote,
                func.count(HeatmapProcuraBotFeedback.id),
            ).group_by(HeatmapProcuraBotFeedback.vote)
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


def _serialize_scoring_config_row(row: ScoringConfigVersion) -> ScoringConfigVersionOut:
    payload = parse_config_json(row.config_json)
    return ScoringConfigVersionOut(
        id=int(row.id or 0),
        version=int(row.version),
        status=str(row.status),
        title=str(row.title),
        config=payload,
        created_by=str(row.created_by),
        created_at=row.created_at,
        updated_at=row.updated_at,
        published_at=row.published_at,
    )


@heatmap_router.get("/scoring-config/active", response_model=ScoringConfigVersionOut)
def heatmap_scoring_config_active():
    session = heatmap_db.get_db_session()
    try:
        row = ensure_default_scoring_config(session)
        return _serialize_scoring_config_row(row)
    finally:
        session.close()


@heatmap_router.get("/scoring-config/versions", response_model=List[ScoringConfigVersionOut])
def heatmap_scoring_config_versions():
    session = heatmap_db.get_db_session()
    try:
        ensure_default_scoring_config(session)
        rows = session.exec(
            select(ScoringConfigVersion).order_by(ScoringConfigVersion.version.desc(), ScoringConfigVersion.id.desc())
        ).all()
        return [_serialize_scoring_config_row(r) for r in rows]
    finally:
        session.close()


@heatmap_router.post("/scoring-config/draft", response_model=ScoringConfigVersionOut)
def heatmap_scoring_config_create_draft(req: ScoringConfigDraftRequest):
    ok, errors = validate_scoring_config(req.config)
    if not ok:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    session = heatmap_db.get_db_session()
    try:
        ensure_default_scoring_config(session)
        latest = session.exec(select(func.max(ScoringConfigVersion.version))).one()
        max_version = int((latest[0] if isinstance(latest, (tuple, list)) else latest) or 1)
        now = datetime.now(timezone.utc)
        row = ScoringConfigVersion(
            version=max_version + 1,
            status="draft",
            title=req.title,
            config_json=json.dumps(req.config),
            created_by=req.created_by,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _serialize_scoring_config_row(row)
    finally:
        session.close()


@heatmap_router.put("/scoring-config/draft/{config_id}", response_model=ScoringConfigVersionOut)
def heatmap_scoring_config_update_draft(config_id: int, req: ScoringConfigDraftRequest):
    ok, errors = validate_scoring_config(req.config)
    if not ok:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    session = heatmap_db.get_db_session()
    try:
        row = session.get(ScoringConfigVersion, config_id)
        if not row:
            raise HTTPException(status_code=404, detail="Scoring config draft not found")
        if row.status != "draft":
            raise HTTPException(status_code=400, detail="Only draft versions can be edited")
        row.title = req.title
        row.config_json = json.dumps(req.config)
        row.created_by = req.created_by
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _serialize_scoring_config_row(row)
    finally:
        session.close()


@heatmap_router.post("/scoring-config/draft/{config_id}/validate")
def heatmap_scoring_config_validate_draft(config_id: int):
    session = heatmap_db.get_db_session()
    try:
        row = session.get(ScoringConfigVersion, config_id)
        if not row:
            raise HTTPException(status_code=404, detail="Scoring config draft not found")
        payload = parse_config_json(row.config_json)
        ok, errors = validate_scoring_config(payload)
        return {"valid": ok, "errors": errors}
    finally:
        session.close()


@heatmap_router.post("/scoring-config/draft/{config_id}/publish", response_model=ScoringConfigVersionOut)
def heatmap_scoring_config_publish_draft(config_id: int):
    from backend.heatmap.services.learned_weights import normalize_full, save_learned_weights

    session = heatmap_db.get_db_session()
    try:
        row = session.get(ScoringConfigVersion, config_id)
        if not row:
            raise HTTPException(status_code=404, detail="Scoring config draft not found")
        if row.status != "draft":
            raise HTTPException(status_code=400, detail="Only draft versions can be published")
        payload = parse_config_json(row.config_json)
        ok, errors = validate_scoring_config(payload)
        if not ok:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        active_rows = session.exec(
            select(ScoringConfigVersion).where(ScoringConfigVersion.status == "active")
        ).all()
        for ar in active_rows:
            ar.status = "archived"
            ar.updated_at = datetime.now(timezone.utc)
            session.add(ar)

        row.status = "active"
        row.published_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        # Wire published config to live scoring by syncing configured weight values
        # into learned weights (shared by table + bulk scoring paths).
        overrides = extract_weight_overrides(payload)
        if overrides:
            save_learned_weights(session, normalize_full(overrides))
        session.commit()
        session.refresh(row)
        return _serialize_scoring_config_row(row)
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


@heatmap_router.post("/opportunities/disposition")
def update_opportunity_disposition(req: OpportunityDispositionUpdateRequest):
    session = heatmap_db.get_db_session()
    try:
        opp = session.get(Opportunity, req.opportunity_id)
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")

        reason_code = (req.not_pursue_reason_code or "").strip() or None
        if req.disposition == "not_pursuing" and not reason_code:
            raise HTTPException(
                status_code=400,
                detail="not_pursue_reason_code is required when disposition=not_pursuing",
            )

        old_payload = {
            "disposition": opp.disposition,
            "not_pursue_reason_code": opp.not_pursue_reason_code,
        }

        opp.disposition = req.disposition
        opp.not_pursue_reason_code = reason_code if req.disposition == "not_pursuing" else None
        session.add(opp)

        audit = AuditLog(
            event_type="OPPORTUNITY_DISPOSITION_UPDATED",
            entity_id=str(opp.id),
            old_value=json.dumps(old_payload),
            new_value=json.dumps(
                {
                    "disposition": opp.disposition,
                    "not_pursue_reason_code": opp.not_pursue_reason_code,
                    "comment_text": (req.comment_text or "").strip()[:1000] or None,
                }
            ),
            user_id=(req.updated_by or "human-manager").strip() or "human-manager",
        )
        session.add(audit)
        session.commit()
        session.refresh(opp)
        return {"success": True, "opportunity": opp.model_dump(mode="json")}
    finally:
        session.close()

@heatmap_router.post("/run")
def run_pipeline():
    # Lightweight mode for low-memory hosts (e.g. Render 512MB):
    # run scoring in background and return immediately.
    return _start_heatmap_pipeline_background()

@heatmap_router.get("/run/status", response_model=PipelineStatusResponse)
def run_pipeline_status():
    return PipelineStatusResponse(**_pipeline_status)

"""
Score new sourcing requests (PS_new) per framework; used by API preview + submit.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from sqlmodel import Session, select

from backend.heatmap.scoring_framework import (
    ius_from_implementation_months,
    es_from_estimated_spend,
    csis_from_category_spend,
    sas_from_category_cards,
)
from backend.heatmap.context_builder import build_heatmap_context
from backend.heatmap.persistence.heatmap_models import Opportunity
from backend.heatmap.services.feedback_memory import apply_learning_nudge
from backend.heatmap.services.learned_weights import merge_intake_ps_new_weights


def tier_from_total(total: float) -> str:
    if total >= 8.0:
        return "T1"
    if total >= 6.0:
        return "T2"
    if total >= 4.0:
        return "T3"
    return "T4"


def ps_new_components(
    *,
    category: str,
    supplier_name: Optional[str],
    estimated_spend_usd: float,
    implementation_timeline_months: float,
    preferred_supplier_status: Optional[str],
    heatmap_context: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, Optional[float]], float, str, str]:
    w = weights or {}
    w_ius = w.get("w_ius", 0.30)
    w_es = w.get("w_es", 0.30)
    w_csis = w.get("w_csis", 0.25)
    w_sas = w.get("w_sas", 0.15)

    ius = ius_from_implementation_months(float(implementation_timeline_months))
    max_pipeline = float(heatmap_context.get("max_estimated_spend_pipeline") or 1.0)
    es = es_from_estimated_spend(float(estimated_spend_usd), max_pipeline)

    cat_spend = float((heatmap_context.get("category_spend_total") or {}).get(category) or 0.0)
    max_cat = float(heatmap_context.get("max_category_spend") or 0.0)
    denom_c = max_cat if max_cat > 0 else max(cat_spend, 1.0)
    csis = csis_from_category_spend(cat_spend, denom_c)

    cards = heatmap_context.get("category_cards") or {}
    sas, sas_ev = sas_from_category_cards(
        category,
        supplier_name,
        True,
        preferred_supplier_status,
        cards,
    )

    total = (w_ius * ius) + (w_es * es) + (w_csis * csis) + (w_sas * sas)
    total_r = round(total, 2)
    tier = tier_from_total(total_r)

    action_window = (
        "Critical (<3 mo)" if implementation_timeline_months < 3
        else "High (3–6 mo)" if implementation_timeline_months < 6
        else "Standard (6–12 mo)" if implementation_timeline_months <= 12
        else "Planned (>12 mo)"
    )

    justification = (
        f"New request PS_new={total_r}. IUS({ius})*{w_ius} + ES({es})*{w_es} + "
        f"CSIS({csis})*{w_csis} + SAS({sas})*{w_sas}. {sas_ev}"
    )

    scores = {
        "ius_score": round(ius, 2),
        "es_score": round(es, 2),
        "csis_score": round(csis, 2),
        "sas_score": round(sas, 2),
    }
    return scores, total_r, tier, justification + f" | {action_window}"


def max_estimated_from_db(session: Session) -> float:
    stmt = select(Opportunity).where(Opportunity.contract_id.is_(None))
    rows = session.exec(stmt).all()
    vals = [float(o.estimated_spend_usd) for o in rows if o.estimated_spend_usd is not None]
    return max(vals) if vals else 0.0


def score_intake_payload(
    session: Session,
    *,
    category: str,
    subcategory: Optional[str],
    supplier_name: Optional[str],
    estimated_spend_usd: float,
    implementation_timeline_months: float,
    preferred_supplier_status: Optional[str],
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Optional[float]], float, str, str]:
    """Build context with correct ES denominator; return context dict + scores + total + tier + justification."""
    existing_max = max_estimated_from_db(session)
    candidate = max(float(estimated_spend_usd), 0.0)
    max_pipeline = max(existing_max, candidate, 1.0)
    ctx = build_heatmap_context(max_estimated_spend_pipeline=max_pipeline)
    raw_card = (ctx.get("category_cards") or {}).get(category)
    category_card = raw_card if isinstance(raw_card, dict) else None
    merged_w = merge_intake_ps_new_weights(session, weights, category_card=category_card)
    scores, total_r, tier, justification = ps_new_components(
        category=category,
        supplier_name=supplier_name,
        estimated_spend_usd=candidate,
        implementation_timeline_months=float(implementation_timeline_months),
        preferred_supplier_status=preferred_supplier_status,
        heatmap_context=ctx,
        weights=merged_w,
    )
    mem_delta, mem_note, total_adj, tier_adj = apply_learning_nudge(
        category=category,
        subcategory=subcategory,
        supplier_name=supplier_name,
        is_new=True,
        baseline_summary=justification,
        base_total=total_r,
        weights=merged_w,
    )
    if mem_note:
        justification = f"{justification} | Learning: {mem_note}"
    total_r = total_adj
    tier = tier_adj
    meta = {
        "max_estimated_spend_pipeline": max_pipeline,
        "category_spend_used": (ctx.get("category_spend_total") or {}).get(category),
        "fis_field_note": ctx.get("fis_contract_value_field"),
        "feedback_memory_delta": mem_delta,
        "weights_used": merged_w,
    }
    return meta, scores, total_r, tier, justification


def persist_intake_opportunity(
    session: Session,
    *,
    request_title: Optional[str],
    category: str,
    subcategory: Optional[str],
    supplier_name: Optional[str],
    estimated_spend_usd: float,
    implementation_timeline_months: float,
    preferred_supplier_status: Optional[str],
    justification_summary_text: Optional[str],
) -> Opportunity:
    meta, scores, total_r, tier, justification = score_intake_payload(
        session,
        category=category,
        subcategory=subcategory,
        supplier_name=supplier_name,
        estimated_spend_usd=estimated_spend_usd,
        implementation_timeline_months=implementation_timeline_months,
        preferred_supplier_status=preferred_supplier_status,
    )
    req_id = f"REQ-INTAKE-{uuid4().hex[:10].upper()}"
    if justification_summary_text:
        justification = justification + " | " + justification_summary_text[:500]

    opp = Opportunity(
        contract_id=None,
        request_id=req_id,
        supplier_name=supplier_name,
        category=category,
        subcategory=subcategory,
        eus_score=None,
        ius_score=scores["ius_score"],
        fis_score=None,
        es_score=scores["es_score"],
        rss_score=None,
        scs_score=None,
        csis_score=scores["csis_score"],
        sas_score=scores["sas_score"],
        total_score=total_r,
        tier=tier,
        recommended_action_window=None,
        justification_summary=justification,
        status="Pending",
        source="intake",
        estimated_spend_usd=float(estimated_spend_usd),
        implementation_timeline_months=float(implementation_timeline_months),
        request_title=request_title,
        preferred_supplier_status=preferred_supplier_status,
        weights_used_json=str(
            {
                "pipeline_max_estimated": meta["max_estimated_spend_pipeline"],
                "feedback_memory_delta": meta.get("feedback_memory_delta"),
                "ps_new_weights": meta.get("weights_used"),
            }
        ),
    )
    session.add(opp)
    session.commit()
    session.refresh(opp)
    return opp

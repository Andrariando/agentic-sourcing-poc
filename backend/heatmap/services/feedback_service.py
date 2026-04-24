from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from sqlmodel import select

from backend.heatmap.persistence.heatmap_models import Opportunity, ReviewFeedback, AuditLog
from backend.infrastructure.storage_providers import get_heatmap_db, get_heatmap_vector_store
from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay
from backend.heatmap.context_builder import load_category_cards
from backend.heatmap.services.learned_weights import (
    normalize_full,
    sync_opportunity_scores_after_weight_change,
    tier_from_total,
    update_weights_from_feedback,
)


class FeedbackService:
    """
    Handles human-in-the-loop feedback for the Heatmap scoring system.
    Stores adjustments in SQLite and embeds written feedback into ChromaDB
    for the agentic learning loop. Tier reviews also nudge persisted scoring
    weights (see HeatmapLearnedWeights) and reconcile the opportunity row.
    """

    def submit_feedback(
        self,
        opportunity_id: int,
        reviewer_id: str,
        adj_type: str,
        adj_val: float,
        reason: str,
        comment: str,
        component: str,
        *,
        suggested_tier: Optional[str] = None,
        weight_adjustments: Optional[Dict[str, float]] = None,
        scoring_weight_overrides: Optional[Dict[str, float]] = None,
        tier_before: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        session = get_heatmap_db().get_db_session()

        try:
            feedback = ReviewFeedback(
                opportunity_id=opportunity_id,
                reviewer_id=reviewer_id,
                adjustment_type=adj_type,
                adjustment_value=adj_val,
                reason_code=reason,
                comment_text=comment,
                component_affected=component,
            )
            session.add(feedback)

            audit = AuditLog(
                event_type="SCORE_OVERRIDE",
                entity_id=str(opportunity_id),
                user_id=reviewer_id,
                new_value=f"{component} {adj_type} {adj_val}",
            )
            session.add(audit)

            stmt = select(Opportunity).where(Opportunity.id == opportunity_id)
            opp = session.exec(stmt).first()

            if opp and (suggested_tier or weight_adjustments or scoring_weight_overrides):
                w = update_weights_from_feedback(
                    session,
                    opp,
                    suggested_tier=suggested_tier or (opp.tier or "T4"),
                    weight_overrides=scoring_weight_overrides,
                    manual_deltas=weight_adjustments,
                )
                cards = load_category_cards()
                raw_c = cards.get((opp.category or "").strip()) or cards.get(opp.category or "")
                ccard = raw_c if isinstance(raw_c, dict) else {}
                w_effective = apply_category_scoring_overlay(w, ccard)
                sync_opportunity_scores_after_weight_change(
                    session,
                    opp,
                    w_effective,
                    suggested_tier=suggested_tier,
                )
                if scoring_weight_overrides:
                    # User expectation: "Save review" should immediately reflect on table score
                    # for the reviewed row. Apply saved slider mix directly to this row.
                    w_manual = normalize_full(scoring_weight_overrides)
                    if opp.contract_id is None:
                        total_manual = (
                            float(w_manual.get("w_ius", 0.0)) * float(opp.ius_score or 0.0)
                            + float(w_manual.get("w_es", 0.0)) * float(opp.es_score or 0.0)
                            + float(w_manual.get("w_csis", 0.0)) * float(opp.csis_score or 0.0)
                            + float(w_manual.get("w_sas_new", 0.0)) * float(opp.sas_score or 0.0)
                        )
                    else:
                        total_manual = (
                            float(w_manual.get("w_eus", 0.0)) * float(opp.eus_score or 0.0)
                            + float(w_manual.get("w_fis", 0.0)) * float(opp.fis_score or 0.0)
                            + float(w_manual.get("w_rss", 0.0)) * float(opp.rss_score or 0.0)
                            + float(w_manual.get("w_scs", 0.0)) * float(opp.scs_score or 0.0)
                            + float(w_manual.get("w_sas_contract", 0.0)) * float(opp.sas_score or 0.0)
                        )
                    total_manual = round(max(0.0, min(10.0, total_manual)), 2)
                    opp.total_score = total_manual
                    st = (suggested_tier or "").strip().upper()
                    opp.tier = st if st in {"T1", "T2", "T3", "T4"} else tier_from_total(total_manual)
                    session.add(opp)
                # Keep dashboard consistent with the latest learned/global mix:
                # recompute all opportunity totals (per-row category overlay) so
                # table/list scores match what users see in weight sliders.
                all_opps = session.exec(select(Opportunity)).all()
                for other in all_opps:
                    if not other or (opp.id is not None and other.id == opp.id):
                        continue
                    raw_other = cards.get((other.category or "").strip()) or cards.get(other.category or "")
                    ccard_other = raw_other if isinstance(raw_other, dict) else {}
                    w_other = apply_category_scoring_overlay(w, ccard_other)
                    sync_opportunity_scores_after_weight_change(
                        session,
                        other,
                        w_other,
                        suggested_tier=None,
                    )

            session.commit()

            session.refresh(feedback)
            stmt2 = select(Opportunity).where(Opportunity.id == opportunity_id)
            opp = session.exec(stmt2).first()
            out_snap: Optional[Dict[str, Any]] = None
            if opp:
                out_snap = {
                    "id": opp.id,
                    "tier": opp.tier,
                    "total_score": float(opp.total_score),
                }

            vs = get_heatmap_vector_store()
            metadata = {
                "opportunity_id": str(opportunity_id),
                "reason_code": reason,
                "reviewer_id": reviewer_id,
                "component": component,
                "adjustment_type": adj_type,
                "adjustment_value": float(adj_val),
                "category": (opp.category if opp else "") or "",
                "supplier_name": (opp.supplier_name or "") if opp else "",
                "opportunity_tier": (opp.tier if opp else "") or "",
            }
            chunk_text = (
                f"Human sourcing correction: category={(opp.category if opp else '')}, "
                f"supplier={(opp.supplier_name or '') if opp else ''}, "
                f"tier_before={tier_before or ''}, tier_after={(opp.tier if opp else '')}. "
                f"Adjusted {component} via {adj_type} (value {adj_val}). "
                f"Reason: {reason}. "
                f"Detail: {comment or 'No additional comment.'}"
            )
            doc_id = f"feedback_{feedback.id or uuid4().hex}"
            vs.add_chunks([chunk_text], doc_id, metadata)

            return True, out_snap
        finally:
            session.close()


def get_feedback_service() -> FeedbackService:
    return FeedbackService()

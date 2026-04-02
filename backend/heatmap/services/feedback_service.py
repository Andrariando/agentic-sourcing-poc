from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from sqlmodel import select

from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import Opportunity, ReviewFeedback, AuditLog
from backend.heatmap.persistence.heatmap_vector_store import get_heatmap_vector_store
from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay
from backend.heatmap.context_builder import load_category_cards
from backend.heatmap.services.learned_weights import (
    sync_opportunity_scores_after_weight_change,
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
        session = heatmap_db.get_db_session()

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

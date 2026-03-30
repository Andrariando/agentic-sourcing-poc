"""
Synthetic ReviewFeedback + pipeline audit rows so KPI/KLI surfaces show realistic demo values.

Inserts directly into SQLite (does not call FeedbackService / Chroma) so demos work without vector DB.

Called automatically after each batch scoring run in run_pipeline_init. Optional CLI re-seeds current batch.
"""
from __future__ import annotations

import json
import os
import time
from sqlmodel import Session, select

from backend.heatmap.persistence.heatmap_models import Opportunity, ReviewFeedback, AuditLog


def _should_seed() -> bool:
    return os.getenv("HEATMAP_SKIP_KPI_DEMO_SEED", "").lower() not in ("1", "true", "yes")


def seed_demo_feedback_and_pipeline_audit(
    session: Session,
    *,
    pipeline_duration_sec: float,
    opportunity_count: int,
) -> int:
    """
    For each batch-sourced opportunity, insert a deterministic mix of feedback rows (0–5)
    so the matrix and dashboard show varied override counts, reliability, etc.

    Returns number of ReviewFeedback rows inserted.
    """
    if not _should_seed():
        return 0

    rows = session.exec(select(Opportunity).where(Opportunity.source == "batch")).all()
    sorted_rows = sorted(rows, key=lambda o: (o.id or 0))
    inserted = 0
    reasons = (
        "DEMO_SEED_TIER_REVIEW",
        "DEMO_SEED_RISK_SCORE",
        "DEMO_SEED_SPEND_CHECK",
        "DEMO_SEED_STRATEGY_ALIGN",
    )
    components = ("tier", "rss_score", "total_score", "csis_score")

    for idx, opp in enumerate(sorted_rows):
        if opp.id is None:
            continue
        # Deterministic variety: different rows get different feedback volumes
        n = (idx * 5 + 7 + (hash(opp.supplier_name or "") % 5)) % 6
        for j in range(n):
            session.add(
                ReviewFeedback(
                    opportunity_id=int(opp.id),
                    reviewer_id=f"demo-reviewer-{(idx + j) % 3 + 1}",
                    adjustment_type="override" if j % 2 == 0 else "delta",
                    adjustment_value=float(1.0 + (j % 4)),
                    reason_code=reasons[j % len(reasons)],
                    comment_text=f"Synthetic demo feedback {j + 1}/{n} for KPI/KLI matrix.",
                    component_affected=components[j % len(components)],
                )
            )
            inserted += 1

    audit = AuditLog(
        event_type="HEATMAP_PIPELINE_RUN",
        entity_id="batch",
        new_value=json.dumps(
            {
                "duration_sec": round(float(pipeline_duration_sec), 3),
                "opportunity_count": int(opportunity_count),
                "success": True,
                "finished_at": time.time(),
                "agents_run": 5,
                "demo_seed": True,
            }
        ),
        user_id="pipeline",
    )
    session.add(audit)
    session.commit()
    return inserted


def reseed_demo_for_current_database() -> tuple[int, int]:
    """
    CLI: attach to heatmap.db, remove DEMO_SEED* feedback for batch opps, re-insert demo feedback + audit.
    Use when DB exists but pipeline was run with an older build without seeding.
    """
    from backend.heatmap.persistence.heatmap_database import heatmap_db
    from sqlmodel import delete

    session = heatmap_db.get_db_session()
    try:
        batch = session.exec(select(Opportunity).where(Opportunity.source == "batch")).all()
        ids = [o.id for o in batch if o.id is not None]
        removed = 0
        for oid in ids:
            fb_rows = session.exec(
                select(ReviewFeedback).where(ReviewFeedback.opportunity_id == oid)
            ).all()
            for f in fb_rows:
                if (f.reason_code or "").startswith("DEMO_SEED"):
                    session.delete(f)
                    removed += 1
        session.commit()

        n = seed_demo_feedback_and_pipeline_audit(
            session,
            pipeline_duration_sec=12.5,
            opportunity_count=len(ids),
        )
        return removed, n
    finally:
        session.close()


if __name__ == "__main__":
    removed, inserted = reseed_demo_for_current_database()
    print(
        f"Heatmap KPI demo seed: removed {removed} old DEMO_SEED feedback rows; "
        f"wrote {inserted} new synthetic feedback rows + pipeline audit."
    )

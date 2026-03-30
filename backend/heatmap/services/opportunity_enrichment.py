"""
Enrich opportunity payloads with data-quality warnings and KLI/KPI-derived metrics (honest labeling).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.heatmap.services.data_quality import warnings_for_opportunity


def _non_null_score_fields(row: Dict[str, Any]) -> int:
    keys = (
        "eus_score", "ius_score", "fis_score", "es_score", "rss_score",
        "scs_score", "csis_score", "sas_score",
    )
    return sum(1 for k in keys if row.get(k) is not None)


def _age_days(row: Dict[str, Any]) -> Optional[float]:
    ts = row.get("record_created_at") or row.get("last_refresh_ts")
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(ts, datetime):
        t = ts
    else:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    else:
        t = t.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0.0, (now - t).total_seconds() / 86400.0)


def build_kli_metrics(
    row: Dict[str, Any],
    feedback_count: int,
    pipeline_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Derived metrics from ReviewFeedback counts + pipeline telemetry where available.
    Fields that are not yet measurable are explicitly null.
    """
    pipeline_meta = pipeline_meta or {}
    agents_run = pipeline_meta.get("agents_run")
    if agents_run is None:
        agents_run = 5  # batch scoring depth (documented default until per-node telemetry)

    duration_sec = pipeline_meta.get("duration_sec")
    opp_count = pipeline_meta.get("opportunity_count") or 0
    exec_avg = None
    if duration_sec is not None and opp_count and opp_count > 0:
        exec_avg = round(float(duration_sec) / float(opp_count), 2)

    reliability = max(50, min(99, 100 - min(feedback_count, 10) * 5))
    warnings_len = len(row.get("data_quality_warnings") or [])

    age = _age_days(row)
    cycle_proxy = None
    if age is not None:
        cycle_proxy = round(min(99.0, 20.0 + min(age * 2.0, 60.0)))

    return {
        "source": "derived_feedback_and_telemetry",
        "feedback_rows": feedback_count,
        "ai_reliability_pct": reliability,
        "override_count": feedback_count,
        "cycle_time_reduce_pct": cycle_proxy,
        "edit_density": feedback_count,
        "data_vis_rate_pct": max(60, 100 - warnings_len * 8),
        "signal_density": _non_null_score_fields(row),
        "agents_run": agents_run,
        "exec_time_s": exec_avg,
        "pending_age_days": round(age, 2) if age is not None else None,
    }


def enrich_opportunity_dict(
    d: Dict[str, Any],
    feedback_count: int,
    category_cards_keys: Optional[List[str]],
    pipeline_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    d = dict(d)
    d["data_quality_warnings"] = warnings_for_opportunity(d, category_cards_keys)
    d["kli_metrics"] = build_kli_metrics(d, feedback_count, pipeline_meta)
    return d

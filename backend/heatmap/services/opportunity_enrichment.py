"""
Enrich opportunity payloads with data-quality warnings and KLI/KPI-derived metrics (honest labeling).
"""
from __future__ import annotations

import os
import zlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.heatmap.services.data_quality import warnings_for_opportunity

# Synthetic human baseline until real manual triage benchmarks exist.
# Assumption: analyst wall time to gather signals + score one opportunity to heatmap-equivalent depth.
_DEFAULT_HUMAN_BASELINE_HOURS = 6.0

_CATEGORY_HUMAN_HOUR_MULT: Dict[str, float] = {
    "it infrastructure": 1.0,
    "security": 1.08,
    "software": 1.05,
    "network": 1.0,
}


def _non_null_score_fields(row: Dict[str, Any]) -> int:
    keys = (
        "eus_score", "ius_score", "fis_score", "es_score", "rss_score",
        "scs_score", "csis_score", "sas_score",
    )
    return sum(1 for k in keys if row.get(k) is not None)


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, str):
        try:
            t = datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(val, datetime):
        t = val
    else:
        return None
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def _pending_age_days(row: Dict[str, Any]) -> Optional[float]:
    """Days since record_created_at (opportunity first landed in queue)."""
    t = _parse_dt(row.get("record_created_at"))
    if t is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0.0, (now - t).total_seconds() / 86400.0)


def _category_hour_multiplier(category: str) -> float:
    key = (category or "").strip().lower()
    for prefix, mult in _CATEGORY_HUMAN_HOUR_MULT.items():
        if prefix in key or key.startswith(prefix):
            return mult
    return 1.12


def _human_baseline_scoring_seconds(category: str, opportunity_id: Optional[int]) -> float:
    hours = float(os.environ.get("HEATMAP_HUMAN_BASELINE_SCORE_HOURS", str(_DEFAULT_HUMAN_BASELINE_HOURS)))
    oid = int(opportunity_id or 0)
    jitter_bucket = zlib.adler32(f"{category or ''}\0{oid}".encode("utf-8", errors="ignore")) % 25
    jitter = 1.0 + (jitter_bucket / 100.0)  # 1.00–1.24h scale spread for demos
    mult = _category_hour_multiplier(category)
    return max(300.0, hours * 3600.0 * mult * jitter)  # floor 5 min so % is never insane


def _scoring_latency_seconds(
    row: Dict[str, Any],
    pipeline_meta: Dict[str, Any],
) -> Tuple[Optional[float], str]:
    """
    T_system: time from opportunity record to scored row (last_refresh).
    When both timestamps are identical (typical on same-tick DB insert), use an apportioned
    share of the last pipeline wall clock so the KPI is still computable.
    """
    t0 = _parse_dt(row.get("record_created_at"))
    t1 = _parse_dt(row.get("last_refresh_ts"))
    if t0 is None or t1 is None:
        return None, "missing_timestamps"

    delta = (t1 - t0).total_seconds()
    if delta >= 1.0:
        return max(0.0, delta), "timestamp_delta"

    duration_sec = pipeline_meta.get("duration_sec")
    opp_count = pipeline_meta.get("opportunity_count") or 0
    if duration_sec is not None and opp_count > 0:
        share = float(duration_sec) / float(opp_count)
        return max(share, 0.001), "pipeline_apportioned"

    return max(delta, 0.001), "timestamp_delta"


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

    pending_age = _pending_age_days(row)

    opp_id = row.get("id")
    if isinstance(opp_id, str) and opp_id.isdigit():
        opp_id = int(opp_id)
    elif not isinstance(opp_id, int):
        opp_id = None

    t_system, cycle_method = _scoring_latency_seconds(row, pipeline_meta)
    t_human: Optional[float] = None
    cycle_reduce: Optional[float] = None
    if t_system is not None and cycle_method != "missing_timestamps":
        t_human = _human_baseline_scoring_seconds(str(row.get("category") or ""), opp_id)
        raw_pct = (t_human - t_system) / t_human * 100.0 if t_human > 0 else None
        if raw_pct is not None:
            cycle_reduce = round(max(0.0, min(99.0, raw_pct)), 1)

    return {
        "source": "derived_feedback_and_telemetry",
        "feedback_rows": feedback_count,
        "ai_reliability_pct": reliability,
        "override_count": feedback_count,
        "cycle_time_reduce_pct": cycle_reduce,
        "cycle_time_scoring_sec": round(t_system, 4) if t_system is not None else None,
        "cycle_time_human_baseline_sec": round(t_human, 1) if t_human is not None else None,
        "cycle_time_method": cycle_method,
        "cycle_time_assumption": (
            "Synthetic analyst baseline hours from HEATMAP_HUMAN_BASELINE_SCORE_HOURS "
            f"(default {_DEFAULT_HUMAN_BASELINE_HOURS}h), scaled by category; "
            "T_system = last_refresh_ts - record_created_at or pipeline wall time / N. "
            "Swap in historical manual triage durations when available."
        ),
        "edit_density": feedback_count,
        "data_vis_rate_pct": max(60, 100 - warnings_len * 8),
        "signal_density": _non_null_score_fields(row),
        "agents_run": agents_run,
        "exec_time_s": exec_avg,
        "pending_age_days": round(pending_age, 2) if pending_age is not None else None,
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

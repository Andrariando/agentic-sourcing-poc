"""Unit tests for heatmap opportunity KLI/KPI enrichment (cycle time vs human baseline)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.heatmap.services.opportunity_enrichment import build_kli_metrics


def test_cycle_time_uses_timestamp_delta_when_spread_enough():
    created = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    refreshed = created + timedelta(hours=2)
    row = {
        "id": 1,
        "category": "IT Infrastructure",
        "record_created_at": created.isoformat(),
        "last_refresh_ts": refreshed.isoformat(),
        "eus_score": 5.0,
        "ius_score": None,
        "fis_score": 5.0,
        "es_score": None,
        "rss_score": 5.0,
        "scs_score": 5.0,
        "csis_score": None,
        "sas_score": 5.0,
        "data_quality_warnings": [],
    }
    km = build_kli_metrics(row, feedback_count=0, pipeline_meta=None)
    assert km["cycle_time_method"] == "timestamp_delta"
    assert km["cycle_time_scoring_sec"] == 2 * 3600
    hb = km["cycle_time_human_baseline_sec"]
    assert hb > 4 * 3600
    pct = km["cycle_time_reduce_pct"]
    assert pct is not None
    assert 0 <= pct <= 99
    assert pct < 95


def test_cycle_time_falls_back_to_pipeline_apportioned_when_same_second():
    ts = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    row = {
        "id": 2,
        "category": "IT Infrastructure",
        "record_created_at": ts.isoformat(),
        "last_refresh_ts": ts.isoformat(),
        "eus_score": 5.0,
        "ius_score": None,
        "fis_score": 5.0,
        "es_score": None,
        "rss_score": 5.0,
        "scs_score": 5.0,
        "csis_score": None,
        "sas_score": 5.0,
        "data_quality_warnings": [],
    }
    km = build_kli_metrics(
        row,
        feedback_count=0,
        pipeline_meta={"duration_sec": 8.0, "opportunity_count": 4, "agents_run": 5},
    )
    assert km["cycle_time_method"] == "pipeline_apportioned"
    assert km["cycle_time_scoring_sec"] == 2.0


def test_cycle_time_null_without_timestamps():
    row = {
        "id": 3,
        "category": "Other",
        "record_created_at": None,
        "last_refresh_ts": None,
        "eus_score": None,
        "ius_score": None,
        "fis_score": None,
        "es_score": None,
        "rss_score": None,
        "scs_score": None,
        "csis_score": None,
        "sas_score": None,
        "data_quality_warnings": [],
    }
    km = build_kli_metrics(row, feedback_count=0, pipeline_meta=None)
    assert km["cycle_time_reduce_pct"] is None
    assert km["cycle_time_scoring_sec"] is None
    assert km["cycle_time_method"] == "missing_timestamps"

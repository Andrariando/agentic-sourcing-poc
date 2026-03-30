"""
API smoke tests for heatmap KPI/KLI, intake meta, approve idempotency, metrics dashboard.
Run from repo root: pytest tests/test_heatmap_api.py -q
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_opportunities_enrich_default_has_kli_metrics(client: TestClient):
    r = client.get("/api/heatmap/opportunities")
    assert r.status_code == 200
    opps = r.json()["opportunities"]
    assert opps
    o0 = opps[0]
    assert "kli_metrics" in o0
    assert "data_quality_warnings" in o0
    assert "feedback_rows" in o0["kli_metrics"]


def test_opportunities_enrich_false_strips_enrichment(client: TestClient):
    r = client.get("/api/heatmap/opportunities?enrich=false")
    assert r.status_code == 200
    o0 = r.json()["opportunities"][0]
    assert "kli_metrics" not in o0
    assert "data_quality_warnings" not in o0


def test_intake_categories_has_card_fingerprint(client: TestClient):
    r = client.get("/api/heatmap/intake/categories")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert "category_cards_meta" in data
    assert data["category_cards_meta"].get("sha256")


def test_metrics_dashboard_shape(client: TestClient):
    r = client.get("/api/heatmap/metrics/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert "feedback_rows_total" in d
    assert "opportunities_total" in d
    assert "tier_counts" in d
    assert isinstance(d["feedback_rows_total"], int)


def test_run_status_includes_last_duration_field(client: TestClient):
    r = client.get("/api/heatmap/run/status")
    assert r.status_code == 200
    data = r.json()
    assert "last_duration_sec" in data


def test_approve_idempotent_flags(client: TestClient):
    r = client.get("/api/heatmap/opportunities?enrich=false")
    assert r.status_code == 200
    opps = [o for o in r.json()["opportunities"] if o.get("status") == "Pending"]
    if not opps:
        pytest.skip("no pending opportunities to approve")
    oid = opps[0]["id"]
    a1 = client.post(
        "/api/heatmap/approve",
        json={"opportunity_ids": [oid], "approver_id": "pytest"},
    )
    assert a1.status_code == 200
    j1 = a1.json()
    assert "already_linked" in j1
    assert j1["already_linked"].get(str(oid)) is False
    a2 = client.post(
        "/api/heatmap/approve",
        json={"opportunity_ids": [oid], "approver_id": "pytest"},
    )
    assert a2.status_code == 200
    j2 = a2.json()
    assert j2["already_linked"].get(str(oid)) is True


def test_data_quality_warnings_helper():
    from backend.heatmap.services.data_quality import warnings_for_opportunity

    w = warnings_for_opportunity(
        {"category": "UnknownCat", "source": "intake", "supplier_name": None},
        category_cards_keys=["IT Infrastructure"],
    )
    assert any("category" in x.lower() for x in w)

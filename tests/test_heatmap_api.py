"""
API smoke tests for heatmap KPI/KLI, intake meta, approve idempotency, metrics dashboard.
Run from repo root: pytest tests/test_heatmap_api.py -q
"""
import json

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


def test_intake_categories_lists_real_categories_not_file_docs(client: TestClient):
    r = client.get("/api/heatmap/intake/categories")
    assert r.status_code == 200
    cats = r.json()["categories"]
    assert "_documentation" not in cats
    assert all(not str(c).startswith("_") for c in cats)
    assert "IT Infrastructure" in cats


def test_category_scoring_mix_renormalizes_renewal_block():
    from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay
    from backend.heatmap.services.learned_weights import DEFAULT_WEIGHTS_FLAT, normalize_full

    base = normalize_full(dict(DEFAULT_WEIGHTS_FLAT))
    card = {
        "scoring_mix": {
            "existing_contract_renewal": {
                "supplier_risk_RSS": 0.5,
                "expiry_urgency_EUS": 0.2,
                "financial_impact_FIS": 0.1,
                "spend_concentration_SCS": 0.1,
                "strategic_alignment_SAS": 0.1,
            }
        }
    }
    out = apply_category_scoring_overlay(base, card)
    renew_sum = sum(
        out[k] for k in ("w_eus", "w_fis", "w_rss", "w_scs", "w_sas_contract")
    )
    assert renew_sum == pytest.approx(1.0, abs=0.02)
    assert out["w_rss"] > DEFAULT_WEIGHTS_FLAT["w_rss"]


def test_validate_scoring_mix_rejects_unknown_weight_key():
    from backend.heatmap.category_scoring_mix import validate_scoring_mix_for_patch

    with pytest.raises(ValueError, match="Unknown weight key"):
        validate_scoring_mix_for_patch(
            {"new_sourcing_request": {"implementation_typo_IUS": 1.0}}
        )


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


def test_category_cards_extract_from_unstructured_text(client: TestClient):
    raw_text = """
    Default supplier status: allowed
    Category Strategy SAS = 8.5
    Azure: preferred
    LegacyVendor - non preferred
    """
    r = client.post(
        "/api/heatmap/category-cards/extract",
        json={"category": "IT Infrastructure", "raw_text": raw_text},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["used_llm"] is False
    assert data["category"] == "IT Infrastructure"
    patch = data["proposed_patch"]
    assert patch["default_preferred_status"] == "allowed"
    assert patch["category_strategy_sas"] == pytest.approx(8.5)
    assert patch["supplier_preferred_status"]["Azure"] == "preferred"
    assert patch["supplier_preferred_status"]["LegacyVendor"] == "nonpreferred"


def test_category_cards_extract_requires_meaningful_text(client: TestClient):
    r = client.post(
        "/api/heatmap/category-cards/extract",
        json={"category": "IT Infrastructure", "raw_text": "too short"},
    )
    assert r.status_code == 422


def test_category_cards_extract_upload_multipart(client: TestClient):
    body = b"""Default supplier status: allowed
Category Strategy SAS = 8.0
WidgetCo: preferred
"""
    r = client.post(
        "/api/heatmap/category-cards/extract-upload",
        data={"category": "Software"},
        files={"file": ("policy.txt", body, "text/plain")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("filename") == "policy.txt"
    assert data["proposed_patch"]["default_preferred_status"] == "allowed"
    assert data["proposed_patch"]["supplier_preferred_status"]["WidgetCo"] == "preferred"


def test_apply_category_cards_patch_merge_tmp_path(tmp_path):
    from backend.heatmap.services.category_cards_store import apply_category_cards_patch

    p = tmp_path / "category_cards.json"
    p.write_text(
        json.dumps(
            {
                "Software": {
                    "default_preferred_status": "allowed",
                    "category_strategy_sas": 7.5,
                    "supplier_preferred_status": {"NexusSoft LLC": "preferred"},
                }
            }
        ),
        encoding="utf-8",
    )
    out = apply_category_cards_patch(
        "Software",
        {"category_strategy_sas": 8.0, "supplier_preferred_status": {"NewCo": "allowed"}},
        cards_path=p,
    )
    assert out["merged_card"]["category_strategy_sas"] == 8.0
    assert out["merged_card"]["supplier_preferred_status"]["NexusSoft LLC"] == "preferred"
    assert out["merged_card"]["supplier_preferred_status"]["NewCo"] == "allowed"
    reloaded = json.loads(p.read_text(encoding="utf-8"))
    assert reloaded["Software"]["category_strategy_sas"] == 8.0

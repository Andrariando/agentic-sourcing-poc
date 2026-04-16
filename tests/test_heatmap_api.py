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


def test_opportunity_not_pursue_and_filter_exclusion(client: TestClient):
    r = client.get("/api/heatmap/opportunities?enrich=false")
    assert r.status_code == 200
    opps = r.json()["opportunities"]
    assert opps
    oid = opps[0]["id"]

    u = client.post(
        "/api/heatmap/opportunities/disposition",
        json={
            "opportunity_id": oid,
            "disposition": "not_pursuing",
            "not_pursue_reason_code": "strategy_change",
            "comment_text": "No longer in scope",
            "updated_by": "pytest",
        },
    )
    assert u.status_code == 200
    updated = u.json()["opportunity"]
    assert updated["disposition"] == "not_pursuing"
    assert updated["not_pursue_reason_code"] == "strategy_change"

    f = client.get("/api/heatmap/opportunities?enrich=false&include_not_pursuing=false")
    assert f.status_code == 200
    ids = {o["id"] for o in f.json()["opportunities"]}
    assert oid not in ids


def test_case_cancel_with_reason(client: TestClient):
    c = client.post(
        "/api/cases",
        json={"category_id": "IT Infrastructure", "trigger_source": "pytest"},
    )
    assert c.status_code == 200
    case_id = c.json()["case_id"]

    k = client.post(
        f"/api/cases/{case_id}/cancel",
        json={
            "reason_code": "budget_cut",
            "reason_text": "Stopped after budget re-baseline",
            "cancelled_by": "pytest-user",
        },
    )
    assert k.status_code == 200
    assert k.json()["status"] == "Cancelled"

    g = client.get(f"/api/cases/{case_id}")
    assert g.status_code == 200
    assert g.json()["status"] == "Cancelled"


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


def test_system1_preview_includes_scoring_readiness(client: TestClient):
    csv_bytes = (
        b"row_type,category,supplier_name,estimated_spend_usd,contract_id,months_to_expiry\n"
        b"renewal,IT Infrastructure,VendorA,1200000,CNT-1,6\n"
    )
    r = client.post(
        "/api/system1/upload/preview",
        files={"files": ("rows.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["candidates"]
    row = data["candidates"][0]
    assert "score_components" in row
    assert "computed_total_score" in row
    assert "readiness_status" in row


def test_system1_approve_requires_warning_ack(client: TestClient):
    # Missing months_to_expiry makes at least one component defaulted => warning row.
    csv_bytes = (
        b"row_type,category,supplier_name,estimated_spend_usd,contract_id\n"
        b"renewal,IT Infrastructure,VendorB,900000,CNT-2\n"
    )
    p = client.post(
        "/api/system1/upload/preview",
        files={"files": ("rows.csv", csv_bytes, "text/csv")},
    )
    assert p.status_code == 200
    payload = p.json()
    rid = payload["candidates"][0]["row_id"]
    job_id = payload["job_id"]

    fail = client.post(
        "/api/system1/upload/approve",
        json={"job_id": job_id, "approved_row_ids": [rid], "approver_id": "pytest"},
    )
    assert fail.status_code == 400

    ok = client.post(
        "/api/system1/upload/approve",
        json={
            "job_id": job_id,
            "approved_row_ids": [rid],
            "approver_id": "pytest",
            "acknowledge_warning_row_ids": [rid],
        },
    )
    assert ok.status_code == 200
    assert ok.json()["success"] is True


def test_system1_templates_endpoint(client: TestClient):
    r = client.get("/api/system1/upload/templates")
    assert r.status_code == 200
    templates = r.json().get("templates", [])
    assert templates
    names = {t["name"] for t in templates}
    assert "renewals_template.csv" in names
    assert "new_business_template.csv" in names


def test_system1_preview_sponsor_style_headers(client: TestClient):
    """Excel/CSV exports often use vendor / commodity / TCV style columns."""
    csv_bytes = (
        b"Opportunity Type,Commodity,Vendor Name,Agreement #,TCV,Expiration Date\n"
        b"renewal,Cloud Services,Acme Corp,AGR-99,\"$1,200,000\",2026-11-30\n"
    )
    r = client.post(
        "/api/system1/upload/preview",
        files={"files": ("sponsor_export.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["candidates"]
    row = data["candidates"][0]
    assert row["supplier_name"] == "Acme Corp"
    assert row["category"] == "Cloud Services"
    assert row["contract_id"] == "AGR-99"
    assert float(row["estimated_spend_usd"]) == 1_200_000.0
    assert row["row_type"] == "renewal"


def test_system1_preview_capstone_contract_export_headers(client: TestClient):
    """J&J-style contract workbook columns (Supplier, Value in USD, Master Agreement, Expiry)."""
    csv_bytes = (
        b"Supplier,Category,Sub Category,Expiry Date,Value in USD,Master Agreement Reference Number,Contract Name\n"
        b"RENTACOM INC,IT Infrastructure,zIT - Other - DO NOT USE,2016-06-30,2800,C2015023508,Dermatology Work Order\n"
    )
    r = client.post(
        "/api/system1/upload/preview",
        files={"files": ("contract_export.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    row = r.json()["candidates"][0]
    assert row["supplier_name"] == "RENTACOM INC"
    assert row["category"] == "IT Infrastructure"
    assert row["subcategory"] == "zIT - Other - DO NOT USE"
    assert row["contract_id"] == "C2015023508"
    assert float(row["estimated_spend_usd"]) == 2800.0
    assert "Dermatology" in (row.get("request_title") or "")


def test_system1_preview_capstone_spend_export_headers(client: TestClient):
    """IT Infra Spend grain: booked hierarchy + SMD supplier + invoice amount."""
    csv_bytes = (
        b"key_spend_id,Booked category,Booked subcategory,Commodity,SMD cleansed name,Invoice amount (USD)\n"
        b"k1,IT Infrastructure,IT Infrastructure - Mobile,Mobile Device Management,DISCORP NV,15.76\n"
    )
    r = client.post(
        "/api/system1/upload/preview",
        files={"files": ("spend_lines.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    row = r.json()["candidates"][0]
    assert row["supplier_name"] == "DISCORP NV"
    assert row["category"] == "IT Infrastructure"
    assert "Mobile" in (row.get("subcategory") or "")
    assert float(row["estimated_spend_usd"]) == 15.76
    assert row.get("request_title")


def test_system1_scan_bundle_fuses_contract_spend_metrics(client: TestClient):
    contract_csv = (
        b"Supplier,Category,Sub Category,Expiry Date,Master Agreement Reference Number,Contract Name\n"
        b"ACME CORP,IT Infrastructure,Cloud Hosting,2027-06-30,CNT-ACME-1,Cloud Renewal\n"
    )
    spend_csv = (
        b"SMD cleansed name,Booked category,Booked subcategory,Invoice amount (USD),key_spend_id\n"
        b"ACME CORP,IT Infrastructure,Cloud Hosting,1000000,sp-1\n"
    )
    metrics_csv = (
        b"Supplier,Category,Subcategory,Supplier Risk Score,BPRA Vendor Status\n"
        b"ACME CORP,IT Infrastructure,Cloud Hosting,7.2,preferred\n"
    )
    r = client.post(
        "/api/system1/upload/scan-bundle",
        files=[
            ("files", ("contracts.csv", contract_csv, "text/csv")),
            ("files", ("spend.csv", spend_csv, "text/csv")),
            ("files", ("metrics.csv", metrics_csv, "text/csv")),
        ],
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_candidates"] >= 1
    rows = data["candidates"]
    # Contract-led fusion should produce a renewal row for ACME.
    acme = [x for x in rows if (x.get("supplier_name") or "").upper() == "ACME CORP"]
    assert acme
    row = acme[0]
    assert row["row_type"] == "renewal"
    assert row["contract_id"] == "CNT-ACME-1"
    assert float(row["estimated_spend_usd"]) > 0
    assert row.get("computed_total_score") is not None


def test_system1_scan_bundle_rejects_non_structured_only(client: TestClient):
    txt_bytes = b"This is guidance text only."
    r = client.post(
        "/api/system1/upload/scan-bundle",
        files=[("files", ("guidance.txt", txt_bytes, "text/plain"))],
    )
    assert r.status_code == 400

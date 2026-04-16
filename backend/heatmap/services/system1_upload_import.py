"""
Normalize sponsor / Capstone-style spreadsheets for System 1 staged upload.

Maps messy column headers (Excel exports, BOM, spaces, synonyms) to canonical
fields consumed by ``_build_preview_row`` in ``backend.main``.

Tested against sample layouts:
- IT Infra Spend.xlsx (invoice/PO grain, SMD supplier, booked hierarchy)
- IT Infrastructure Contract Data.xlsx (agreements, expiry, contract value)
- Supplier Metrics Data (supplier + category; spend tier is categorical — not USD)
"""
from __future__ import annotations

import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# slug (lowercase alphanum + underscores) -> canonical field name
SYSTEM1_SLUG_TO_CANONICAL: Dict[str, str] = {
    # row / opportunity type
    "row_type": "row_type",
    "type": "row_type",
    "opportunity_type": "row_type",
    "record_type": "row_type",
    "request_type": "row_type",
    "sourcing_type": "row_type",
    # category (do NOT map Commodity -> category; see fallbacks)
    "category": "category",
    "booked_category": "category",
    "reporting_category": "category",
    "spend_category": "category",
    "procurement_category": "category",
    "category_name": "category",
    "unspsc": "category",
    # subcategory
    "subcategory": "subcategory",
    "sub_category": "subcategory",
    "booked_subcategory": "subcategory",
    "reporting_subcategory": "subcategory",
    "sub_category_name": "subcategory",
    "sub_cat": "subcategory",
    # supplier / vendor
    "supplier_name": "supplier_name",
    "supplier": "supplier_name",
    "vendor": "supplier_name",
    "vendor_name": "supplier_name",
    "supplier_legal_name": "supplier_name",
    "incumbent": "supplier_name",
    "incumbent_supplier": "supplier_name",
    "supplier_company": "supplier_name",
    "company_name": "supplier_name",
    "service_provider": "supplier_name",
    "partner": "supplier_name",
    "smd_cleansed_name": "supplier_name",
    "smd_name": "supplier_name",
    "original_contract_supplier_contracting_party": "supplier_name",
    "msa_id": "contract_id",
    # contract / agreement id
    "contract_id": "contract_id",
    "contract_number": "contract_id",
    "agreement_id": "contract_id",
    "agreement_number": "contract_id",
    "agreement": "contract_id",
    "contract_no": "contract_id",
    "contract_num": "contract_id",
    "po_number": "contract_id",
    "purchase_order": "contract_id",
    "po_id": "contract_id",
    "master_agreement_reference_number": "contract_id",
    # spend (USD-ish numeric columns) — prioritized resolution may override
    "estimated_spend_usd": "estimated_spend_usd",
    "spend": "estimated_spend_usd",
    "estimated_spend": "estimated_spend_usd",
    "annual_spend": "estimated_spend_usd",
    "contract_value": "estimated_spend_usd",
    "tcv": "estimated_spend_usd",
    "total_contract_value": "estimated_spend_usd",
    "acv": "estimated_spend_usd",
    "amount": "estimated_spend_usd",
    "value": "estimated_spend_usd",
    "value_usd": "estimated_spend_usd",
    "usd_spend": "estimated_spend_usd",
    "spend_amount": "estimated_spend_usd",
    "total_spend": "estimated_spend_usd",
    "est_spend": "estimated_spend_usd",
    "budget": "estimated_spend_usd",
    "spend_usd": "estimated_spend_usd",
    "usd_amount": "estimated_spend_usd",
    "full_contract_value": "estimated_spend_usd",
    "invoice_amount_usd": "estimated_spend_usd",
    "currency_icmanticiptaedspendamount": "estimated_spend_usd",
    "h_invoice_net_amount_usd": "estimated_spend_usd",
    "h_invoice_gross_amount_usd": "estimated_spend_usd",
    "p_payment_amount_usd": "estimated_spend_usd",
    "h_total_po_amount_usd": "estimated_spend_usd",
    "po_amount_usd": "estimated_spend_usd",
    # dates
    "contract_end_date": "contract_end_date",
    "expiration_date": "contract_end_date",
    "expiry_date": "contract_end_date",
    "end_date": "contract_end_date",
    "contract_expiry": "contract_end_date",
    "contract_expiry_date": "contract_end_date",
    "renewal_date": "contract_end_date",
    "contract_end": "contract_end_date",
    # months to expiry
    "months_to_expiry": "months_to_expiry",
    "months_remaining": "months_to_expiry",
    "monthstoexpiry": "months_to_expiry",
    "mte": "months_to_expiry",
    "expiry_months": "months_to_expiry",
    "months_to_expire": "months_to_expiry",
    # new business timeline
    "implementation_timeline_months": "implementation_timeline_months",
    "implementation_months": "implementation_timeline_months",
    "timeline_months": "implementation_timeline_months",
    "impl_months": "implementation_timeline_months",
    "go_live_months": "implementation_timeline_months",
    # preferred supplier
    "preferred_supplier_status": "preferred_supplier_status",
    "supplier_status": "preferred_supplier_status",
    "preferred_status": "preferred_supplier_status",
    "ps_status": "preferred_supplier_status",
    "strategic_supplier_status": "preferred_supplier_status",
    "preference": "preferred_supplier_status",
    "bpra_vendor_status": "preferred_supplier_status",
    # optional scores
    "rss_score": "rss_score",
    "rss": "rss_score",
    "supplier_risk_score": "rss_score",
    "scs_score": "scs_score",
    "scs": "scs_score",
    "sas_score": "sas_score",
    "sas": "sas_score",
    # titles (new business)
    "request_title": "request_title",
    "title": "request_title",
    "request_name": "request_title",
    "project_name": "request_title",
    "initiative": "request_title",
    "initiative_name": "request_title",
    "business_request": "request_title",
    "contract_name": "request_title",
}

# When several money columns exist, prefer payment / contract value fields over invoice lines.
_SPEND_SLUG_PRIORITY: Tuple[str, ...] = (
    "p_payment_amount_usd",
    "payment_amount_usd",
    "invoice_amount_usd",
    "h_invoice_net_amount_usd",
    "h_invoice_gross_amount_usd",
    "value_in_usd",
    "full_contract_value",
    "contract_value",
    "currency_icmanticiptaedspendamount",
    "h_total_po_amount_usd",
    "po_amount_usd",
    "estimated_spend_usd",
    "spend",
    "amount",
    "value",
)


def _slug_header(name: str) -> str:
    s = (name or "").replace("\ufeff", "").strip().lower()
    s = re.sub(r"[\s\.\-\/\\]+", "_", s)
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _is_blank_cell(v: Any) -> bool:
    if v is None:
        return True
    try:
        import pandas as pd

        if pd.isna(v):
            return True
    except Exception:
        pass
    if isinstance(v, str) and not v.strip():
        return True
    return False


def _row_is_effectively_empty(row: Dict[str, Any]) -> bool:
    return all(_is_blank_cell(v) for v in row.values())


def _apply_prioritized_spend_usd(raw_slugs: Dict[str, Any], out: Dict[str, Any]) -> None:
    for slug in _SPEND_SLUG_PRIORITY:
        v = raw_slugs.get(slug)
        if not _is_blank_cell(v):
            out["estimated_spend_usd"] = v
            return


def _apply_capstone_field_fallbacks(raw_slugs: Dict[str, Any], out: Dict[str, Any]) -> None:
    """Fill gaps common in J&J-style Capstone extracts."""
    if _is_blank_cell(out.get("category")):
        for slug in ("booked_category", "reporting_category", "category"):
            v = raw_slugs.get(slug)
            if not _is_blank_cell(v):
                out["category"] = v
                break
    if _is_blank_cell(out.get("category")):
        for slug in ("commodity", "booked_commodity", "reporting_commodity"):
            v = raw_slugs.get(slug)
            if not _is_blank_cell(v):
                out["category"] = str(v).strip()
                break

    if _is_blank_cell(out.get("subcategory")):
        for slug in ("booked_subcategory", "reporting_subcategory", "sub_category", "subcategory"):
            v = raw_slugs.get(slug)
            if not _is_blank_cell(v):
                out["subcategory"] = v
                break
    if _is_blank_cell(out.get("subcategory")):
        cat = str(out.get("category") or "").strip()
        for slug in ("commodity", "booked_commodity", "reporting_commodity"):
            v = raw_slugs.get(slug)
            if _is_blank_cell(v):
                continue
            sv = str(v).strip()
            if sv and sv != cat:
                out["subcategory"] = sv
                break

    if _is_blank_cell(out.get("supplier_name")):
        for slug in (
            "smd_cleansed_name",
            "smd_name",
            "supplier_name",
            "supplier",
            "original_contract_supplier_contracting_party",
        ):
            v = raw_slugs.get(slug)
            if not _is_blank_cell(v):
                out["supplier_name"] = str(v).strip()
                break

    if _is_blank_cell(out.get("request_title")):
        for slug in ("contract_name", "key_spend_id", "project_name", "title"):
            v = raw_slugs.get(slug)
            if not _is_blank_cell(v):
                out["request_title"] = str(v).strip()[:500]
                break

    # Prefer master agreement / explicit contract id over generic case number when filling contract_id
    if _is_blank_cell(out.get("contract_id")):
        for slug in (
            "master_agreement_reference_number",
            "contract_id",
            "contract_number",
            "agreement_number",
            "po_id",
            "case_number",
        ):
            v = raw_slugs.get(slug)
            if not _is_blank_cell(v):
                out["contract_id"] = str(v).strip()
                break


def canonicalize_system1_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge messy keys into canonical keys expected by System 1 preview builder.
    Later keys win only if canonical slot still empty (Excel column order preserved).
    """
    raw_slugs: Dict[str, Any] = {}
    for key, val in raw.items():
        slug = _slug_header(str(key))
        if slug:
            raw_slugs[slug] = val

    out: Dict[str, Any] = {}
    for slug, val in raw_slugs.items():
        canon = SYSTEM1_SLUG_TO_CANONICAL.get(slug)
        if canon is None:
            if slug not in out or _is_blank_cell(out.get(slug)):
                out[slug] = val
            continue
        if canon not in out or _is_blank_cell(out.get(canon)):
            out[canon] = val

    _apply_prioritized_spend_usd(raw_slugs, out)
    _apply_capstone_field_fallbacks(raw_slugs, out)
    return out


def extract_rows_from_structured_file(
    content: bytes,
    filename: str,
    column_mapping: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse CSV / Excel into list of dicts with canonical-ish keys.
    Returns (rows, parsing_notes).
    """
    notes: List[str] = []
    try:
        import pandas as pd
    except Exception:
        return [], ["pandas not available; cannot parse structured upload"]

    ext = os.path.splitext(filename)[1].lower()
    if ext == ".csv":
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=enc)
                break
            except Exception:
                df = None  # type: ignore[assignment]
        else:
            return [], ["Could not decode CSV (tried utf-8-sig, utf-8, cp1252)"]
    elif ext in {".xls", ".xlsx"}:
        try:
            xls = pd.ExcelFile(io.BytesIO(content))
            if len(xls.sheet_names) > 1:
                notes.append(
                    f"Excel has {len(xls.sheet_names)} sheet(s); using first sheet "
                    f"'{xls.sheet_names[0]}'. Others: {xls.sheet_names[1:5]}"
                    + ("..." if len(xls.sheet_names) > 5 else "")
                )
            df = pd.read_excel(xls, sheet_name=0)
        except Exception as e:
            return [], [f"Excel read failed: {e!s}"]
    else:
        return [], []

    n_rows = len(df)
    if n_rows > 1500:
        notes.append(
            f"{os.path.basename(filename)}: {n_rows} data rows — if this is invoice/PO-level spend, "
            "each row becomes one opportunity; aggregate in analytics first if you need contract-level scoring."
        )

    df = df.dropna(how="all")
    if df.empty:
        return [], ["No data rows after removing empty lines"]

    mapping = {str(k).strip().lower(): str(v).strip().lower() for k, v in (column_mapping or {}).items()}

    out: List[Dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        normalized = {str(k).strip().lower(): v for k, v in row.items()}
        if mapping:
            remapped: Dict[str, Any] = {}
            for k, v in normalized.items():
                remapped[mapping.get(k, k)] = v
            normalized = remapped
        merged = canonicalize_system1_row(normalized)
        if _row_is_effectively_empty(merged):
            continue
        out.append(merged)

    if not out:
        notes.append("All rows were empty after parsing")
    return out, notes

"""
System 1 bundle scan helpers.

Goal: fuse multiple structured sponsor files (contracts, spend, supplier metrics)
into a deduplicated set of opportunity rows for review.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from typing import Any, Dict, List, Optional, Tuple


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _clean(s: Any) -> Optional[str]:
    try:
        import pandas as pd

        if pd.isna(s):
            return None
    except Exception:
        pass
    out = str(s or "").strip()
    if out.lower() in {"nan", "none", "null"}:
        return None
    return out or None


def _safe_float(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    txt = str(raw).strip().replace(",", "")
    for sym in ("$", "€", "£"):
        txt = txt.replace(sym, "")
    txt = txt.strip()
    if not txt:
        return None
    try:
        val = float(txt)
        if not math.isfinite(val):
            return None
        return val
    except Exception:
        return None


def _safe_opt_datetime(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    txt = str(raw).strip()
    if not txt:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(txt, fmt)
        except Exception:
            pass
    try:
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(tz=None).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _looks_contract_file(filename: str) -> bool:
    f = _norm(filename)
    return "contract" in f or "agreement" in f


def _looks_spend_file(filename: str) -> bool:
    f = _norm(filename)
    return "spend" in f or "invoice" in f or "po" in f


def _looks_metrics_file(filename: str) -> bool:
    f = _norm(filename)
    return "metric" in f or "risk" in f or "supplier metrics" in f


def _coalesce(*vals: Any) -> Optional[str]:
    for v in vals:
        s = _clean(v)
        if s:
            return s
    return None


def _merge_key(*, supplier_name: Optional[str], category: Optional[str], subcategory: Optional[str]) -> str:
    return f"{_norm(supplier_name)}|{_norm(category)}|{_norm(subcategory)}"


def _row_type_from_raw(raw_row_type: Any, contract_id: Optional[str]) -> str:
    t = _norm(raw_row_type)
    if t in {"renewal", "new_business"}:
        return t
    return "renewal" if contract_id else "new_business"


def fuse_bundle_rows(rows_by_file: Dict[str, List[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Returns (fused_rows, notes) where fused_rows are canonical-ish raw rows
    compatible with `_build_preview_row`.
    """
    notes: List[str] = []

    contracts: List[Dict[str, Any]] = []
    spend_agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"estimated_spend_usd": 0.0, "row_count": 0})
    metrics_by_key: Dict[str, Dict[str, Any]] = {}

    for filename, rows in rows_by_file.items():
        is_contract = _looks_contract_file(filename)
        is_spend = _looks_spend_file(filename)
        is_metrics = _looks_metrics_file(filename)

        if not (is_contract or is_spend or is_metrics):
            # fallback heuristic by available columns
            sample = rows[0] if rows else {}
            if "contract_end_date" in sample or "contract_id" in sample:
                is_contract = True
            elif "rss_score" in sample or "supplier_risk_score" in sample:
                is_metrics = True
            else:
                is_spend = True

        if is_contract:
            for r in rows:
                cid = _coalesce(r.get("contract_id"))
                contracts.append(
                    {
                        "source_filename": filename,
                        "row_type": _row_type_from_raw(
                            r.get("row_type") or r.get("type") or r.get("opportunity_type"),
                            cid,
                        ),
                        "supplier_name": _coalesce(r.get("supplier_name"), r.get("supplier")),
                        "category": _coalesce(r.get("category"), "Uncategorized"),
                        "subcategory": _coalesce(r.get("subcategory")),
                        "contract_id": cid,
                        "contract_end_date": r.get("contract_end_date"),
                        "months_to_expiry": _safe_float(r.get("months_to_expiry")),
                        "implementation_timeline_months": _safe_float(r.get("implementation_timeline_months")),
                        "estimated_spend_usd": _safe_float(r.get("estimated_spend_usd")),
                        "request_title": _coalesce(r.get("request_title")),
                        "preferred_supplier_status": _coalesce(
                            r.get("preferred_supplier_status"), r.get("bpra_vendor_status")
                        ),
                        "rss_score": _safe_float(r.get("rss_score") or r.get("supplier_risk_score")),
                    }
                )
            continue

        if is_spend:
            for r in rows:
                supplier = _coalesce(r.get("supplier_name"), r.get("supplier"))
                category = _coalesce(r.get("category"), "Uncategorized")
                subcategory = _coalesce(r.get("subcategory"))
                amt = _safe_float(r.get("estimated_spend_usd")) or 0.0
                if not supplier or amt <= 0:
                    continue
                key = _merge_key(supplier_name=supplier, category=category, subcategory=subcategory)
                bucket = spend_agg[key]
                bucket["estimated_spend_usd"] = float(bucket["estimated_spend_usd"]) + float(amt)
                bucket["row_count"] = int(bucket["row_count"]) + 1
                bucket["supplier_name"] = supplier
                bucket["category"] = category
                bucket["subcategory"] = subcategory
            continue

        if is_metrics:
            for r in rows:
                supplier = _coalesce(r.get("supplier_name"), r.get("supplier"))
                category = _coalesce(r.get("category"), "Uncategorized")
                subcategory = _coalesce(r.get("subcategory"))
                if not supplier:
                    continue
                key = _merge_key(supplier_name=supplier, category=category, subcategory=subcategory)
                cur = metrics_by_key.get(key, {})
                rss = _safe_float(r.get("rss_score") or r.get("supplier_risk_score"))
                if rss is not None:
                    cur["rss_score"] = rss
                pref = _coalesce(r.get("preferred_supplier_status"), r.get("bpra_vendor_status"))
                if pref:
                    cur["preferred_supplier_status"] = pref
                cur["supplier_name"] = supplier
                cur["category"] = category
                cur["subcategory"] = subcategory
                metrics_by_key[key] = cur

    fused: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    # Contract-led opportunities; enrich with spend and metrics by supplier/category/subcategory.
    for c in contracts:
        supplier = c.get("supplier_name")
        category = c.get("category")
        subcategory = c.get("subcategory")
        row_type = str(c.get("row_type") or "renewal")
        key = _merge_key(supplier_name=supplier, category=category, subcategory=subcategory)
        spend = spend_agg.get(key, {})
        metric = metrics_by_key.get(key, {})
        merged_spend = c.get("estimated_spend_usd") or spend.get("estimated_spend_usd") or 0.0
        fused.append(
            {
                "row_type": row_type,
                "category": category or "Uncategorized",
                "subcategory": subcategory,
                "supplier_name": supplier,
                "contract_id": c.get("contract_id") if row_type == "renewal" else None,
                "contract_end_date": c.get("contract_end_date"),
                "months_to_expiry": c.get("months_to_expiry"),
                "estimated_spend_usd": round(float(merged_spend), 2),
                "request_title": c.get("request_title"),
                "implementation_timeline_months": c.get("implementation_timeline_months"),
                "rss_score": c.get("rss_score") if c.get("rss_score") is not None else metric.get("rss_score"),
                "preferred_supplier_status": (
                    c.get("preferred_supplier_status")
                    if c.get("preferred_supplier_status")
                    else metric.get("preferred_supplier_status")
                ),
            }
        )
        seen_keys.add(key)

    # Spend-led opportunities where no contract-led row exists.
    for key, s in spend_agg.items():
        if key in seen_keys:
            continue
        metric = metrics_by_key.get(key, {})
        fused.append(
            {
                "row_type": "new_business",
                "category": s.get("category") or "Uncategorized",
                "subcategory": s.get("subcategory"),
                "supplier_name": s.get("supplier_name"),
                "request_title": f"Aggregated spend scan ({int(s.get('row_count', 0))} lines)",
                "estimated_spend_usd": round(float(s.get("estimated_spend_usd") or 0.0), 2),
                "rss_score": metric.get("rss_score"),
                "preferred_supplier_status": metric.get("preferred_supplier_status"),
            }
        )
        seen_keys.add(key)

    # Metrics-only rows as low-confidence candidates (spend may default invalid and need review).
    for key, m in metrics_by_key.items():
        if key in seen_keys:
            continue
        fused.append(
            {
                "row_type": "new_business",
                "category": m.get("category") or "Uncategorized",
                "subcategory": m.get("subcategory"),
                "supplier_name": m.get("supplier_name"),
                "request_title": "Metrics-only scan candidate",
                "estimated_spend_usd": 0.0,
                "rss_score": m.get("rss_score"),
                "preferred_supplier_status": m.get("preferred_supplier_status"),
            }
        )

    notes.append(
        "Bundle scan fused contract + spend + supplier metrics into deduplicated candidates "
        "(contract-led first, then spend-led aggregates, then metrics-only)."
    )
    notes.append(f"Fused candidates: {len(fused)} from {sum(len(v) for v in rows_by_file.values())} raw rows.")
    return fused, notes


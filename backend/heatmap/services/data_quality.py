"""
Lightweight data-quality flags for heatmap opportunities (expectation-setting, not MDM).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def warnings_for_opportunity(row: Dict[str, Any], category_cards_keys: Optional[List[str]] = None) -> List[str]:
    """
    Return human-readable warning strings for suspicious or missing inputs.
    `category_cards_keys` — known categories from category_cards.json (optional).
    """
    out: List[str] = []
    cat = (row.get("category") or "").strip()
    if not cat:
        out.append("Missing category")
    elif category_cards_keys is not None and cat not in category_cards_keys:
        out.append(f"Category not in category cards: {cat}")

    sub = row.get("subcategory")
    if sub is not None and str(sub).strip() == "":
        out.append("Empty subcategory")

    spend = row.get("estimated_spend_usd")
    if spend is not None and float(spend) <= 0:
        out.append("Estimated spend is zero or negative")

    sn = row.get("supplier_name")
    if sn is None or (isinstance(sn, str) and not sn.strip()):
        if row.get("source") == "intake":
            out.append("No supplier name (new request)")

    # Batch rows: contract expiry urgency uses contract data — flag if no contract id but scores imply contract path
    cid = row.get("contract_id")
    if cid and row.get("eus_score") is None:
        out.append("Contract-linked row missing expiry urgency (EUS)")

    return out

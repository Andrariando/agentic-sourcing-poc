"""
Deterministic scoring helpers aligned with:
Agentic AI Sourcing Prioritization Framework (IT Infrastructure).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# Strategic Alignment Score by preferred-supplier tier (0–10 scale)
SAS_BY_STATUS: Dict[str, float] = {
    "preferred": 10.0,
    "straightpo": 10.0,
    "straight_to_po": 10.0,
    "straight-to-po": 10.0,
    "allowed": 7.0,
    "nonpreferred": 3.0,
    "non_preferred": 3.0,
    "non-preferred": 3.0,
}


def eus_from_months_to_expiry(months: float) -> float:
    """Expiry Urgency Score from framework §4 (months to expiry)."""
    if months <= 0:
        return 10.0
    if months <= 3:
        return 10.0
    if months <= 6:
        return 9.0
    if months <= 12:
        return 8.0
    if months <= 18:
        return 5.0
    return 2.0


def ius_from_implementation_months(months: float) -> float:
    """Implementation Urgency Score from framework §5."""
    if months < 3:
        return 10.0
    if months < 6:
        return 8.0
    if months <= 12:
        return 6.0
    return 3.0


def fis_from_contract_value(contract_value: float, max_in_category: float) -> float:
    """FIS = (Contract Value / max TCV in category) × 10"""
    if max_in_category <= 0:
        return 0.0
    return min(10.0, (contract_value / max_in_category) * 10.0)


def es_from_estimated_spend(estimated: float, max_in_pipeline: float) -> float:
    """ES = (Estimated Spend / max in request pipeline) × 10"""
    if max_in_pipeline <= 0:
        return 0.0
    return min(10.0, (estimated / max_in_pipeline) * 10.0)


def csis_from_category_spend(category_spend: float, max_category_spend: float) -> float:
    """CSIS = (category spend / max category spend) × 10"""
    if max_category_spend <= 0:
        return 0.0
    return min(10.0, (category_spend / max_category_spend) * 10.0)


def scs_from_supplier_share_pct(share_pct: float) -> float:
    """Spend Concentration Score from supplier share of category spend (%)."""
    if share_pct > 30:
        return 10.0
    if share_pct >= 20:
        return 7.0
    if share_pct >= 10:
        return 5.0
    return 2.0


def rss_from_supplier_risk_raw(raw: Any) -> float:
    """
    Framework: RSS = Supplier Risk Score from supplier metrics.
    Synthetic generator uses ~1–5 scale; map to 0–10. If already >5, cap at 10.
    """
    try:
        v = float(raw)
    except (TypeError, ValueError):
        v = 3.0
    if v <= 5.5:
        return min(10.0, round(v * 2.0, 1))
    return min(10.0, round(v, 1))


def _normalize_status_token(raw: str) -> str:
    s = raw.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "straight_to_po": "straightpo",
        "straighttopo": "straightpo",
        "non_preferred": "nonpreferred",
        "nonpreferred_supplier": "nonpreferred",
        "preferred_supplier": "preferred",
        "allowed_supplier": "allowed",
    }
    return aliases.get(s, s)


def resolve_preferred_status_key(
    category: str,
    supplier_name: Optional[str],
    explicit_status: Optional[str],
    category_cards: Dict[str, Any],
) -> str:
    """Return a normalized key for SAS_BY_STATUS lookup."""
    if explicit_status:
        return _normalize_status_token(str(explicit_status))
    cat_card = category_cards.get(category) or category_cards.get(category.strip(), {})
    by_supplier = cat_card.get("supplier_preferred_status") or {}
    if supplier_name and supplier_name in by_supplier:
        return _normalize_status_token(str(by_supplier[supplier_name]))
    default = cat_card.get("default_preferred_status", "allowed")
    return _normalize_status_token(str(default))


def sas_from_category_cards(
    category: str,
    supplier_name: Optional[str],
    is_new_request: bool,
    explicit_status: Optional[str],
    category_cards: Dict[str, Any],
) -> tuple[float, str]:
    """
    SAS from Category Cards (preferred supplier guidance).
    New requests without status fall back to category_strategy_sas then default table.
    """
    cat_card = category_cards.get(category) or category_cards.get((category or "").strip(), {}) or {}
    key = resolve_preferred_status_key(category, supplier_name, explicit_status, category_cards)
    if key in SAS_BY_STATUS:
        score = SAS_BY_STATUS[key]
        return score, f"SAS {score} from preferred status '{key}' (category card)."
    fallback = float(cat_card.get("category_strategy_sas", 7.0))
    if key in ("unknown", "tbd", ""):
        return fallback, f"SAS {fallback} from category strategy default (unclassified)."
    return fallback, f"SAS {fallback} from category strategy (unmapped status '{key}')."


def months_until_expiry_from_iso(exp_date_str: str, today) -> Optional[float]:
    from datetime import datetime

    try:
        exp = datetime.strptime(exp_date_str, "%Y-%m-%d")
    except ValueError:
        return None
    delta = exp - today
    return max(0.0, delta.days / 30.437)  # mean month length

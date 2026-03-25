"""
Build heatmap_context from synthetic CSVs + category cards (framework-aligned).
Used by batch pipeline and intake preview/submit.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

from backend.heatmap.seed_synthetic_data import DATA_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CATEGORY_CARDS_PATH = PROJECT_ROOT / "data" / "heatmap" / "category_cards.json"


def fis_contract_value_field() -> str:
    """Framework 'Contract Value': default TCV; set HEATMAP_FIS_USE_ACV=1 for ACV."""
    if os.environ.get("HEATMAP_FIS_USE_ACV", "").lower() in ("1", "true", "yes"):
        return "ACV (Annual Contract Value USD)"
    return "TCV (Total Contract Value USD)"


def load_category_cards() -> dict:
    if CATEGORY_CARDS_PATH.is_file():
        with open(CATEGORY_CARDS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"IT Infrastructure": {"default_preferred_status": "allowed", "category_strategy_sas": 7.0}}


def load_supplier_metrics_map() -> dict[str, dict]:
    path = DATA_DIR / "synthetic_supplier_metrics.csv"
    if not path.is_file():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["Supplier"]] = row
    return out


def load_spend_aggregates() -> tuple[dict[str, list], dict[str, float], dict[str, float]]:
    """Returns spend_by_supplier, category_spend_total, supplier_category_spend."""
    spend_by_supplier: dict[str, list] = defaultdict(list)
    category_spend_total: dict[str, float] = defaultdict(float)
    supplier_category_spend: dict[str, float] = defaultdict(float)
    path = DATA_DIR / "synthetic_spend.csv"
    if not path.is_file():
        return {}, {}, {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                row["PO Spend (USD)"] = float(row["PO Spend (USD)"])
            except (TypeError, ValueError):
                row["PO Spend (USD)"] = 0.0
            supp = row["Supplier"]
            cat = row.get("Category") or "IT Infrastructure"
            spend_by_supplier[supp].append(row)
            category_spend_total[cat] += row["PO Spend (USD)"]
            supplier_category_spend[f"{supp}||{cat}"] += row["PO Spend (USD)"]
    return dict(spend_by_supplier), dict(category_spend_total), dict(supplier_category_spend)


def load_max_contract_value_by_category() -> dict[str, float]:
    fis_key = fis_contract_value_field()
    max_by_cat: dict[str, float] = defaultdict(float)
    path = DATA_DIR / "synthetic_contracts.csv"
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cat = row.get("Category") or "IT Infrastructure"
            try:
                val = float(row.get(fis_key, 0) or row.get("TCV (Total Contract Value USD)", 0) or 0)
            except (TypeError, ValueError):
                val = 0.0
            max_by_cat[cat] = max(max_by_cat[cat], val)
    return dict(max_by_cat)


def build_heatmap_context(
    *,
    max_estimated_spend_pipeline: float = 1.0,
    extra: dict | None = None,
) -> dict:
    """
    Assemble heatmap_context for agents and intake scoring.
    max_estimated_spend_pipeline: max ES denominator for PS_new (batch slice or intakes + candidate).
    """
    category_cards = load_category_cards()
    _, category_spend_total, supplier_category_spend = load_spend_aggregates()
    max_tcv_by_category = load_max_contract_value_by_category()
    max_category_spend = max(category_spend_total.values()) if category_spend_total else 0.0

    ctx = {
        "max_tcv_by_category": max_tcv_by_category,
        "category_spend_total": category_spend_total,
        "supplier_category_spend": supplier_category_spend,
        "max_category_spend": max_category_spend,
        "max_estimated_spend_pipeline": max(1.0, float(max_estimated_spend_pipeline or 0.0)),
        "category_cards": category_cards,
        "fis_contract_value_field": fis_contract_value_field(),
    }
    if extra:
        ctx.update(extra)
    return ctx

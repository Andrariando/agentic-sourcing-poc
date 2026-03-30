"""
Persist category card patches to data/heatmap/category_cards.json (merge, atomic write).
Used by demo flow: upload policy text → extract patch → apply → re-run scoring pipeline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from backend.heatmap.context_builder import CATEGORY_CARDS_PATH, category_cards_fingerprint
from backend.heatmap.services.heatmap_copilot import _validate_category_patch


def apply_category_cards_patch(
    category: str,
    patch: Dict[str, Any],
    *,
    cards_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Merge validated patch into the category entry and write JSON atomically.
    supplier_preferred_status keys are merged; other keys overwrite.
    """
    cat = (category or "").strip()
    if not cat:
        raise ValueError("category is required")
    if not patch:
        raise ValueError("proposed_patch must not be empty")

    validated = _validate_category_patch(patch)
    if not validated:
        raise ValueError("proposed_patch contained no valid keys after validation")

    path = cards_path or CATEGORY_CARDS_PATH
    if not path.is_file():
        raise FileNotFoundError(f"category_cards.json not found: {path}")

    with open(path, encoding="utf-8") as f:
        cards: Dict[str, Any] = json.load(f)

    entry: Dict[str, Any] = dict(cards.get(cat) or {})
    for k, v in validated.items():
        if k == "supplier_preferred_status" and isinstance(v, dict):
            base = entry.get("supplier_preferred_status") or {}
            if not isinstance(base, dict):
                base = {}
            merged = {**base, **v}
            entry["supplier_preferred_status"] = merged
        else:
            entry[k] = v

    cards[cat] = entry

    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(cards, indent=2, ensure_ascii=False) + "\n"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)

    return {
        "success": True,
        "category": cat,
        "merged_card": entry,
        "category_cards_meta": category_cards_fingerprint(),
    }

"""
Per-category scoring weights stored inside category_cards.json under `scoring_mix`.

Humans can use long, self-explanatory keys; we map them to internal w_* keys and
renormalize each group (new request vs renewal) to sum to 1.

Meta keys (notes for readers) are ignored by the engine — see _is_meta_only_key.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from backend.heatmap.services.learned_weights import (
    DEFAULT_WEIGHTS_FLAT,
    PS_CONTRACT_KEYS,
    PS_NEW_KEYS,
    normalize_full,
)

# --- Human-readable keys in JSON → internal keys (same as learned_weights / supervisor) ---

NEW_REQUEST_LABEL_MAP: Dict[str, str] = {
    # Plain-English names (recommended for people editing the file)
    "implementation_urgency_IUS": "w_ius",
    "estimated_spend_ES": "w_es",
    "category_spend_importance_CSIS": "w_csis",
    "strategic_alignment_SAS": "w_sas_new",
    # Short aliases (optional)
    "w_ius": "w_ius",
    "w_es": "w_es",
    "w_csis": "w_csis",
    "w_sas_new": "w_sas_new",
}

RENEWAL_LABEL_MAP: Dict[str, str] = {
    "expiry_urgency_EUS": "w_eus",
    "financial_impact_FIS": "w_fis",
    "supplier_risk_RSS": "w_rss",
    "spend_concentration_SCS": "w_scs",
    # Same human label as new-request block, but here it maps to renewal SAS weight
    "strategic_alignment_SAS": "w_sas_contract",
    "w_eus": "w_eus",
    "w_fis": "w_fis",
    "w_rss": "w_rss",
    "w_scs": "w_scs",
    "w_sas_contract": "w_sas_contract",
}

# Alternative block headings inside `scoring_mix` (any one can hold the weights dict)
_NEW_BLOCK_ALIASES = (
    "new_sourcing_request",
    "new_request",
    "ps_new",
    "when_this_is_a_new_request",
)

_RENEWAL_BLOCK_ALIASES = (
    "existing_contract_renewal",
    "renewal",
    "ps_contract",
    "contract",
    "when_this_is_a_renewal",
)

ALL_SCORING_MIX_BLOCK_KEYS = frozenset(_NEW_BLOCK_ALIASES) | frozenset(_RENEWAL_BLOCK_ALIASES)


def _is_meta_only_key(key: str) -> bool:
    """Keys that are documentation-only and must not be parsed as weights."""
    k = (key or "").strip().lower()
    if not k:
        return True
    if k.startswith("_"):
        return True
    return k in {
        "plain_english",
        "read_me",
        "readme",
        "description",
        "help",
        "title",
        "what_this_is",
        "notes",
        "note",
    }


def _find_block(mix: Mapping[str, Any], aliases: Tuple[str, ...]) -> Optional[Dict[str, Any]]:
    for name in aliases:
        raw = mix.get(name)
        if isinstance(raw, dict) and raw:
            return dict(raw)
    return None


def _parse_labeled_block(
    block: Mapping[str, Any],
    label_map: Dict[str, str],
    internal_keys: Tuple[str, ...],
) -> Optional[Dict[str, float]]:
    """Return internal_key -> weight for keys present in block; None if nothing valid."""
    out: Dict[str, float] = {}
    for raw_k, raw_v in block.items():
        sk = str(raw_k).strip()
        if _is_meta_only_key(sk):
            continue
        internal = label_map.get(sk)
        if internal not in internal_keys:
            continue
        try:
            out[internal] = float(raw_v)
        except (TypeError, ValueError):
            continue
    return out or None


def _apply_group(
    flat: Dict[str, float],
    group_keys: Tuple[str, str, ...],
    parsed: Optional[Dict[str, float]],
) -> None:
    if not parsed:
        return
    for k in group_keys:
        if k in parsed:
            flat[k] = parsed[k]


def extract_scoring_mix_from_card(category_card: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the scoring_mix dict from a category card, or None."""
    if not category_card or not isinstance(category_card, Mapping):
        return None
    mix = category_card.get("scoring_mix")
    if isinstance(mix, dict) and mix:
        return dict(mix)
    return None


def apply_category_scoring_overlay(
    flat_weights: Dict[str, float],
    category_card: Optional[Mapping[str, Any]],
) -> Dict[str, float]:
    """
    Start from normalized global/learned weights; if the category card defines
    `scoring_mix`, replace the corresponding PS_new and/or renewal groups, then renormalize.
    """
    flat = normalize_full(flat_weights)
    mix = extract_scoring_mix_from_card(category_card)
    if not mix:
        return flat

    new_block = _find_block(mix, _NEW_BLOCK_ALIASES)
    renewal_block = _find_block(mix, _RENEWAL_BLOCK_ALIASES)

    new_parsed = (
        _parse_labeled_block(new_block, NEW_REQUEST_LABEL_MAP, PS_NEW_KEYS) if new_block else None
    )
    renewal_parsed = (
        _parse_labeled_block(renewal_block, RENEWAL_LABEL_MAP, PS_CONTRACT_KEYS)
        if renewal_block
        else None
    )

    _apply_group(flat, PS_NEW_KEYS, new_parsed)
    _apply_group(flat, PS_CONTRACT_KEYS, renewal_parsed)
    return normalize_full(flat)


def validate_scoring_mix_for_patch(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Validate scoring_mix from a category-card patch. Returns a clean dict to merge, or None.
    Unknown block or weight keys raise ValueError so typos are caught early.
    """
    if not isinstance(raw, dict):
        raise ValueError("scoring_mix must be an object.")
    cleaned: Dict[str, Any] = {}

    for k, v in raw.items():
        sk = str(k).strip()
        if _is_meta_only_key(sk):
            if isinstance(v, str):
                cleaned[sk] = v.strip()
            continue
        if sk not in ALL_SCORING_MIX_BLOCK_KEYS:
            raise ValueError(
                f"Unknown scoring_mix block '{sk}'. "
                f"Use one of: {', '.join(sorted(ALL_SCORING_MIX_BLOCK_KEYS))}"
            )
        if not isinstance(v, dict):
            raise ValueError(f"scoring_mix.{sk} must be an object.")
        label_map = NEW_REQUEST_LABEL_MAP if sk in _NEW_BLOCK_ALIASES else RENEWAL_LABEL_MAP
        inner: Dict[str, Any] = {}
        for ik, iv in v.items():
            sik = str(ik).strip()
            if _is_meta_only_key(sik):
                if isinstance(iv, str):
                    inner[sik] = iv.strip()
                continue
            if sik not in label_map:
                allowed = ", ".join(sorted(label_map.keys()))
                raise ValueError(
                    f"Unknown weight key '{sik}' under scoring_mix.{sk}. "
                    f"Allowed labels: {allowed}"
                )
            try:
                inner[sik] = float(iv)
            except (TypeError, ValueError) as e:
                raise ValueError(f"scoring_mix.{sk}.{sik} must be a number.") from e
        weight_like = {ik: iv for ik, iv in inner.items() if not _is_meta_only_key(str(ik))}
        if not weight_like:
            raise ValueError(f"scoring_mix.{sk}: add at least one weight (see allowed labels).")
        cleaned[sk] = inner

    if not cleaned:
        return None
    if not any(k in ALL_SCORING_MIX_BLOCK_KEYS for k in cleaned):
        return None

    probe_flat = normalize_full(dict(DEFAULT_WEIGHTS_FLAT))
    dummy_card = {"scoring_mix": cleaned}
    apply_category_scoring_overlay(probe_flat, dummy_card)
    return cleaned

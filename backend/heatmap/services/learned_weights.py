"""
Persistent heatmap scoring weights with small updates from human tier feedback (gradient-style
on the linear total) plus optional manual deltas. Weights are stored as a flat dict and
normalized per formula group (PS_new vs PS_contract).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from backend.heatmap.persistence.heatmap_models import HeatmapLearnedWeights, Opportunity

PS_NEW_KEYS = ("w_ius", "w_es", "w_csis", "w_sas_new")
PS_CONTRACT_KEYS = ("w_eus", "w_fis", "w_rss", "w_scs", "w_sas_contract")

DEFAULT_WEIGHTS_FLAT: Dict[str, float] = {
    "w_ius": 0.30,
    "w_es": 0.30,
    "w_csis": 0.25,
    "w_sas_new": 0.15,
    "w_eus": 0.30,
    "w_fis": 0.25,
    "w_rss": 0.20,
    "w_scs": 0.15,
    "w_sas_contract": 0.10,
}

TIER_TO_TARGET_TOTAL = {"T1": 9.0, "T2": 7.0, "T3": 5.0, "T4": 2.5}


def _enabled() -> bool:
    return (os.getenv("HEATMAP_WEIGHT_LEARNING") or "1").lower() not in ("0", "false", "no", "off")


def _learning_rate() -> float:
    try:
        return max(0.001, min(0.15, float(os.getenv("HEATMAP_WEIGHT_LR", "0.04"))))
    except (TypeError, ValueError):
        return 0.04


def _clone_defaults() -> Dict[str, float]:
    return dict(DEFAULT_WEIGHTS_FLAT)


def _normalize_keys(w: Dict[str, float], keys: Tuple[str, ...]) -> None:
    s = sum(max(0.0, float(w.get(k, 0.0) or 0.0)) for k in keys)
    if s <= 1e-9:
        for k in keys:
            w[k] = DEFAULT_WEIGHTS_FLAT[k]
        return
    for k in keys:
        w[k] = max(0.01, float(w.get(k, 0.0) or 0.0) / s)


def normalize_full(w: Dict[str, float]) -> Dict[str, float]:
    out = _clone_defaults()
    for k, v in (w or {}).items():
        if k in out:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                pass
    _normalize_keys(out, PS_NEW_KEYS)
    _normalize_keys(out, PS_CONTRACT_KEYS)
    return out


def get_learned_weights_row(session: Session) -> Optional[HeatmapLearnedWeights]:
    stmt = select(HeatmapLearnedWeights).where(HeatmapLearnedWeights.id == 1)
    return session.exec(stmt).first()


def load_learned_weights(session: Session) -> Dict[str, float]:
    row = get_learned_weights_row(session)
    if not row or not (row.weights_json or "").strip():
        return _clone_defaults()
    try:
        raw = json.loads(row.weights_json)
        if isinstance(raw, dict):
            return normalize_full(raw)
    except json.JSONDecodeError:
        pass
    return _clone_defaults()


def save_learned_weights(session: Session, weights: Dict[str, float]) -> None:
    normalized = normalize_full(weights)
    payload = json.dumps(normalized, sort_keys=True)
    row = get_learned_weights_row(session)
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(
            HeatmapLearnedWeights(
                id=1,
                weights_json=payload,
                updated_at=now,
            )
        )
    else:
        row.weights_json = payload
        row.updated_at = now
        session.add(row)


def weights_for_ps_new_intake(w: Dict[str, float]) -> Dict[str, float]:
    """Flat dict expected by ps_new_components (uses w_sas key)."""
    w = normalize_full(w)
    return {
        "w_ius": w["w_ius"],
        "w_es": w["w_es"],
        "w_csis": w["w_csis"],
        "w_sas": w["w_sas_new"],
    }


def merge_intake_ps_new_weights(
    session: Session,
    overrides: Optional[Dict[str, float]] = None,
    *,
    category_card: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Load learned weights, optional category card overlay, API overrides; return dict for ps_new_components."""
    from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay

    base = normalize_full(load_learned_weights(session))
    base = apply_category_scoring_overlay(base, category_card or {})
    if overrides:
        o = dict(overrides)
        if "w_sas" in o:
            base["w_sas_new"] = float(o.pop("w_sas"))
        for k, v in o.items():
            if k not in base:
                continue
            try:
                base[k] = float(v)
            except (TypeError, ValueError):
                pass
        base = normalize_full(base)
    return weights_for_ps_new_intake(base)


def weights_for_supervisor_state(w: Dict[str, float]) -> Dict[str, float]:
    """Single dict on HeatmapState['weights'] with distinct SAS keys per formula."""
    return normalize_full(w)


def _scores_vector_ps_new(opp: Opportunity) -> List[Tuple[str, float]]:
    return [
        ("w_ius", float(opp.ius_score or 0.0)),
        ("w_es", float(opp.es_score or 0.0)),
        ("w_csis", float(opp.csis_score or 0.0)),
        ("w_sas_new", float(opp.sas_score or 0.0)),
    ]


def _scores_vector_ps_contract(opp: Opportunity) -> List[Tuple[str, float]]:
    return [
        ("w_eus", float(opp.eus_score or 0.0)),
        ("w_fis", float(opp.fis_score or 0.0)),
        ("w_rss", float(opp.rss_score or 0.0)),
        ("w_scs", float(opp.scs_score or 0.0)),
        ("w_sas_contract", float(opp.sas_score or 0.0)),
    ]


def tier_from_total(total: float) -> str:
    if total >= 8.0:
        return "T1"
    if total >= 6.0:
        return "T2"
    if total >= 4.0:
        return "T3"
    return "T4"


def recompute_total_and_tier(opp: Opportunity, w: Dict[str, float]) -> Tuple[float, str]:
    w = normalize_full(w)
    if opp.contract_id is None:
        total = sum(w[k] * s for k, s in _scores_vector_ps_new(opp))
    else:
        total = sum(w[k] * s for k, s in _scores_vector_ps_contract(opp))
    total = round(max(0.0, min(10.0, total)), 2)
    return total, tier_from_total(total)


def _tier_target(tier: str) -> float:
    return float(TIER_TO_TARGET_TOTAL.get((tier or "T4").upper()[:2], 2.5))


def _apply_gradient_step(
    w: Dict[str, float],
    keys: Tuple[str, ...],
    scores: List[Tuple[str, float]],
    error: float,
) -> None:
    """One step: w_k += lr * error * s_k / (sum |s| + eps), then group renormalize."""
    lr = _learning_rate()
    denom = sum(abs(s[1]) for s in scores) + 1e-6
    for k, s in scores:
        if k not in keys:
            continue
        grad = error * (s / denom)
        w[k] = float(w.get(k, DEFAULT_WEIGHTS_FLAT[k])) + lr * grad
        w[k] = max(0.01, min(0.95, w[k]))
    _normalize_keys(w, keys)


def apply_manual_weight_deltas(w: Dict[str, float], deltas: Optional[Dict[str, float]]) -> Dict[str, float]:
    if not deltas:
        return w
    out = normalize_full(w)
    for k, dv in deltas.items():
        if k not in out:
            continue
        try:
            out[k] = float(out[k]) + float(dv)
        except (TypeError, ValueError):
            continue
    return normalize_full(out)


def apply_weight_overrides(w: Dict[str, float], overrides: Optional[Dict[str, float]]) -> Dict[str, float]:
    if not overrides:
        return normalize_full(w)
    out = normalize_full(w)
    for k, v in overrides.items():
        if k not in out:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return normalize_full(out)


def merge_weight_edits(
    w: Dict[str, float],
    overrides: Optional[Dict[str, float]] = None,
    deltas: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    out = apply_weight_overrides(w, overrides)
    return apply_manual_weight_deltas(out, deltas)


def update_weights_from_feedback(
    session: Session,
    opp: Opportunity,
    *,
    suggested_tier: str,
    weight_overrides: Optional[Dict[str, float]] = None,
    manual_deltas: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Load weights, apply optional overrides / deltas, then a small gradient step from tier error
    (target total minus current total using pre-update weights). Persist and return new dict.
    """
    from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay
    from backend.heatmap.context_builder import load_category_cards

    w = load_learned_weights(session)
    w = merge_weight_edits(w, weight_overrides, manual_deltas)

    if not _enabled():
        save_learned_weights(session, w)
        return w

    cards = load_category_cards()
    raw_c = cards.get((opp.category or "").strip()) or cards.get(opp.category or "")
    cdict = raw_c if isinstance(raw_c, dict) else {}
    w_display = apply_category_scoring_overlay(w, cdict)
    cur_total, _ = recompute_total_and_tier(opp, w_display)
    target = _tier_target(suggested_tier)
    error = max(-4.0, min(4.0, target - cur_total))

    if opp.contract_id is None:
        _apply_gradient_step(w, PS_NEW_KEYS, _scores_vector_ps_new(opp), error)
    else:
        _apply_gradient_step(w, PS_CONTRACT_KEYS, _scores_vector_ps_contract(opp), error)

    w = normalize_full(w)
    save_learned_weights(session, w)
    return w


def sync_opportunity_scores_after_weight_change(
    session: Session,
    opp: Opportunity,
    w: Dict[str, float],
    *,
    suggested_tier: Optional[str] = None,
) -> None:
    """Recompute total from components; keep human suggested tier when provided."""
    total, tier = recompute_total_and_tier(opp, w)
    opp.total_score = total
    st = (suggested_tier or "").strip().upper()
    if st in TIER_TO_TARGET_TOTAL:
        opp.tier = st
    else:
        opp.tier = tier
    opp.weights_used_json = json.dumps(
        {
            "effective_weights": normalize_full(w),
            "reconciled_tier": opp.tier,
            "recomputed_total": total,
            "note": "Weights = global learned + category_cards.json scoring_mix (if any) for this row's category.",
        },
        sort_keys=True,
    )
    session.add(opp)

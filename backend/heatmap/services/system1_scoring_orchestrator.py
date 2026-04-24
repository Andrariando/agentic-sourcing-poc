"""
System 1 scoring orchestrator for staged upload rows.

Computes score components with provenance:
- provided: value supplied in upload row
- derived: calculated from uploaded business fields
- defaulted: fallback default when neither provided nor derivable
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay
from backend.heatmap.context_builder import load_category_cards
from backend.heatmap.services.feedback_memory import apply_learning_nudge
from backend.heatmap.services.learned_weights import load_learned_weights, normalize_full
from backend.infrastructure.storage_providers import get_heatmap_db
from backend.heatmap.scoring_framework import (
    eus_from_months_to_expiry,
    ius_from_implementation_months,
    sas_from_category_cards,
)


@dataclass
class ComponentResult:
    value: float
    confidence: float
    source_type: str  # provided | derived | defaulted
    evidence_refs: List[str]
    explanation: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "value": round(float(self.value), 2),
            "confidence": round(float(self.confidence), 2),
            "source_type": self.source_type,
            "evidence_refs": list(self.evidence_refs),
            "explanation": self.explanation,
        }


def _clamp_0_10(v: float) -> float:
    return max(0.0, min(10.0, float(v)))


def _tier(total: float) -> str:
    if total >= 8.0:
        return "T1"
    if total >= 6.0:
        return "T2"
    if total >= 4.0:
        return "T3"
    return "T4"


def _provided_or_none(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        s = str(raw).strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def _sas_component(row: Dict[str, Any], category_cards: Dict[str, Any]) -> ComponentResult:
    provided = _provided_or_none(row.get("sas_score"))
    if provided is not None:
        return ComponentResult(
            value=_clamp_0_10(provided),
            confidence=0.98,
            source_type="provided",
            evidence_refs=["upload_field:sas_score"],
            explanation="SAS supplied directly in uploaded row.",
        )
    sas, sas_note = sas_from_category_cards(
        str(row.get("category") or "Uncategorized"),
        row.get("supplier_name"),
        bool(row.get("row_type") == "new_business"),
        row.get("preferred_supplier_status"),
        category_cards,
    )
    return ComponentResult(
        value=_clamp_0_10(sas),
        confidence=0.78,
        source_type="derived",
        evidence_refs=["category_cards", "preferred_supplier_status"],
        explanation=f"SAS derived from category card policy. {sas_note}",
    )


def _rss_component(row: Dict[str, Any]) -> ComponentResult:
    provided = _provided_or_none(row.get("rss_score"))
    if provided is not None:
        return ComponentResult(
            value=_clamp_0_10(provided),
            confidence=0.98,
            source_type="provided",
            evidence_refs=["upload_field:rss_score"],
            explanation="RSS supplied directly in uploaded row.",
        )
    status = str(row.get("preferred_supplier_status") or "").strip().lower()
    if status in {"nonpreferred", "non_preferred", "non-preferred"}:
        v = 7.5
        why = "RSS derived from preferred_supplier_status=nonpreferred."
    elif status in {"preferred", "straightpo", "straight_to_po", "straight-to-po"}:
        v = 4.0
        why = "RSS derived from preferred_supplier_status=preferred."
    elif status in {"allowed"}:
        v = 5.5
        why = "RSS derived from preferred_supplier_status=allowed."
    else:
        v = 5.0
        why = "RSS defaulted because supplier risk evidence was unavailable."
        return ComponentResult(
            value=v,
            confidence=0.35,
            source_type="defaulted",
            evidence_refs=[],
            explanation=why,
        )
    return ComponentResult(
        value=v,
        confidence=0.7,
        source_type="derived",
        evidence_refs=["preferred_supplier_status"],
        explanation=why,
    )


def _scs_component(row: Dict[str, Any], max_spend: float) -> ComponentResult:
    provided = _provided_or_none(row.get("scs_score"))
    if provided is not None:
        return ComponentResult(
            value=_clamp_0_10(provided),
            confidence=0.98,
            source_type="provided",
            evidence_refs=["upload_field:scs_score"],
            explanation="SCS supplied directly in uploaded row.",
        )
    spend = _provided_or_none(row.get("estimated_spend_usd")) or 0.0
    if max_spend <= 0:
        return ComponentResult(
            value=5.0,
            confidence=0.35,
            source_type="defaulted",
            evidence_refs=[],
            explanation="SCS defaulted because spend normalization denominator was unavailable.",
        )
    ratio = spend / max_spend
    v = _clamp_0_10(ratio * 10.0)
    return ComponentResult(
        value=v,
        confidence=0.72,
        source_type="derived",
        evidence_refs=["estimated_spend_usd", "batch_max_spend"],
        explanation="SCS derived as normalized spend concentration proxy within upload batch.",
    )


def _window_from_expiry(months_to_expiry: Optional[float]) -> str:
    m = float(months_to_expiry) if months_to_expiry is not None else 9.0
    if m <= 3:
        return "Critical (<3 mo)"
    if m <= 6:
        return "High (3–6 mo)"
    if m <= 12:
        return "Standard (6–12 mo)"
    return "Planned (>12 mo)"


def score_row(
    row: Dict[str, Any],
    *,
    max_renewal_spend: float,
    max_new_spend: float,
    category_cards: Optional[Dict[str, Any]] = None,
    effective_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    cards = category_cards or load_category_cards()
    row_type = str(row.get("row_type") or "new_business")
    spend = _provided_or_none(row.get("estimated_spend_usd")) or 0.0
    components: Dict[str, ComponentResult] = {}
    readiness_warnings: List[str] = []

    if row_type == "renewal":
        months = _provided_or_none(row.get("months_to_expiry"))
        if months is None:
            eus = ComponentResult(
                value=5.0,
                confidence=0.3,
                source_type="defaulted",
                evidence_refs=[],
                explanation="EUS defaulted because months_to_expiry was unavailable.",
            )
        else:
            eus = ComponentResult(
                value=_clamp_0_10(eus_from_months_to_expiry(months)),
                confidence=0.85,
                source_type="derived",
                evidence_refs=["months_to_expiry"],
                explanation="EUS derived from months_to_expiry using scoring framework bands.",
            )
        if max_renewal_spend > 0:
            fis_val = _clamp_0_10((spend / max_renewal_spend) * 10.0)
            fis = ComponentResult(
                value=fis_val,
                confidence=0.8,
                source_type="derived",
                evidence_refs=["estimated_spend_usd", "batch_max_renewal_spend"],
                explanation="FIS derived as normalized spend impact within renewal upload batch.",
            )
        else:
            fis = ComponentResult(
                value=5.0,
                confidence=0.3,
                source_type="defaulted",
                evidence_refs=[],
                explanation="FIS defaulted because spend denominator was unavailable.",
            )
        rss = _rss_component(row)
        scs = _scs_component(row, max_renewal_spend)
        sas = _sas_component(row, cards)
        components = {"eus_score": eus, "fis_score": fis, "rss_score": rss, "scs_score": scs, "sas_score": sas}
        ew = normalize_full(effective_weights or {})
        weights = {
            "w_eus": float(ew.get("w_eus", 0.30)),
            "w_fis": float(ew.get("w_fis", 0.25)),
            "w_rss": float(ew.get("w_rss", 0.20)),
            "w_scs": float(ew.get("w_scs", 0.15)),
            "w_sas_contract": float(ew.get("w_sas_contract", 0.10)),
        }
        total = round(
            (eus.value * weights["w_eus"])
            + (fis.value * weights["w_fis"])
            + (rss.value * weights["w_rss"])
            + (scs.value * weights["w_scs"])
            + (sas.value * weights["w_sas_contract"]),
            2,
        )
        formula_tail = (
            f"EUS({eus.value})*{weights['w_eus']} + FIS({fis.value})*{weights['w_fis']} + "
            f"RSS({rss.value})*{weights['w_rss']} + SCS({scs.value})*{weights['w_scs']} + "
            f"SAS({sas.value})*{weights['w_sas_contract']}"
        )
        action_window = _window_from_expiry(months)
    else:
        impl = _provided_or_none(row.get("implementation_timeline_months"))
        if impl is None:
            ius = ComponentResult(
                value=6.0,
                confidence=0.35,
                source_type="defaulted",
                evidence_refs=[],
                explanation="IUS defaulted because implementation_timeline_months was unavailable.",
            )
        else:
            ius = ComponentResult(
                value=_clamp_0_10(ius_from_implementation_months(impl)),
                confidence=0.86,
                source_type="derived",
                evidence_refs=["implementation_timeline_months"],
                explanation="IUS derived from implementation timeline using scoring framework bands.",
            )
        if max_new_spend > 0:
            es = ComponentResult(
                value=_clamp_0_10((spend / max_new_spend) * 10.0),
                confidence=0.8,
                source_type="derived",
                evidence_refs=["estimated_spend_usd", "batch_max_new_spend"],
                explanation="ES derived as normalized estimated spend within new-business upload batch.",
            )
        else:
            es = ComponentResult(
                value=5.0,
                confidence=0.3,
                source_type="defaulted",
                evidence_refs=[],
                explanation="ES defaulted because spend denominator was unavailable.",
            )
        # CSIS can be replaced later with enterprise category spend ingestion.
        csis = ComponentResult(
            value=_clamp_0_10((es.value * 0.7) + 1.5),
            confidence=0.55,
            source_type="derived",
            evidence_refs=["estimated_spend_usd"],
            explanation="CSIS derived from spend proxy pending full category spend feed integration.",
        )
        sas = _sas_component(row, cards)
        components = {"ius_score": ius, "es_score": es, "csis_score": csis, "sas_score": sas}
        ew = normalize_full(effective_weights or {})
        weights = {
            "w_ius": float(ew.get("w_ius", 0.30)),
            "w_es": float(ew.get("w_es", 0.30)),
            "w_csis": float(ew.get("w_csis", 0.25)),
            "w_sas_new": float(ew.get("w_sas_new", 0.15)),
        }
        total = round(
            (ius.value * weights["w_ius"])
            + (es.value * weights["w_es"])
            + (csis.value * weights["w_csis"])
            + (sas.value * weights["w_sas_new"]),
            2,
        )
        formula_tail = (
            f"IUS({ius.value})*{weights['w_ius']} + ES({es.value})*{weights['w_es']} + "
            f"CSIS({csis.value})*{weights['w_csis']} + SAS({sas.value})*{weights['w_sas_new']}"
        )
        action_window = None

    _delta, learning_note, nudged_total, nudged_tier = apply_learning_nudge(
        category=str(row.get("category") or ""),
        subcategory=row.get("subcategory"),
        supplier_name=row.get("supplier_name"),
        is_new=(row_type != "renewal"),
        baseline_summary=f"Baseline weighted total {total:.2f}. {formula_tail}",
        base_total=float(total),
        weights=weights,
    )

    if spend <= 0:
        readiness_warnings.append("Non-positive spend prevents reliable score.")
    for name, comp in components.items():
        if comp.source_type == "defaulted":
            readiness_warnings.append(f"{name} used fallback default.")
        if comp.confidence < 0.5:
            readiness_warnings.append(f"{name} confidence is low ({comp.confidence:.2f}).")

    readiness_status = "ready"
    if readiness_warnings:
        readiness_status = "ready_with_warnings"
    if spend <= 0:
        readiness_status = "needs_review"

    avg_conf = sum(c.confidence for c in components.values()) / max(1, len(components))
    return {
        "components": {k: v.as_dict() for k, v in components.items()},
        "weights_used": weights,
        "total_score": float(nudged_total),
        "tier": str(nudged_tier or _tier(total)),
        "confidence": round(avg_conf, 2),
        "readiness_status": readiness_status,
        "readiness_warnings": readiness_warnings,
        "recommended_action_window": action_window,
        "learning_note": learning_note,
    }


def _derive_completeness_annotations(row: Dict[str, Any]) -> Dict[str, Any]:
    components = row.get("score_components") or {}
    defaulted = sorted(
        [
            name
            for name, meta in components.items()
            if isinstance(meta, dict) and str(meta.get("source_type") or "") == "defaulted"
        ]
    )
    low_conf = sorted(
        [
            name
            for name, meta in components.items()
            if isinstance(meta, dict) and float(meta.get("confidence") or 0.0) < 0.5
        ]
    )
    spend = float(row.get("estimated_spend_usd") or 0.0)
    supplier = str(row.get("supplier_name") or "").strip()
    category = str(row.get("category") or "").strip()
    row_type = str(row.get("row_type") or "")
    months_to_expiry = row.get("months_to_expiry")
    contract_end_date = row.get("contract_end_date")

    missing_critical: List[str] = []
    if spend <= 0:
        missing_critical.append("estimated_spend_usd")
    if not supplier:
        missing_critical.append("supplier_name")
    if not category:
        missing_critical.append("category")
    if row_type == "renewal" and months_to_expiry is None and contract_end_date is None:
        missing_critical.append("months_to_expiry_or_contract_end_date")

    # Heuristic completeness score (0-100) for ranking and triage.
    score = 100.0
    score -= 18.0 * len(missing_critical)
    score -= 10.0 * len(defaulted)
    score -= 6.0 * len(low_conf)
    score = max(0.0, min(100.0, score))

    suggested_actions: List[Dict[str, str]] = []
    if "scs_score" in defaulted:
        suggested_actions.append(
            {
                "action": "impute_scs_from_supplier_spend_share",
                "reason": "SCS defaulted; no reliable supplier/category concentration evidence.",
            }
        )
    if "rss_score" in defaulted:
        suggested_actions.append(
            {
                "action": "impute_rss_from_supplier_parent_or_status",
                "reason": "RSS defaulted; supplier risk data missing from fused evidence.",
            }
        )
    if "eus_score" in defaulted and row_type == "renewal":
        suggested_actions.append(
            {
                "action": "derive_expiry_from_contract_end_date",
                "reason": "Renewal urgency defaulted; provide expiry date or months_to_expiry.",
            }
        )
    if spend <= 0:
        suggested_actions.append(
            {
                "action": "provide_positive_spend_or_contract_value",
                "reason": "Non-positive spend blocks reliable prioritization.",
            }
        )
    if not supplier:
        suggested_actions.append(
            {
                "action": "resolve_supplier_identity_mapping",
                "reason": "Supplier is required for risk, concentration, and policy alignment.",
            }
        )
    return {
        "completeness_score": round(score, 1),
        "defaulted_components": defaulted,
        "low_confidence_components": low_conf,
        "missing_critical_fields": missing_critical,
        "suggested_actions": suggested_actions,
    }


def summarize_preview_completeness(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    readiness_counts: Dict[str, int] = {}
    defaulted_counts: Dict[str, int] = {}
    action_counts: Dict[str, int] = {}
    scoreables = 0
    for row in rows:
        readiness = str(row.get("readiness_status") or "unknown")
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1
        if bool(row.get("valid_for_approval")) and readiness != "needs_review":
            scoreables += 1
        for name in row.get("defaulted_components") or []:
            defaulted_counts[name] = defaulted_counts.get(name, 0) + 1
        for action in row.get("suggested_actions") or []:
            key = str((action or {}).get("action") or "").strip()
            if key:
                action_counts[key] = action_counts.get(key, 0) + 1
    top_actions = sorted(action_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    return {
        "total_rows_analyzed": len(rows),
        "scoreable_rows": scoreables,
        "readiness_breakdown": readiness_counts,
        "defaulted_component_counts": defaulted_counts,
        "imputation_action_candidates": [{"action": a, "rows": n} for a, n in top_actions],
    }


def enrich_rows_for_preview(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    renewals = [r for r in rows if str(r.get("row_type")) == "renewal"]
    new_rows = [r for r in rows if str(r.get("row_type")) != "renewal"]
    max_renewal_spend = max([float(r.get("estimated_spend_usd") or 0.0) for r in renewals], default=0.0)
    max_new_spend = max([float(r.get("estimated_spend_usd") or 0.0) for r in new_rows], default=0.0)
    cards = load_category_cards()
    try:
        session = get_heatmap_db().get_db_session()
        try:
            global_weights = normalize_full(load_learned_weights(session))
        finally:
            session.close()
    except Exception:
        global_weights = normalize_full({})
    out: List[Dict[str, Any]] = []
    for row in rows:
        category = str(row.get("category") or "").strip()
        raw_card = cards.get(category) or cards.get(str(row.get("category") or ""))
        category_card = raw_card if isinstance(raw_card, dict) else {}
        effective_weights = apply_category_scoring_overlay(global_weights, category_card)
        scored = score_row(
            row,
            max_renewal_spend=max_renewal_spend,
            max_new_spend=max_new_spend,
            category_cards=cards,
            effective_weights=effective_weights,
        )
        d = dict(row)
        d["score_components"] = scored["components"]
        d["weights_used"] = scored["weights_used"]
        d["computed_total_score"] = scored["total_score"]
        d["computed_tier"] = scored["tier"]
        d["computed_confidence"] = scored["confidence"]
        d["readiness_status"] = scored["readiness_status"]
        d["readiness_warnings"] = scored["readiness_warnings"]
        d["recommended_action_window"] = scored["recommended_action_window"]
        d.update(_derive_completeness_annotations(d))
        out.append(d)
    return out


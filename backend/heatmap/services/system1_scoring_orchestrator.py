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

from backend.heatmap.context_builder import load_category_cards
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
        weights = {"w_eus": 0.30, "w_fis": 0.25, "w_rss": 0.20, "w_scs": 0.15, "w_sas_contract": 0.10}
        total = round(
            (eus.value * 0.30) + (fis.value * 0.25) + (rss.value * 0.20) + (scs.value * 0.15) + (sas.value * 0.10),
            2,
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
        weights = {"w_ius": 0.30, "w_es": 0.30, "w_csis": 0.25, "w_sas_new": 0.15}
        total = round((ius.value * 0.30) + (es.value * 0.30) + (csis.value * 0.25) + (sas.value * 0.15), 2)
        action_window = None

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
        "total_score": total,
        "tier": _tier(total),
        "confidence": round(avg_conf, 2),
        "readiness_status": readiness_status,
        "readiness_warnings": readiness_warnings,
        "recommended_action_window": action_window,
    }


def enrich_rows_for_preview(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    renewals = [r for r in rows if str(r.get("row_type")) == "renewal"]
    new_rows = [r for r in rows if str(r.get("row_type")) != "renewal"]
    max_renewal_spend = max([float(r.get("estimated_spend_usd") or 0.0) for r in renewals], default=0.0)
    max_new_spend = max([float(r.get("estimated_spend_usd") or 0.0) for r in new_rows], default=0.0)
    cards = load_category_cards()
    out: List[Dict[str, Any]] = []
    for row in rows:
        scored = score_row(
            row,
            max_renewal_spend=max_renewal_spend,
            max_new_spend=max_new_spend,
            category_cards=cards,
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
        out.append(d)
    return out


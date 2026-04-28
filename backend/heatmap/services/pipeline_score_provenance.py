"""
Build score_provenance_json for LangGraph batch scoring and PS_new intake so DB rows match
the richness of `/api/system1/upload/approve` (score_components + scoring_inputs + weights_used).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.heatmap.agents.state import HeatmapState
from backend.heatmap.category_scoring_mix import apply_category_scoring_overlay
from backend.heatmap.scoring_framework import months_until_expiry_from_iso
from backend.heatmap.services.learned_weights import normalize_full


def weights_for_contract_row(state: HeatmapState, idx: int) -> Dict[str, float]:
    contract = state["contracts"][idx]
    w_global = normalize_full(state.get("weights") or {})
    card = contract.get("category_strategy") or {}
    return apply_category_scoring_overlay(w_global, card)


def parse_contract_end_datetime(details: Dict[str, Any]) -> Optional[datetime]:
    """Naive midnight UTC-style date from synthetic CSV `Expiration Date` when parseable."""
    iso = _parse_contract_end_iso(details)
    if not iso:
        return None
    return datetime.strptime(iso, "%Y-%m-%d")


def _parse_contract_end_iso(details: Dict[str, Any]) -> Optional[str]:
    exp = (details or {}).get("Expiration Date") or ""
    if not str(exp).strip():
        return None
    raw = str(exp).strip()[:10]
    try:
        datetime.strptime(raw, "%Y-%m-%d")
        return raw
    except ValueError:
        return None


def _contract_evidence_is_defaulted(evidence: str) -> bool:
    ev = (evidence or "").lower()
    needles = (
        "could not parse expiration",
        "no expiration date on contract record",
        "could not parse expiration date (and no interpreter",
        "no expiration date field; interpreter suggested",
        "no expiration date on contract",
    )
    return any(n in ev for n in needles)


def _component_dict(
    *,
    value: Optional[float],
    confidence: float,
    source_type: str,
    evidence_refs: List[str],
    explanation: str,
) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    expl = (explanation or "").replace("\n", " ").strip()
    if len(expl) > 480:
        expl = expl[:477] + "..."
    return {
        "value": round(float(value), 2),
        "confidence": round(float(confidence), 2),
        "source_type": source_type,
        "evidence_refs": list(evidence_refs),
        "explanation": expl,
    }


def build_langgraph_batch_provenance(state: HeatmapState, idx: int, scored: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aligns with main.py upload approve: score_components, scoring_inputs, weights_used,
    row metadata. Uses LangGraph agent evidence strings + canonical values from `scored`.
    """
    contract = state["contracts"][idx]
    spend_sig = state["spend_signals"][idx]
    contract_sig = state["contract_signals"][idx]
    strat_sig = state["strategy_signals"][idx]
    risk_sig = state["risk_signals"][idx]

    is_new = contract.get("contract_id") is None
    details = contract.get("contract_details") or {}
    weights_used = weights_for_contract_row(state, idx)

    score_components: Dict[str, Any] = {}

    if is_new:
        ius_ev = contract_sig.get("evidence") or ""
        spend_ev = spend_sig.get("evidence") or ""
        strat_ev = strat_sig.get("evidence") or ""

        score_components["ius_score"] = _component_dict(
            value=scored.get("ius_score"),
            confidence=0.86,
            source_type="derived",
            evidence_refs=["langgraph:contract_agent", "intake:implementation_timeline_months"],
            explanation=ius_ev,
        )
        score_components["es_score"] = _component_dict(
            value=scored.get("es_score"),
            confidence=0.84,
            source_type="derived",
            evidence_refs=["langgraph:spend_agent", "heatmap_context:max_estimated_spend_pipeline"],
            explanation=spend_ev,
        )
        score_components["csis_score"] = _component_dict(
            value=scored.get("csis_score"),
            confidence=0.83,
            source_type="derived",
            evidence_refs=["langgraph:spend_agent", "heatmap_context:category_spend_total"],
            explanation=spend_ev,
        )
        score_components["sas_score"] = _component_dict(
            value=scored.get("sas_score"),
            confidence=0.78,
            source_type="derived",
            evidence_refs=["langgraph:strategy_agent", "category_cards"],
            explanation=strat_ev,
        )
    else:
        cev = contract_sig.get("evidence") or ""
        st_eus, conf_eus = (
            ("defaulted", 0.35) if _contract_evidence_is_defaulted(cev) else ("derived", 0.85)
        )
        spend_ev = spend_sig.get("evidence") or ""
        risk_ev = risk_sig.get("evidence") or ""
        strat_ev = strat_sig.get("evidence") or ""

        score_components["eus_score"] = _component_dict(
            value=scored.get("eus_score"),
            confidence=conf_eus,
            source_type=st_eus,
            evidence_refs=["langgraph:contract_agent", "contract_details:Expiration Date"],
            explanation=cev,
        )
        score_components["fis_score"] = _component_dict(
            value=scored.get("fis_score"),
            confidence=0.84,
            source_type="derived",
            evidence_refs=["langgraph:spend_agent", "heatmap_context:max_tcv_by_category"],
            explanation=spend_ev,
        )
        score_components["rss_score"] = _component_dict(
            value=scored.get("rss_score"),
            confidence=0.8,
            source_type="derived",
            evidence_refs=["langgraph:risk_agent", "supplier_metrics:Supplier Risk Score"],
            explanation=risk_ev,
        )
        score_components["scs_score"] = _component_dict(
            value=scored.get("scs_score"),
            confidence=0.83,
            source_type="derived",
            evidence_refs=["langgraph:spend_agent", "heatmap_context:supplier_category_spend"],
            explanation=spend_ev,
        )
        score_components["sas_score"] = _component_dict(
            value=scored.get("sas_score"),
            confidence=0.78,
            source_type="derived",
            evidence_refs=["langgraph:strategy_agent", "category_cards"],
            explanation=strat_ev,
        )

    score_components = {k: v for k, v in score_components.items() if v is not None}

    ctx = state.get("heatmap_context") or {}
    category = contract.get("category") or ""
    supplier = contract.get("supplier_name")
    subcat = contract.get("subcategory")

    scoring_inputs: Dict[str, Any] = {
        "supplier_name": supplier,
        "category": category,
        "subcategory": subcat,
    }

    if is_new:
        scoring_inputs["estimated_spend_usd"] = contract.get("estimated_spend_usd")
        scoring_inputs["implementation_timeline_months"] = contract.get("implementation_timeline_months")
        scoring_inputs["preferred_supplier_status"] = contract.get("preferred_supplier_status")
    else:
        today = datetime.today()
        exp_iso = _parse_contract_end_iso(details)
        scoring_inputs["contract_end_date"] = exp_iso
        if exp_iso:
            m = months_until_expiry_from_iso(exp_iso, today)
            scoring_inputs["months_to_expiry"] = round(float(m), 3) if m is not None else None
        else:
            scoring_inputs["months_to_expiry"] = None
        po_sum = sum(float(s.get("PO Spend (USD)", 0) or 0) for s in contract.get("spend_data", []))
        scoring_inputs["aggregate_po_spend_usd"] = round(po_sum, 2)
        try:
            tcv = float(
                details.get(ctx.get("fis_contract_value_field") or "TCV (Total Contract Value USD)", 0)
                or details.get("TCV (Total Contract Value USD)", 0)
                or 0
            )
        except (TypeError, ValueError):
            tcv = 0.0
        scoring_inputs["tcv_usd"] = round(tcv, 2)

    return {
        "score_components": score_components,
        "row_type": "new_business" if is_new else "renewal",
        "source_kind": "langgraph_batch",
        "source_filename": "synthetic_contracts.csv",
        "supporting_artifacts": [
            {"kind": "batch_seed", "description": "Synthetic CSV matrix run via heatmap_graph (run_pipeline_init)."}
        ],
        "scoring_inputs": scoring_inputs,
        "weights_used": weights_used,
    }


def build_intake_ps_new_provenance(
    *,
    ctx: Dict[str, Any],
    merged_weights: Dict[str, float],
    scores: Dict[str, Optional[float]],
    category: str,
    subcategory: Optional[str],
    supplier_name: Optional[str],
    estimated_spend_usd: float,
    implementation_timeline_months: float,
    preferred_supplier_status: Optional[str],
    request_title: Optional[str],
) -> Dict[str, Any]:
    """PS_new intake — mirrors framework used in ps_new_components + upload approve shape."""
    from backend.heatmap.scoring_framework import sas_from_category_cards

    cards = ctx.get("category_cards") or {}
    _, sas_note = sas_from_category_cards(
        category,
        supplier_name,
        True,
        preferred_supplier_status,
        cards,
    )
    max_pipeline = float(ctx.get("max_estimated_spend_pipeline") or 1.0)
    cat_spend = float((ctx.get("category_spend_total") or {}).get(category) or 0.0)
    max_cat = float(ctx.get("max_category_spend") or 0.0)

    def _val(key: str) -> Optional[float]:
        v = scores.get(key)
        return float(v) if v is not None else None

    components: Dict[str, Any] = {}
    components["ius_score"] = _component_dict(
        value=_val("ius_score"),
        confidence=0.86,
        source_type="derived",
        evidence_refs=["intake_field:implementation_timeline_months", "framework:ius_from_implementation_months"],
        explanation=(
            f"IUS derived from implementation timeline {implementation_timeline_months} months "
            f"(PS_new framework bands)."
        ),
    )
    components["es_score"] = _component_dict(
        value=_val("es_score"),
        confidence=0.84,
        source_type="derived",
        evidence_refs=["intake_field:estimated_spend_usd", "heatmap_context:max_estimated_spend_pipeline"],
        explanation=(
            f"ES normalized from estimated spend vs pipeline max "
            f"(max_estimated_spend_pipeline={max_pipeline:.2f})."
        ),
    )
    components["csis_score"] = _component_dict(
        value=_val("csis_score"),
        confidence=0.83,
        source_type="derived",
        evidence_refs=["heatmap_context:category_spend_total", "heatmap_context:max_category_spend"],
        explanation=(
            f"CSIS from category spend ${cat_spend:,.0f} vs denominator ${max_cat:,.0f}."
        ),
    )
    components["sas_score"] = _component_dict(
        value=_val("sas_score"),
        confidence=0.78,
        source_type="derived",
        evidence_refs=["category_cards", "intake_field:preferred_supplier_status"],
        explanation=sas_note,
    )
    components = {k: v for k, v in components.items() if v is not None}

    scoring_inputs: Dict[str, Any] = {
        "request_title": request_title,
        "supplier_name": supplier_name,
        "category": category,
        "subcategory": subcategory,
        "estimated_spend_usd": estimated_spend_usd,
        "implementation_timeline_months": implementation_timeline_months,
        "preferred_supplier_status": preferred_supplier_status,
    }

    return {
        "score_components": components,
        "row_type": "new_business",
        "source_kind": "api_intake",
        "source_filename": None,
        "scoring_inputs": scoring_inputs,
        "weights_used": merged_weights,
    }

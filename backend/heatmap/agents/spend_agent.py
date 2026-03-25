from backend.heatmap.agents.state import HeatmapState, SpendSignal
from backend.heatmap.scoring_framework import (
    fis_from_contract_value,
    es_from_estimated_spend,
    csis_from_category_spend,
    scs_from_supplier_share_pct,
)


def process_spend(state: HeatmapState) -> dict:
    """
    Spend agent: FIS + SCS (existing contracts) or ES + CSIS (new requests).
    Uses precomputed heatmap_context from run_init (category maxima, spend shares).
    """
    idx = state["current_index"]
    contract = state["contracts"][idx]
    ctx = state.get("heatmap_context") or {}

    is_new = contract.get("contract_id") is None
    category = contract.get("category") or "IT Infrastructure"
    supplier = (contract.get("supplier_name") or "").strip()

    max_tcv_by_cat = ctx.get("max_tcv_by_category") or {}
    category_spend_total = ctx.get("category_spend_total") or {}
    supplier_category_spend = ctx.get("supplier_category_spend") or {}
    max_category_spend = float(ctx.get("max_category_spend") or 0.0)
    max_pipeline = float(ctx.get("max_estimated_spend_pipeline") or 0.0)

    spend_val = sum(float(s.get("PO Spend (USD)", 0) or 0) for s in contract.get("spend_data", []))

    if not is_new:
        details = contract.get("contract_details") or {}
        fis_key = ctx.get("fis_contract_value_field") or "TCV (Total Contract Value USD)"
        try:
            tcv = float(
                details.get(fis_key, 0)
                or details.get("TCV (Total Contract Value USD)", 0)
                or 0
            )
        except (TypeError, ValueError):
            tcv = 0.0
        max_tcv = float(max_tcv_by_cat.get(category) or 0.0)
        fis = fis_from_contract_value(tcv, max_tcv)

        key = f"{supplier}||{category}"
        sup_in_cat = float(supplier_category_spend.get(key) or 0.0)
        cat_total = float(category_spend_total.get(category) or 0.0)
        share_pct = (100.0 * sup_in_cat / cat_total) if cat_total > 0 else 0.0
        scs = scs_from_supplier_share_pct(share_pct)

        evidence = (
            f"FIS={fis:.1f} from TCV ${tcv:,.0f} vs category max ${max_tcv:,.0f}. "
            f"SCS={scs:.1f} from supplier share {share_pct:.1f}% of category spend "
            f"(${sup_in_cat:,.0f} / ${cat_total:,.0f}). "
            f"({len(contract.get('spend_data', []))} PO rows, Σ≈${spend_val:,.0f})."
        )
        signal = SpendSignal(
            fis_score=round(fis, 2),
            es_score=None,
            scs_score=scs,
            csis_score=None,
            evidence=evidence,
        )
    else:
        try:
            est = float(contract.get("estimated_spend_usd") or 0.0)
        except (TypeError, ValueError):
            est = 0.0
        denom = max_pipeline if max_pipeline > 0 else max(est, 1.0)
        es = es_from_estimated_spend(est, denom)

        cat_spend = float(category_spend_total.get(category) or 0.0)
        denom_c = max_category_spend if max_category_spend > 0 else max(cat_spend, 1.0)
        csis = csis_from_category_spend(cat_spend, denom_c)

        evidence = (
            f"ES={es:.1f} from estimated ${est:,.0f} vs pipeline max ${max_pipeline:,.0f}. "
            f"CSIS={csis:.1f} from category spend ${cat_spend:,.0f} vs max ${max_category_spend:,.0f}."
        )
        signal = SpendSignal(
            fis_score=None,
            es_score=round(es, 2),
            scs_score=None,
            csis_score=round(csis, 2),
            evidence=evidence,
        )

    current_list = list(state.get("spend_signals", []))
    current_list.append(signal)
    return {"spend_signals": current_list}

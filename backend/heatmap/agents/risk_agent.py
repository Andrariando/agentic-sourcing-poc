from backend.heatmap.agents.state import HeatmapState, RiskSignal
from backend.heatmap.scoring_framework import rss_from_supplier_risk_raw


def process_risk(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]

    is_new = contract.get("contract_id") is None

    if is_new:
        signal = RiskSignal(
            rss_score=None,
            evidence="New request — RSS not used in PS_new per framework.",
        )
    else:
        metrics = contract.get("metrics_data") or contract.get("supplier_metrics") or {}
        raw = metrics.get("Supplier Risk Score")
        rss = rss_from_supplier_risk_raw(raw if raw is not None else 3.0)
        signal = RiskSignal(
            rss_score=rss,
            evidence=f"RSS={rss}/10 from Supplier Risk Score field ({raw}).",
        )

    current_list = list(state.get("risk_signals", []))
    current_list.append(signal)
    return {"risk_signals": current_list}

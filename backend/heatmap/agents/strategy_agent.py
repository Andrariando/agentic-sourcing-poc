from backend.heatmap.agents.state import HeatmapState, StrategySignal
from backend.heatmap.scoring_framework import sas_from_category_cards


def process_strategy(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]
    ctx = state.get("heatmap_context") or {}
    category_cards = ctx.get("category_cards") or {}

    is_new = contract.get("contract_id") is None
    explicit = contract.get("preferred_supplier_status")

    score, evidence = sas_from_category_cards(
        contract.get("category") or "IT Infrastructure",
        contract.get("supplier_name"),
        is_new,
        explicit,
        category_cards,
    )

    signal = StrategySignal(sas_score=round(score, 2), evidence=evidence)
    current_list = list(state.get("strategy_signals", []))
    current_list.append(signal)
    return {"strategy_signals": current_list}

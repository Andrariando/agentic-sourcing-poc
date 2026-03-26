from backend.heatmap.agents.state import HeatmapState, StrategySignal
from backend.heatmap.scoring_framework import sas_from_category_cards
from backend.heatmap.services.llm_interpreter import normalize_preferred_status_token


def process_strategy(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]
    ctx = state.get("heatmap_context") or {}
    category_cards = ctx.get("category_cards") or {}

    is_new = contract.get("contract_id") is None
    explicit = contract.get("preferred_supplier_status")
    explicit_note = ""
    if explicit:
        token, conf, note, used_llm = normalize_preferred_status_token(explicit)
        if token and token != explicit:
            explicit_note = f" (normalized '{explicit}'→'{token}', conf={conf:.2f})"
            explicit = token
        elif used_llm and note:
            explicit_note = f" (status check: {note})"

    score, evidence = sas_from_category_cards(
        contract.get("category") or "IT Infrastructure",
        contract.get("supplier_name"),
        is_new,
        explicit,
        category_cards,
    )
    if explicit_note:
        evidence = evidence + explicit_note

    signal = StrategySignal(sas_score=round(score, 2), evidence=evidence)
    current_list = list(state.get("strategy_signals", []))
    current_list.append(signal)
    return {"strategy_signals": current_list}

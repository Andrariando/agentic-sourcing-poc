from backend.heatmap.agents.state import HeatmapState, StrategySignal
import random

def process_strategy(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]
    
    # Strategy Alignment Score (SAS) between 0 and 10
    # Higher logic would query category_strategies.json
    sas_score = round(random.uniform(5.0, 10.0), 1)
    
    signal = StrategySignal(
        sas_score=sas_score,
        evidence=f"Supplier {contract.get('supplier_name', 'Unknown')} partially aligns with preferred category strategies for {contract.get('category', 'IT')}."
    )
    
    current_list = list(state.get("strategy_signals", []))
    current_list.append(signal)
    return {"strategy_signals": current_list}

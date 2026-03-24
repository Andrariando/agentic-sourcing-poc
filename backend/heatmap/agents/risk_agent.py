from backend.heatmap.agents.state import HeatmapState, RiskSignal

def process_risk(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]
    
    is_new = contract.get("contract_id") is None
    
    if is_new:
        # New requests may not have a supplier yet, RSS is N/A
        signal = RiskSignal(rss_score=None, evidence="New request, supplier risk not yet applicable.")
    else:
        metrics = contract.get("metrics_data", {})
        raw_risk = metrics.get("Supplier Risk Score", 3.0)
        # Normalize 1-5 scale to 1-10
        rss = float(raw_risk) * 2.0
        
        signal = RiskSignal(
            rss_score=round(rss, 1),
            evidence=f"Supplier risk rating derived as {rss}/10 based on internal metrics."
        )
        
    current_list = list(state.get("risk_signals", []))
    current_list.append(signal)
    return {"risk_signals": current_list}

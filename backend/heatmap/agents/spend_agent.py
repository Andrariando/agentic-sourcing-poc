from backend.heatmap.agents.state import HeatmapState, SpendSignal


def process_spend(state: HeatmapState) -> dict:
    """
    Spend Analysis Agent.
    Calculates FIS (Financial Impact Score) for existing contracts
    and ES (Estimated Spend Score) for new requests.
    
    Future: Will use LLM to parse raw spend_data and extract insights.
    Currently uses deterministic scoring for POC reliability.
    """
    idx = state["current_index"]
    contract = state["contracts"][idx]
    
    # Deterministic scoring for POC:
    is_new = contract.get("contract_id") is None
    spend_val = sum(s.get("PO Spend (USD)", 0) for s in contract.get("spend_data", []))
    
    # Dummy scores between 3 and 9 based on spend
    score = min(10.0, max(2.0, spend_val / 500000.0 * 10))
    
    signal = SpendSignal(
        fis_score=score if not is_new else None,
        es_score=score if is_new else None,
        scs_score=6.0 if not is_new else None,
        csis_score=7.0 if is_new else None,
        evidence=f"Analyzed {len(contract.get('spend_data', []))} spend records. Total spend extrapolated is roughly ${spend_val:,.2f}."
    )
    
    # Append to state list
    current_list = list(state.get("spend_signals", []))
    current_list.append(signal)
    return {"spend_signals": current_list}

from datetime import datetime
from backend.heatmap.agents.state import HeatmapState, ContractSignal

def process_contract(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]
    
    is_new = contract.get("contract_id") is None
    details = contract.get("contract_details", {})
    
    if is_new:
        # It's a new request, meaning Implementation Urgency (IUS) applies.
        # This could come from a simulated form field.
        ius = 8.0 
        signal = ContractSignal(
            eus_score=None,
            ius_score=ius,
            action_window="Immediate",
            evidence="New request marked with high implementation urgency."
        )
    else:
        # Existing contract
        exp_date_str = details.get("Expiration Date", "")
        if exp_date_str:
            try:
                exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                days_left = (exp_date - datetime.today()).days
                
                if days_left <= 90:
                    eus = 10.0
                    act = "Critical (<= 90 days)"
                elif days_left <= 180:
                    eus = 8.0
                    act = "High (<= 180 days)"
                else:
                    eus = max(2.0, 10.0 - (days_left / 365.0 * 5.0))
                    act = "Monitor"
                    
                signal = ContractSignal(
                    eus_score=round(eus, 1),
                    ius_score=None,
                    action_window=act,
                    evidence=f"Contract expires in {days_left} days on {exp_date_str}."
                )
            except Exception:
                signal = ContractSignal(eus_score=5.0, ius_score=None, action_window="Unknown", evidence="Could not parse expiration date.")
        else:
            signal = ContractSignal(eus_score=5.0, ius_score=None, action_window="Unknown", evidence="No expiration date provided.")
            
    current_list = list(state.get("contract_signals", []))
    current_list.append(signal)
    return {"contract_signals": current_list}

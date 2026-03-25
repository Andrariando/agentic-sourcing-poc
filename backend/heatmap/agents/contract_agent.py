from datetime import datetime
from backend.heatmap.agents.state import HeatmapState, ContractSignal
from backend.heatmap.scoring_framework import (
    eus_from_months_to_expiry,
    ius_from_implementation_months,
    months_until_expiry_from_iso,
)


def process_contract(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]
    today = datetime.today()

    is_new = contract.get("contract_id") is None
    details = contract.get("contract_details") or {}

    if is_new:
        months = contract.get("implementation_timeline_months")
        if months is None:
            months = 6.0
        try:
            months = float(months)
        except (TypeError, ValueError):
            months = 6.0
        ius = ius_from_implementation_months(months)
        if months < 3:
            act = "Critical (<3 mo to implement)"
        elif months < 6:
            act = "High (3–6 mo)"
        elif months < 12:
            act = "Standard (6–12 mo)"
        else:
            act = "Planned (>12 mo)"
        signal = ContractSignal(
            eus_score=None,
            ius_score=round(ius, 1),
            action_window=act,
            evidence=f"Implementation timeline ~{months:.1f} mo → IUS={ius} ({act}).",
        )
    else:
        exp_date_str = details.get("Expiration Date", "")
        if exp_date_str:
            months_left = months_until_expiry_from_iso(exp_date_str, today)
            if months_left is not None:
                eus = eus_from_months_to_expiry(months_left)
                days_left = int(months_left * 30.437)
                if months_left <= 3:
                    act = "Critical (0–3 months to expiry)"
                elif months_left <= 6:
                    act = "High (3–6 months)"
                elif months_left <= 12:
                    act = "Medium (6–12 months)"
                elif months_left <= 18:
                    act = "Watch (12–18 months)"
                else:
                    act = "Monitor (>18 months)"
                signal = ContractSignal(
                    eus_score=round(eus, 1),
                    ius_score=None,
                    action_window=act,
                    evidence=f"~{months_left:.1f} months to expiry ({exp_date_str}, ≈{days_left}d) → EUS={eus}.",
                )
            else:
                signal = ContractSignal(
                    eus_score=5.0,
                    ius_score=None,
                    action_window="Unknown",
                    evidence="Could not parse expiration date.",
                )
        else:
            signal = ContractSignal(
                eus_score=5.0,
                ius_score=None,
                action_window="Unknown",
                evidence="No expiration date on contract record.",
            )

    current_list = list(state.get("contract_signals", []))
    current_list.append(signal)
    return {"contract_signals": current_list}

from datetime import datetime
from backend.heatmap.agents.state import HeatmapState, ContractSignal
from backend.heatmap.scoring_framework import (
    eus_from_months_to_expiry,
    ius_from_implementation_months,
    months_until_expiry_from_iso,
)
from backend.heatmap.services.llm_interpreter import extract_expiration_date_iso


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
                # Fallback: try LLM interpreter to extract an ISO date from messy contract_details.
                iso, conf, note, used_llm = extract_expiration_date_iso(details)
                if iso:
                    months_left2 = months_until_expiry_from_iso(iso, today)
                    if months_left2 is not None:
                        eus = eus_from_months_to_expiry(months_left2)
                        days_left = int(months_left2 * 30.437)
                        if months_left2 <= 3:
                            act = "Critical (0–3 months to expiry)"
                        elif months_left2 <= 6:
                            act = "High (3–6 months)"
                        elif months_left2 <= 12:
                            act = "Medium (6–12 months)"
                        elif months_left2 <= 18:
                            act = "Watch (12–18 months)"
                        else:
                            act = "Monitor (>18 months)"
                        src = "LLM interpreter" if used_llm else "fallback"
                        signal = ContractSignal(
                            eus_score=round(eus, 1),
                            ius_score=None,
                            action_window=act,
                            evidence=(
                                f"Expiration Date parse failed for '{exp_date_str}'. "
                                f"{src} extracted {iso} (conf={conf:.2f}) → ~{months_left2:.1f} months (≈{days_left}d) → EUS={eus}. "
                                f"Note: {note}"
                            ),
                        )
                    else:
                        signal = ContractSignal(
                            eus_score=5.0,
                            ius_score=None,
                            action_window="Unknown",
                            evidence=f"Could not parse expiration date; interpreter suggested '{iso}' but parsing still failed. Note: {note}",
                        )
                else:
                    signal = ContractSignal(
                        eus_score=5.0,
                        ius_score=None,
                        action_window="Unknown",
                        evidence="Could not parse expiration date (and no interpreter extraction available).",
                    )
        else:
            # If the explicit field is missing, attempt interpreter extraction from other metadata.
            iso, conf, note, used_llm = extract_expiration_date_iso(details)
            if iso:
                months_left2 = months_until_expiry_from_iso(iso, today)
                if months_left2 is not None:
                    eus = eus_from_months_to_expiry(months_left2)
                    days_left = int(months_left2 * 30.437)
                    if months_left2 <= 3:
                        act = "Critical (0–3 months to expiry)"
                    elif months_left2 <= 6:
                        act = "High (3–6 months)"
                    elif months_left2 <= 12:
                        act = "Medium (6–12 months)"
                    elif months_left2 <= 18:
                        act = "Watch (12–18 months)"
                    else:
                        act = "Monitor (>18 months)"
                    src = "LLM interpreter" if used_llm else "fallback"
                    signal = ContractSignal(
                        eus_score=round(eus, 1),
                        ius_score=None,
                        action_window=act,
                        evidence=(
                            f"No Expiration Date field. {src} extracted {iso} (conf={conf:.2f}) "
                            f"→ ~{months_left2:.1f} months (≈{days_left}d) → EUS={eus}. Note: {note}"
                        ),
                    )
                else:
                    signal = ContractSignal(
                        eus_score=5.0,
                        ius_score=None,
                        action_window="Unknown",
                        evidence=f"No Expiration Date field; interpreter suggested '{iso}' but parsing failed. Note: {note}",
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

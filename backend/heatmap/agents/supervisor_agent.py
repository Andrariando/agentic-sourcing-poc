from backend.heatmap.agents.state import HeatmapState, ScoredOpportunity
from backend.heatmap.services.feedback_memory import apply_learning_nudge


def process_supervisor(state: HeatmapState) -> dict:
    idx = state["current_index"]
    contract = state["contracts"][idx]
    
    s_spend = state["spend_signals"][idx]
    s_contract = state["contract_signals"][idx]
    s_strategy = state["strategy_signals"][idx]
    s_risk = state["risk_signals"][idx]
    
    is_new = contract.get("contract_id") is None
    w = state.get("weights", {})
    
    total_score = 0.0
    tier = "T4"
    justification = ""
    
    if is_new:
        # PS_new = 0.30(IUS) + 0.30(ES) + 0.25(CSIS) + 0.15(SAS)
        w_ius = w.get("w_ius", 0.30)
        w_es = w.get("w_es", 0.30)
        w_csis = w.get("w_csis", 0.25)
        w_sas = w.get("w_sas", 0.15)
        
        ius = s_contract.get("ius_score") or 0.0
        es = s_spend.get("es_score") or 0.0
        csis = s_spend.get("csis_score") or 0.0
        sas = s_strategy.get("sas_score") or 0.0
        
        total_score = (w_ius * ius) + (w_es * es) + (w_csis * csis) + (w_sas * sas)
        justification = (
            f"New request scored {total_score:.2f}. "
            f"IUS({ius})*{w_ius} + ES({es})*{w_es} + CSIS({csis})*{w_csis} + SAS({sas})*{w_sas}"
        )
    else:
        # PS_contract = 0.30(EUS) + 0.25(FIS) + 0.20(RSS) + 0.15(SCS) + 0.10(SAS)
        w_eus = w.get("w_eus", 0.30)
        w_fis = w.get("w_fis", 0.25)
        w_rss = w.get("w_rss", 0.20)
        w_scs = w.get("w_scs", 0.15)
        w_sas = w.get("w_sas", 0.10)
        
        eus = s_contract.get("eus_score") or 0.0
        fis = s_spend.get("fis_score") or 0.0
        rss = s_risk.get("rss_score") or 0.0
        scs = s_spend.get("scs_score") or 0.0
        sas = s_strategy.get("sas_score") or 0.0
        
        total_score = (w_eus * eus) + (w_fis * fis) + (w_rss * rss) + (w_scs * scs) + (w_sas * sas)
        justification = (
            f"Contract scored {total_score:.2f}. "
            f"EUS({eus})*{w_eus} + FIS({fis})*{w_fis} + RSS({rss})*{w_rss} + SCS({scs})*{w_scs} + SAS({sas})*{w_sas}"
        )

    base_total = round(total_score, 2)
    _delta, mem_note, total_score, tier = apply_learning_nudge(
        category=contract.get("category") or "",
        subcategory=contract.get("subcategory"),
        supplier_name=contract.get("supplier_name"),
        is_new=is_new,
        baseline_summary=justification,
        base_total=base_total,
        weights=w,
    )
    if mem_note:
        justification = f"{justification} | Learning: {mem_note}"
        
    opp = ScoredOpportunity(
        contract_id=contract.get("contract_id"),
        request_id=contract.get("request_id"),
        supplier_name=contract.get("supplier_name"),
        category=contract.get("category"),
        subcategory=contract.get("subcategory"),
        eus_score=s_contract.get("eus_score"),
        ius_score=s_contract.get("ius_score"),
        fis_score=s_spend.get("fis_score"),
        es_score=s_spend.get("es_score"),
        rss_score=s_risk.get("rss_score"),
        scs_score=s_spend.get("scs_score"),
        csis_score=s_spend.get("csis_score"),
        sas_score=s_strategy.get("sas_score"),
        total_score=round(total_score, 2),
        tier=tier,
        action_window=s_contract.get("action_window"),
        justification_summary=justification
    )
    
    current_list = list(state.get("scored_opportunities", []))
    current_list.append(opp)
    
    return {"scored_opportunities": current_list}

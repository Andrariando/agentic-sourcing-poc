import csv
import random
import time
from pathlib import Path

from sqlmodel import Session, delete, select

from backend.heatmap.seed_synthetic_data import generate_supplier_metrics, generate_contracts, generate_spend, DATA_DIR
from backend.heatmap.agents.state import HeatmapState
from backend.heatmap.agents.graph import heatmap_graph
from backend.heatmap.context_builder import (
    load_category_cards,
    load_supplier_metrics_map,
    load_spend_aggregates,
    load_max_contract_value_by_category,
    build_heatmap_context,
    fis_contract_value_field,
)
from backend.heatmap.persistence.heatmap_database import heatmap_db, get_engine
from backend.heatmap.persistence.heatmap_models import Opportunity, ReviewFeedback
from backend.heatmap.services.seed_kpi_demo_data import seed_demo_feedback_and_pipeline_audit
from backend.heatmap.services.learned_weights import load_learned_weights, weights_for_supervisor_state


def run_init():
    print("Generating CSVs to:", DATA_DIR)
    generate_supplier_metrics()
    generate_contracts()
    generate_spend()

    print("Reading CSVs to build initial LangGraph state matrix...")

    category_cards = load_category_cards()
    supplier_metrics = load_supplier_metrics_map()
    spend_by_supplier, category_spend_total, supplier_category_spend = load_spend_aggregates()
    max_tcv_by_category = load_max_contract_value_by_category()
    fis_key = fis_contract_value_field()

    contracts = []
    with open(DATA_DIR / "synthetic_contracts.csv", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            supp = row["Supplier"]
            cat = row.get("Category") or "IT Infrastructure"
            contracts.append({
                "contract_id": row["Contract ID"],
                "request_id": None,
                "supplier_name": supp,
                "category": cat,
                "subcategory": row["Subcategory"],
                "spend_data": spend_by_supplier.get(supp, []),
                "contract_details": dict(row),
                "metrics_data": supplier_metrics.get(supp, {}),
                "category_strategy": category_cards.get(cat, {}),
            })

    new_estimates: list[float] = []
    timeline_choices = [2.0, 4.0, 7.0, 9.0, 14.0]
    for i in range(5):
        supp = random.choice(list(supplier_metrics.keys()))
        cat = "IT Infrastructure"
        po_sum = sum(s.get("PO Spend (USD)", 0) or 0 for s in spend_by_supplier.get(supp, []))
        estimated = max(
            80_000.0,
            round(po_sum * random.uniform(0.8, 1.4) if po_sum else random.uniform(200_000, 2_000_000), 2),
        )
        new_estimates.append(estimated)
        contracts.append({
            "contract_id": None,
            "request_id": f"REQ-2026-{900+i}",
            "supplier_name": supp,
            "category": cat,
            "subcategory": "Cloud Hosting",
            "spend_data": spend_by_supplier.get(supp, []),
            "contract_details": {},
            "metrics_data": supplier_metrics.get(supp, {}),
            "category_strategy": category_cards.get(cat, {}),
            "estimated_spend_usd": estimated,
            "implementation_timeline_months": timeline_choices[i % len(timeline_choices)],
            "preferred_supplier_status": None,
        })

    max_estimated_spend_pipeline = max(new_estimates) if new_estimates else 1.0

    heatmap_context = build_heatmap_context(max_estimated_spend_pipeline=max_estimated_spend_pipeline)
    heatmap_context["max_tcv_by_category"] = max_tcv_by_category
    heatmap_context["category_spend_total"] = dict(category_spend_total)
    heatmap_context["supplier_category_spend"] = dict(supplier_category_spend)
    max_category_spend = max(category_spend_total.values()) if category_spend_total else 0.0
    heatmap_context["max_category_spend"] = max_category_spend
    heatmap_context["category_cards"] = category_cards
    heatmap_context["fis_contract_value_field"] = fis_key

    print(f"Loaded {len(contracts)} opportunities. Executing Multi-Agent Pipeline...")
    t_pipeline = time.time()

    with Session(get_engine()) as _w_sess:
        merged_w = weights_for_supervisor_state(load_learned_weights(_w_sess))

    initial_state: HeatmapState = {
        "contracts": contracts,
        "spend_signals": [],
        "contract_signals": [],
        "strategy_signals": [],
        "risk_signals": [],
        "scored_opportunities": [],
        "current_index": 0,
        "weights": merged_w,
        "heatmap_context": heatmap_context,
    }

    final_state = heatmap_graph.invoke(initial_state, config={"recursion_limit": 1000})

    print("Engine finished. Committing to SQLite database...")
    heatmap_db.init_db()
    with Session(get_engine()) as session:
        old_ids = session.exec(select(Opportunity.id).where(Opportunity.source == "batch")).all()
        for row in old_ids:
            oid = row[0] if isinstance(row, (tuple, list)) else row
            if oid is not None:
                session.exec(delete(ReviewFeedback).where(ReviewFeedback.opportunity_id == oid))
        session.exec(delete(Opportunity).where(Opportunity.source == "batch"))
        session.commit()

        new_idx = 0
        for opp in final_state["scored_opportunities"]:
            is_new = opp.get("contract_id") is None
            est = None
            impl_mo = None
            if is_new:
                if new_idx < len(new_estimates):
                    est = new_estimates[new_idx]
                    impl_mo = timeline_choices[new_idx % len(timeline_choices)]
                new_idx += 1
            db_opp = Opportunity(
                contract_id=opp.get("contract_id"),
                request_id=opp.get("request_id"),
                supplier_name=opp.get("supplier_name"),
                category=opp.get("category"),
                subcategory=opp.get("subcategory"),
                eus_score=float(opp["eus_score"]) if opp.get("eus_score") is not None else None,
                ius_score=float(opp["ius_score"]) if opp.get("ius_score") is not None else None,
                fis_score=float(opp["fis_score"]) if opp.get("fis_score") is not None else None,
                es_score=float(opp["es_score"]) if opp.get("es_score") is not None else None,
                rss_score=float(opp["rss_score"]) if opp.get("rss_score") is not None else None,
                scs_score=float(opp["scs_score"]) if opp.get("scs_score") is not None else None,
                csis_score=float(opp["csis_score"]) if opp.get("csis_score") is not None else None,
                sas_score=float(opp["sas_score"]) if opp.get("sas_score") is not None else None,
                total_score=float(opp.get("total_score", 0)),
                tier=opp.get("tier"),
                recommended_action_window=opp.get("action_window"),
                justification_summary=opp.get("justification_summary"),
                status="Pending",
                disposition="new_request" if is_new else "renewal_candidate",
                not_pursue_reason_code=None,
                source="batch",
                estimated_spend_usd=est,
                implementation_timeline_months=impl_mo,
                request_title=None,
                preferred_supplier_status=None,
            )
            session.add(db_opp)
        session.commit()

        duration_sec = max(0.001, time.time() - t_pipeline)
        n_demo = seed_demo_feedback_and_pipeline_audit(
            session,
            pipeline_duration_sec=duration_sec,
            opportunity_count=len(final_state["scored_opportunities"]),
        )
        if n_demo:
            print(f"Demo KPI/KLI: inserted {n_demo} synthetic ReviewFeedback rows + pipeline audit log.")
    print(f"Success! {len(final_state['scored_opportunities'])} scored opportunities saved to heatmap.db")


if __name__ == "__main__":
    run_init()

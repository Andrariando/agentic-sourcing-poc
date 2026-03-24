import os
import csv
import random
from pathlib import Path
from backend.heatmap.seed_synthetic_data import generate_supplier_metrics, generate_contracts, generate_spend, DATA_DIR
from backend.heatmap.agents.state import HeatmapState
from backend.heatmap.agents.graph import heatmap_graph
from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import Opportunity
from sqlmodel import Session

def run_init():
    print("Generating CSVs to:", DATA_DIR)
    generate_supplier_metrics()
    generate_contracts()
    generate_spend()

    print("Reading CSVs to build initial LangGraph state matrix...")
    
    # Load Supplier Metrics
    supplier_metrics = {}
    with open(DATA_DIR / "synthetic_supplier_metrics.csv", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            supplier_metrics[row["Supplier"]] = row

    # Load Spend Data
    spend_by_supplier = {}
    with open(DATA_DIR / "synthetic_spend.csv", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Parse PO Spend as float safely
            try:
                row["PO Spend (USD)"] = float(row["PO Spend (USD)"])
            except:
                row["PO Spend (USD)"] = 0.0
            
            supp = row["Supplier"]
            if supp not in spend_by_supplier:
                spend_by_supplier[supp] = []
            spend_by_supplier[supp].append(row)

    # Load Contracts
    contracts = []
    with open(DATA_DIR / "synthetic_contracts.csv", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            supp = row["Supplier"]
            contracts.append({
                "contract_id": row["Contract ID"],
                "request_id": None,
                "supplier_name": supp,
                "category": row["Category"],
                "subcategory": row["Subcategory"],
                "spend_data": spend_by_supplier.get(supp, []),
                "contract_details": row,
                "supplier_metrics": supplier_metrics.get(supp, {}),
                "category_strategy": {},
                "market_reports": []
            })
            
    # Add a few "New Demand" Requests (no contract_id)
    for i in range(5):
        supp = random.choice(list(supplier_metrics.keys()))
        contracts.append({
            "contract_id": None,
            "request_id": f"REQ-2026-{900+i}",
            "supplier_name": supp,
            "category": "IT Infrastructure",
            "subcategory": "Cloud Hosting",
            "spend_data": spend_by_supplier.get(supp, []), # Proxy for estimated spend
            "contract_details": {},
            "supplier_metrics": supplier_metrics.get(supp, {}),
            "category_strategy": {},
            "market_reports": []
        })

    print(f"Loaded {len(contracts)} opportunities. Executing Multi-Agent Pipeline...")
    
    initial_state = HeatmapState(
        contracts=contracts,
        spend_signals=[],
        contract_signals=[],
        strategy_signals=[],
        risk_signals=[],
        scored_opportunities=[],
        current_index=0,
        weights={}
    )

    final_state = heatmap_graph.invoke(initial_state, config={"recursion_limit": 1000})

    print("Engine finished. Committing to SQLite database...")
    heatmap_db.init_db()
    with heatmap_db.get_db_session() as session:
        # Clear existing
        session.query(Opportunity).delete()
        
        for opp in final_state["scored_opportunities"]:
            # Round numerical scores to 1 decimal correctly for database
            db_opp = Opportunity(
                contract_id=opp.get("contract_id"),
                request_id=opp.get("request_id"),
                supplier_name=opp.get("supplier_name"),
                category=opp.get("category"),
                subcategory=opp.get("subcategory"),
                eus_score=float(opp.get("eus_score")) if opp.get("eus_score") is not None else None,
                ius_score=float(opp.get("ius_score")) if opp.get("ius_score") is not None else None,
                fis_score=float(opp.get("fis_score")) if opp.get("fis_score") is not None else None,
                es_score=float(opp.get("es_score")) if opp.get("es_score") is not None else None,
                rss_score=float(opp.get("rss_score")) if opp.get("rss_score") is not None else None,
                scs_score=float(opp.get("scs_score")) if opp.get("scs_score") is not None else None,
                csis_score=float(opp.get("csis_score")) if opp.get("csis_score") is not None else None,
                sas_score=float(opp.get("sas_score")) if opp.get("sas_score") is not None else None,
                total_score=float(opp.get("total_score")),
                tier=opp.get("tier"),
                recommended_action_window=opp.get("action_window"),
                justification_summary=opp.get("justification_summary"),
                status="Pending"
            )
            session.add(db_opp)
        session.commit()
    print(f"Success! {len(final_state['scored_opportunities'])} scored opportunities saved to heatmap.db")

if __name__ == "__main__":
    run_init()

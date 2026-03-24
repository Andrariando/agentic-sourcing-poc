import os
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# Config
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "heatmap" / "synthetic"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CATEGORIES = ["IT Infrastructure"]
SUBCATEGORIES = ["Cloud Hosting", "Network Infrastructure", "Data Center", "End User Computing", "Cybersecurity"]
SUPPLIERS = [
    "TechGlobal Inc", "NetSystems LLC", "CloudServe Group", "SecureShield Tech",
    "DataCenter Partners", "Endpoint Solutions Corp", "AlphaNetwork Services", "CyberGuard Ltd",
    "DeltaStorage Systems", "Infinite Computing"
]

def generate_supplier_metrics():
    path = DATA_DIR / "synthetic_supplier_metrics.csv"
    headers = [
        'Supplier Number', 'Supplier Parent', 'Supplier', 'Site', 'Category', 'Subcategory', 
        'Sector', 'Region', 'Country', 'State', 'City', 'Spend Tier (USD)', 
        'Supplier Parent Risk Rating', 'Supplier Risk Score', 'Criticality Risk Level', 
        'Criticality Risk Score', 'Strategic Risk Score', 'BPRA Security Scorecard', 
        'BPRA Vendor Status', 'Ethics', 'Labor & Human Rights', 'Resilinc Alerts by Supplier', 
        'Sanctions, AML+ABC due diligence', 'Environment', 'Supplier Financial Health', 
        'Sustainable Procurement'
    ]
    
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for i, supp in enumerate(SUPPLIERS):
            risk_score = round(random.uniform(1.0, 5.0), 2)  # Score out of 5 usually
            writer.writerow([
                f"SUP-{1000+i}", supp, supp, "HQ", "IT Infrastructure", random.choice(SUBCATEGORIES),
                "Tech", "NA", "USA", "NY", "New York", random.choice(["Tier 1", "Tier 2", "Tier 3"]),
                random.choice(["Low", "Medium", "High"]), risk_score, random.choice(["Low", "Medium", "High"]),
                round(random.uniform(1.0, 5.0), 2), round(random.uniform(1.0, 5.0), 2), "A",
                "Approved", "Pass", "Pass", "0", "Clear", "Pass", 
                random.choice(["Strong", "Stable", "Weak"]), "Pass"
            ])
    print(f"Generated {path}")

def generate_contracts():
    path = DATA_DIR / "synthetic_contracts.csv"
    headers = [
        'Contract ID', 'Contract Title', 'Supplier Parent', 'Supplier', 'Category', 
        'Subcategory', 'Contract Type', 'Status', 'Effective Date', 'Expiration Date', 
        'Auto-Renewal', 'Notice Period (Days)', 'TCV (Total Contract Value USD)', 
        'ACV (Annual Contract Value USD)', 'Business Owner', 'Sourcing Manager', 
        'Payment Terms', 'SLA Penalties (Y/N)'
    ]
    
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        base_date = datetime.today()
        
        for i in range(25):
            supp = random.choice(SUPPLIERS)
            subcat = random.choice(SUBCATEGORIES)
            
            # Mix of expiring soon and far out
            days_to_expiry = random.randint(30, 400)
            exp_date = base_date + timedelta(days=days_to_expiry)
            eff_date = exp_date - timedelta(days=365 * random.randint(1, 3))
            
            tcv = random.randint(100000, 5000000)
            acv = int(tcv / 3)
            
            writer.writerow([
                f"CNT-2026-{100+i}", f"{subcat} Master Agreement", supp, supp, "IT Infrastructure",
                subcat, "MSA", "Active", eff_date.strftime("%Y-%m-%d"), exp_date.strftime("%Y-%m-%d"),
                random.choice(["Yes", "No"]), random.choice([30, 60, 90]), tcv, acv,
                "IT Ops Lead", "Sourcing Manager A", "Net 45", random.choice(["Y", "N"])
            ])
    print(f"Generated {path}")

def generate_spend():
    path = DATA_DIR / "synthetic_spend.csv"
    headers = [
        'PO Number', 'PO Line', 'PO Date', 'Requisition ID', 'Requisition Date', 
        'Category', 'Subcategory', 'Supplier Parent', 'Supplier', 'PO Spend (USD)', 
        'Currency', 'Business Unit', 'Cost Center', 'Requester', 'Description', 
        'Month', 'Year', 'Payment Terms'
    ]
    
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        base_date = datetime.today()
        
        for i in range(150):
            supp = random.choice(SUPPLIERS)
            po_date = base_date - timedelta(days=random.randint(1, 365))
            spend = round(random.uniform(5000, 200000), 2)
            
            writer.writerow([
                f"PO-{80000+i}", 1, po_date.strftime("%Y-%m-%d"), f"REQ-{60000+i}", po_date.strftime("%Y-%m-%d"),
                "IT Infrastructure", random.choice(SUBCATEGORIES), supp, supp, spend,
                "USD", "IT", "CC-IT-101", "Jane Doe", "Monthly Services",
                po_date.strftime("%b"), po_date.strftime("%Y"), "Net 45"
            ])
    print(f"Generated {path}")

if __name__ == "__main__":
    print(f"Generating synthetic data to {DATA_DIR}...")
    generate_supplier_metrics()
    generate_contracts()
    generate_spend()
    print("Done.")

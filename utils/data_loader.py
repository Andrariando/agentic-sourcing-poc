"""
Data loading utilities for synthetic data files.
"""
import json
import os
from typing import List, Dict, Any, Optional


def load_json_data(filename: str) -> List[Dict[str, Any]]:
    """Load JSON data file from data directory"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    filepath = os.path.join(data_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_category(category_id: str) -> Optional[Dict[str, Any]]:
    """Get category by ID"""
    categories = load_json_data("categories.json")
    return next((c for c in categories if c["category_id"] == category_id), None)


def get_supplier(supplier_id: str) -> Optional[Dict[str, Any]]:
    """Get supplier by ID"""
    suppliers = load_json_data("suppliers.json")
    return next((s for s in suppliers if s["supplier_id"] == supplier_id), None)


def get_contract(contract_id: str) -> Optional[Dict[str, Any]]:
    """Get contract by ID"""
    contracts = load_json_data("contracts.json")
    return next((c for c in contracts if c["contract_id"] == contract_id), None)


def get_performance(supplier_id: str) -> Optional[Dict[str, Any]]:
    """Get performance data by supplier ID"""
    performance = load_json_data("performance.json")
    return next((p for p in performance if p["supplier_id"] == supplier_id), None)


def get_market_data(category_id: str) -> Optional[Dict[str, Any]]:
    """Get market benchmark data by category ID"""
    market = load_json_data("market.json")
    return next((m for m in market if m["category_id"] == category_id), None)


def get_requirements(category_id: str) -> Optional[Dict[str, Any]]:
    """Get requirements data by category ID"""
    requirements = load_json_data("requirements.json")
    return next((r for r in requirements if r["category_id"] == category_id), None)


def get_suppliers_by_category(category_id: str) -> List[Dict[str, Any]]:
    """Get all suppliers for a category"""
    suppliers = load_json_data("suppliers.json")
    return [s for s in suppliers if s["category_id"] == category_id]


def get_contracts_by_supplier(supplier_id: str) -> List[Dict[str, Any]]:
    """Get all contracts for a supplier"""
    contracts = load_json_data("contracts.json")
    return [c for c in contracts if c["supplier_id"] == supplier_id]


def generate_signal_from_contract(contract_id: str) -> Dict[str, Any]:
    """Generate a signal from contract expiry"""
    contract = get_contract(contract_id)
    if not contract:
        return {}
    
    expiry_days = contract["expiry_days"]
    severity = "High" if expiry_days <= 60 else "Medium" if expiry_days <= 180 else "Low"
    
    return {
        "signal_id": f"SIG-{contract_id}",
        "signal_type": "Contract Expiry",
        "category_id": contract["category_id"],
        "contract_id": contract_id,
        "supplier_id": contract["supplier_id"],
        "severity": severity,
        "description": f"Contract {contract_id} expiring in {expiry_days} days",
        "detected_date": "2024-02-01",
        "metadata": {
            "expiry_days": expiry_days,
            "annual_value_usd": contract["annual_value_usd"]
        }
    }



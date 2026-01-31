"""
DTP Stage Prerequisites Definition.

Single source of truth for what each DTP stage requires to proceed.
Used by ChatService preflight check and readiness reports.
"""

from typing import Dict, List, Any

STAGE_PREREQS: Dict[str, Dict[str, Any]] = {
    "DTP-01": {
        "description": "Strategy & Triage",
        "case_fields": ["category_id", "trigger_source"],
        "human_decisions": [],  # No prior decisions needed
        "context_fields": [],
        "context_fields_or": [],
    },
    "DTP-02": {
        "description": "Supplier Identification",
        "case_fields": [],
        "human_decisions": ["DTP-01.sourcing_required"],  # Must confirm sourcing needed
        "context_fields": ["candidate_suppliers"],  # Required for demo stability
        "context_fields_or": [],
    },
    "DTP-03": {
        "description": "RFx & Evaluation",
        "case_fields": [],
        "human_decisions": ["DTP-02.supplier_list_confirmed"],
        "context_fields": [],
        "context_fields_or": [],
    },
    "DTP-04": {
        "description": "Negotiation & Award",
        "case_fields": [],
        "human_decisions": ["DTP-03.evaluation_complete"],
        "context_fields": [],
        # OR logic: need finalists OR selected supplier for negotiation
        "context_fields_or": ["finalist_suppliers", "selected_supplier_id"],
    },
    "DTP-05": {
        "description": "Internal Approval",
        "case_fields": [],
        "human_decisions": ["DTP-04.award_supplier_id"],
        "context_fields": [],
        "context_fields_or": [],
    },
    "DTP-06": {
        "description": "Implementation",
        "case_fields": [],
        "human_decisions": ["DTP-05.stakeholder_signoff"],
        "context_fields": [],
        "context_fields_or": [],
    }
}


def get_stage_description(stage: str) -> str:
    """Get human-readable description for a DTP stage."""
    prereqs = STAGE_PREREQS.get(stage, {})
    return prereqs.get("description", stage)


def get_all_prior_decisions(stage: str) -> List[str]:
    """Get all decisions required from prior stages (cumulative)."""
    stage_order = ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"]
    
    try:
        current_idx = stage_order.index(stage)
    except ValueError:
        return []
    
    all_decisions = []
    for i in range(current_idx + 1):
        prereqs = STAGE_PREREQS.get(stage_order[i], {})
        all_decisions.extend(prereqs.get("human_decisions", []))
    
    return all_decisions

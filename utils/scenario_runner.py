"""
Headless scenario runner utilities.

These helpers let you:
- Run a single case through the LangGraph workflow without Streamlit
- Batch‑run all seed cases from `data/cases_seed.json`
- Return structured traces suitable for JSON/CSV export
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils.schemas import (
    Case,
    CaseSummary,
    CacheMeta,
)
from utils.state import PipelineState
from utils.token_accounting import create_initial_budget_state
from utils.data_loader import load_json_data
from utils.dtp_stages import get_dtp_stage_display
from graphs.workflow import get_workflow_graph


def _build_policy_context(dtp_stage: str) -> Dict[str, Any]:
    """
    Lightweight replica of the DTPPolicyContext builder used in `app.py`,
    implemented here without a dependency on Streamlit.
    """
    allowed_transitions = {
        "DTP-01": ["DTP-02"],
        "DTP-02": ["DTP-03", "DTP-04"],
        "DTP-03": ["DTP-04"],
        "DTP-04": ["DTP-05"],
        "DTP-05": ["DTP-06"],
    }
    stage_checks = {
        "DTP-01": ["Ensure category strategy exists"],
        "DTP-02": ["FMV check", "Market localization"],
        "DTP-03": ["Supplier MCDM criteria defined"],
        "DTP-04": ["DDR/HCC flags resolved", "Compliance approvals"],
        "DTP-05": ["Contracting guardrails"],
        "DTP-06": ["Savings validation & reporting"],
    }
    human_required = {
        "DTP-01": ["High-impact strategy shifts"],
        "DTP-02": ["Approach to market decisions"],
        "DTP-04": ["Supplier award / negotiation mandate"],
        "DTP-06": ["Savings sign-off"],
    }
    return {
        "allowed_actions": allowed_transitions.get(dtp_stage, []),
        "mandatory_checks": stage_checks.get(dtp_stage, []),
        "human_required_for": human_required.get(dtp_stage, []),
    }


def _initial_signal_register() -> list:
    """Initial empty signal register placeholder."""
    return []


def build_pipeline_state(
    case: Case,
    user_intent: str,
    use_tier_2: bool = False,
) -> PipelineState:
    """
    Construct a PipelineState for a given case and user intent.

    This mirrors the state built in `run_copilot` but is independent of Streamlit.
    """
    workflow_state: PipelineState = {
        "case_id": case.case_id,
        "dtp_stage": case.dtp_stage,
        "trigger_source": case.trigger_source,
        "user_intent": user_intent,
        "case_summary": case.summary,
        "latest_agent_output": case.latest_agent_output,
        "latest_agent_name": case.latest_agent_name,
        "activity_log": [],
        "human_decision": None,
        "budget_state": create_initial_budget_state(),
        "cache_meta": CacheMeta(
            cache_hit=False,
            cache_key=None,
            input_hash=None,
            schema_version="1.0",
        ),
        "error_state": None,
        "waiting_for_human": False,
        "use_tier_2": use_tier_2,
        "visited_agents": [],
        "iteration_count": 0,
        "dtp_policy_context": _build_policy_context(case.dtp_stage),
        "signal_register": _initial_signal_register(),
    }
    return workflow_state


def run_case_headless(
    case: Case,
    user_intent: str,
    use_tier_2: bool = False,
    recursion_limit: int = 30,
) -> Tuple[PipelineState, Case]:
    """
    Run a single case through the LangGraph workflow without Streamlit.

    Returns (final_state, updated_case_clone).
    """
    state = build_pipeline_state(case, user_intent=user_intent, use_tier_2=use_tier_2)
    graph = get_workflow_graph()
    final_state = graph.invoke(state, {"recursion_limit": recursion_limit})

    # Create an updated Case clone that reflects post‑run state
    updated_case_dict = case.model_dump()
    updated_case_dict["summary"] = final_state["case_summary"]
    updated_case_dict["dtp_stage"] = final_state["dtp_stage"]
    updated_case_dict["latest_agent_output"] = final_state.get("latest_agent_output")
    updated_case_dict["latest_agent_name"] = final_state.get("latest_agent_name")

    # Append activity_log from this run
    existing_log = list(case.activity_log or [])
    existing_log.extend(final_state.get("activity_log", []))
    updated_case_dict["activity_log"] = existing_log

    # Update timestamps
    now = datetime.now().isoformat()
    updated_case_dict["updated_timestamp"] = now
    updated_case_dict["updated_date"] = now.split("T")[0]

    updated_case = Case(**updated_case_dict)
    return final_state, updated_case


def _case_from_seed(seed: Dict[str, Any]) -> Case:
    """
    Build a Case instance from a single seed entry in `cases_seed.json`.
    Mirrors the initialization logic in `app.py` but without UI concerns.
    """
    case_data = dict(seed)

    # Map summary -> summary_text for CaseSummary
    case_summary_data = case_data.copy()
    if "summary" in case_summary_data and "summary_text" not in case_summary_data:
        case_summary_data["summary_text"] = case_summary_data.pop("summary")

    # Timestamps
    try:
        created_date_obj = datetime.strptime(case_data["created_date"], "%Y-%m-%d")
        created_ts = created_date_obj.isoformat()
    except Exception:
        created_ts = datetime.now().isoformat()
    updated_ts = created_ts

    summary = CaseSummary(
        case_id=case_data["case_id"],
        category_id=case_data["category_id"],
        contract_id=case_data.get("contract_id"),
        supplier_id=case_data.get("supplier_id"),
        dtp_stage=case_data["dtp_stage"],
        trigger_source=case_data["trigger_source"],
        status=case_data["status"],
        created_date=case_data["created_date"],
        summary_text=case_summary_data["summary_text"],
        key_findings=[],
        recommended_action=None,
    )

    case = Case(
        case_id=case_data["case_id"],
        name=case_data.get("name", case_data["case_id"]),
        category_id=case_data["category_id"],
        contract_id=case_data.get("contract_id"),
        supplier_id=case_data.get("supplier_id"),
        dtp_stage=case_data["dtp_stage"],
        trigger_source=case_data["trigger_source"],
        user_intent=None,
        created_date=case_data["created_date"],
        updated_date=case_data.get("updated_date", case_data["created_date"]),
        created_timestamp=created_ts,
        updated_timestamp=updated_ts,
        status=case_data["status"],
        summary=summary,
        latest_agent_output=None,
        latest_agent_name=None,
        activity_log=[],
        human_decision=None,
    )
    return case


def load_seed_cases() -> List[Case]:
    """Load all seed cases from `data/cases_seed.json` as `Case` models."""
    seeds = load_json_data("cases_seed.json")
    return [_case_from_seed(seed) for seed in seeds]


def run_all_seed_cases(
    user_intent: str = "What is the next best action I should take on this case?",
    use_tier_2: bool = False,
) -> List[Dict[str, Any]]:
    """
    Batch‑run all seed cases through the workflow.

    Returns a list of dicts summarizing each run:
    - case_id
    - initial_stage
    - final_stage
    - initial_status
    - final_status
    - dtp_stage_label
    - total_actions
    """
    results: List[Dict[str, Any]] = []
    for case in load_seed_cases():
        initial_stage = case.dtp_stage
        initial_status = case.status

        final_state, updated_case = run_case_headless(
            case, user_intent=user_intent, use_tier_2=use_tier_2
        )

        actions = final_state.get("activity_log", [])
        dtp_label = get_dtp_stage_display(final_state["dtp_stage"])

        results.append(
            {
                "case_id": updated_case.case_id,
                "initial_stage": initial_stage,
                "final_stage": updated_case.dtp_stage,
                "initial_status": initial_status,
                "final_status": updated_case.status,
                "dtp_stage_label": dtp_label,
                "total_actions": len(actions),
            }
        )

    return results



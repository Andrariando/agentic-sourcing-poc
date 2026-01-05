"""
Trace and export utilities for DTP case evaluation.

These helpers operate on `Case` objects and their `activity_log` to produce:
- Ordered case traces for JSON/CSV export
- Explicit DTP stage transition sequences
- Human‑in‑the‑loop (HIL) event summaries
"""

from __future__ import annotations

from typing import Any, Dict, List

from utils.schemas import Case, AgentActionLog


def _sorted_logs(case: Case) -> List[AgentActionLog]:
    """Return activity_log sorted by timestamp."""
    return sorted(case.activity_log or [], key=lambda log: log.timestamp)


def derive_dtp_transitions(case: Case) -> List[Dict[str, Any]]:
    """
    Derive an explicit DTP stage transition sequence from the case activity log.

    Looks for logs whose `output_payload` contains `old_stage` and `new_stage`,
    which are written when a human approves a decision.
    """
    transitions: List[Dict[str, Any]] = []
    for log in _sorted_logs(case):
        payload = log.output_payload or {}
        old_stage = payload.get("old_stage")
        new_stage = payload.get("new_stage")
        if old_stage and new_stage and old_stage != new_stage:
            transitions.append(
                {
                    "timestamp": log.timestamp,
                    "case_id": log.case_id,
                    "agent_name": log.agent_name,
                    "task_name": log.task_name,
                    "old_stage": old_stage,
                    "new_stage": new_stage,
                }
            )
    return transitions


def get_hil_events(case: Case) -> List[Dict[str, Any]]:
    """
    Extract Human‑in‑the‑Loop (HIL) events and their outcomes from the activity log.

    A HIL episode is identified by a `Workflow / Wait for Human Decision` log
    (guardrail_events includes 'Human-in-the-loop'), optionally paired with a
    subsequent `Human / Approve Decision` or `Human / Reject Decision` log.
    """
    logs = _sorted_logs(case)
    hil_events: List[Dict[str, Any]] = []

    # Index human decision logs for quick lookup
    human_logs = [
        log
        for log in logs
        if log.agent_name == "Human" and log.task_name in {"Approve Decision", "Reject Decision"}
    ]

    for log in logs:
        if "Human-in-the-loop" not in (log.guardrail_events or []):
            continue

        payload = log.output_payload or {}
        triggering_agent = payload.get("triggering_agent_name")
        triggering_output_type = payload.get("triggering_output_type")

        # Find the first human decision after this wait‑for‑human event
        decision_log = next(
            (h for h in human_logs if h.timestamp >= log.timestamp),
            None,
        )

        hil_events.append(
            {
                "case_id": log.case_id,
                "wait_timestamp": log.timestamp,
                "dtp_stage": log.dtp_stage,
                "triggering_agent_name": triggering_agent,
                "triggering_output_type": triggering_output_type,
                "decision": decision_log.task_name if decision_log else None,
                "decision_timestamp": decision_log.timestamp if decision_log else None,
            }
        )

    return hil_events


def export_case_trace(case: Case) -> Dict[str, Any]:
    """
    Export a complete case trace as a serializable dict suitable for JSON.

    Includes:
    - Basic case metadata
    - DTP transition sequence
    - HIL events
    - Full ordered activity log (Pydantic dicts)
    - Aggregate metrics (tokens, cost, cache hits)
    """
    logs = _sorted_logs(case)
    transitions = derive_dtp_transitions(case)
    hil_events = get_hil_events(case)

    total_tokens = sum(log.token_total for log in logs)
    total_cost = sum(log.estimated_cost_usd for log in logs)
    cache_hits = sum(1 for log in logs if log.cache_hit)

    return {
        "case_id": case.case_id,
        "category_id": case.category_id,
        "contract_id": case.contract_id,
        "supplier_id": case.supplier_id,
        "created_timestamp": case.created_timestamp,
        "updated_timestamp": case.updated_timestamp,
        "initial_stage": case.summary.dtp_stage,
        "final_stage": case.dtp_stage,
        "status": case.status,
        "dtp_transitions": transitions,
        "hil_events": hil_events,
        "activity_log": [log.model_dump() for log in logs],
        "metrics": {
            "total_actions": len(logs),
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "cache_hits": cache_hits,
        },
    }


def extract_execution_trace(updated_case: Case) -> List[Dict[str, Any]]:
    """
    Convert an executed sourcing case into a poster‑ready execution trace.

    Source of truth:
    - Steps: updated_case.activity_log (AgentActionLog)
    - HIL: AgentActionLog.guardrail_events (\"Human-in-the-loop\")
    - Halted: derived from HIL flag and final case status.
    """
    logs = _sorted_logs(updated_case)
    trace: List[Dict[str, Any]] = []

    if not logs:
        return trace

    terminal_statuses = {
        "Waiting for Human Decision",
        "Completed",
        "Rejected",
    }
    final_status = updated_case.status

    for idx, log in enumerate(logs, start=1):
        assert isinstance(log, AgentActionLog)
        hil_triggered = "Human-in-the-loop" in (log.guardrail_events or [])

        is_last_step = idx == len(logs)
        halted = False
        if hil_triggered:
            halted = True
        elif is_last_step and final_status in terminal_statuses:
            halted = True

        trace.append(
            {
                "step": idx,
                "dtp_stage": log.dtp_stage,
                "agent_name": log.agent_name,
                "decision_summary": log.output_summary,
                "hil_triggered": hil_triggered,
                "halted": halted,
            }
        )

    return trace












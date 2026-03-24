"""
Derive workflow ``case_context`` from persisted CaseDetail + supervisor state.

Seed data stores shortlists inside ``latest_agent_output`` and supplier on the case row,
not in a dedicated JSON column. LangGraph / readiness checks need the merged view.
"""
from __future__ import annotations

from typing import Any, Dict


def merge_derived_case_context(case: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    ctx: Dict[str, Any] = dict(state.get("case_context") or {})
    if case is None:
        return ctx
    sid = getattr(case, "supplier_id", None)
    summary = getattr(case, "summary", None)
    if not sid and summary is not None:
        sid = getattr(summary, "supplier_id", None)
    if sid:
        ctx.setdefault("selected_supplier_id", sid)
    lo = getattr(case, "latest_agent_output", None)
    if isinstance(lo, dict):
        finalists = lo.get("finalist_suppliers") or lo.get("shortlisted_suppliers")
        if finalists:
            ctx.setdefault("finalist_suppliers", finalists)
    return ctx

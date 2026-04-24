"""
LangGraph wrapper for System 1 bundle ingestion.

This graph orchestrates deterministic steps used by the upload scan flow:
parse/fuse -> score -> completeness analysis -> top-N prioritization.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from backend.heatmap.services.system1_bundle_scan import fuse_bundle_rows
from backend.heatmap.services.system1_scoring_orchestrator import (
    enrich_rows_for_preview,
    summarize_preview_completeness,
)


class System1IngestionState(TypedDict, total=False):
    rows_by_file: Dict[str, List[Dict[str, Any]]]
    parsing_notes: List[str]
    top_n: Optional[int]
    rank_by: Optional[str]
    row_builder: Callable[[Dict[str, Any], str, str, int], Any]
    fused_rows: List[Dict[str, Any]]
    candidates_all: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    analysis: Dict[str, Any]
    total_candidates: int
    valid_candidates: int
    execution_trace: List[str]


def _append_trace(state: System1IngestionState, step: str) -> List[str]:
    trace = list(state.get("execution_trace") or [])
    trace.append(step)
    return trace


def _fuse_node(state: System1IngestionState) -> Dict[str, Any]:
    fused_rows, notes = fuse_bundle_rows(state.get("rows_by_file") or {})
    parsing_notes = list(state.get("parsing_notes") or [])
    parsing_notes.extend(notes)
    return {
        "fused_rows": fused_rows,
        "parsing_notes": parsing_notes,
        "execution_trace": _append_trace(state, "fuse_bundle_rows"),
    }


def _score_node(state: System1IngestionState) -> Dict[str, Any]:
    builder = state.get("row_builder")
    if builder is None:
        raise ValueError("row_builder is required for system1 ingestion graph.")
    raw = state.get("fused_rows") or []
    candidates_all: List[Dict[str, Any]] = []
    for idx, row in enumerate(raw, start=1):
        candidates_all.append(builder(row, "bundle_scan", "structured", idx).model_dump())
    scored = enrich_rows_for_preview(candidates_all)
    for c in scored:
        warnings = list(dict.fromkeys([*(c.get("warnings") or []), *(c.get("readiness_warnings") or [])]))
        c["warnings"] = warnings
        c["valid_for_approval"] = bool(c.get("valid_for_approval") and c.get("readiness_status") != "needs_review")
    return {
        "candidates_all": scored,
        "execution_trace": _append_trace(state, "score_and_enrich_candidates"),
    }


def _analyze_node(state: System1IngestionState) -> Dict[str, Any]:
    candidates_all = state.get("candidates_all") or []
    analysis = summarize_preview_completeness(candidates_all)
    total = len(candidates_all)
    valid = sum(1 for c in candidates_all if bool(c.get("valid_for_approval")))
    return {
        "analysis": analysis,
        "total_candidates": total,
        "valid_candidates": valid,
        "execution_trace": _append_trace(state, "summarize_completeness"),
    }


def _prioritize_node(state: System1IngestionState) -> Dict[str, Any]:
    candidates = list(state.get("candidates_all") or [])
    top_n = state.get("top_n")
    rank_by = str(state.get("rank_by") or "completeness").strip().lower()
    if rank_by not in {"completeness", "score", "hybrid"}:
        rank_by = "completeness"
    parsing_notes = list(state.get("parsing_notes") or [])
    if rank_by == "score":
        sort_key = lambda c: (
            float(c.get("computed_total_score") or 0.0),
            float(c.get("completeness_score") or 0.0),
            float(c.get("computed_confidence") or 0.0),
            float(c.get("estimated_spend_usd") or 0.0),
        )
    elif rank_by == "hybrid":
        sort_key = lambda c: (
            (0.6 * float(c.get("completeness_score") or 0.0))
            + (0.3 * (10.0 * float(c.get("computed_confidence") or 0.0)))
            + (0.1 * float(c.get("computed_total_score") or 0.0)),
            float(c.get("computed_total_score") or 0.0),
            float(c.get("estimated_spend_usd") or 0.0),
        )
    else:
        sort_key = lambda c: (
            float(c.get("completeness_score") or 0.0),
            float(c.get("computed_confidence") or 0.0),
            float(c.get("computed_total_score") or 0.0),
            float(c.get("estimated_spend_usd") or 0.0),
        )
    if top_n is not None and top_n > 0 and len(candidates) > top_n:
        candidates = sorted(candidates, key=sort_key, reverse=True)[:top_n]
        parsing_notes.append(
            f"Applied top_n={top_n} with rank_by={rank_by}; returned {len(candidates)} rows."
        )
    else:
        candidates = sorted(candidates, key=sort_key, reverse=True)
    analysis = dict(state.get("analysis") or {})
    analysis["returned_rows"] = len(candidates)
    analysis["top_n_applied"] = int(top_n) if top_n is not None and top_n > 0 else None
    analysis["rank_by_applied"] = rank_by
    analysis["execution_trace"] = _append_trace(state, "prioritize_top_n")
    return {
        "candidates": candidates,
        "parsing_notes": parsing_notes,
        "analysis": analysis,
        "execution_trace": analysis["execution_trace"],
    }


def build_system1_ingestion_graph():
    graph = StateGraph(System1IngestionState)
    graph.add_node("fuse", _fuse_node)
    graph.add_node("score", _score_node)
    graph.add_node("analyze", _analyze_node)
    graph.add_node("prioritize", _prioritize_node)
    graph.set_entry_point("fuse")
    graph.add_edge("fuse", "score")
    graph.add_edge("score", "analyze")
    graph.add_edge("analyze", "prioritize")
    graph.add_edge("prioritize", END)
    return graph.compile()


_system1_ingestion_graph = None


def get_system1_ingestion_graph():
    global _system1_ingestion_graph
    if _system1_ingestion_graph is None:
        _system1_ingestion_graph = build_system1_ingestion_graph()
    return _system1_ingestion_graph


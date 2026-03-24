"""
LangGraph pipeline for the Heatmap Scoring Engine.

Architecture: For each opportunity in the input list, the graph runs 
four domain agents sequentially (spend → contract → strategy → risk),
then aggregates their signals via the supervisor. After the supervisor
scores the opportunity, the index is ticked and the loop continues
until all opportunities have been scored.

Note: A sequential chain is used instead of true parallel fan-out/fan-in
to maximize compatibility across LangGraph versions. The agents are
stateless and fast, so the performance difference is negligible.
"""
from langgraph.graph import StateGraph, END
from backend.heatmap.agents.state import HeatmapState
from backend.heatmap.agents.spend_agent import process_spend
from backend.heatmap.agents.contract_agent import process_contract
from backend.heatmap.agents.strategy_agent import process_strategy
from backend.heatmap.agents.risk_agent import process_risk
from backend.heatmap.agents.supervisor_agent import process_supervisor


def should_continue(state: HeatmapState) -> str:
    """Route: continue processing contracts or finish."""
    idx = state.get("current_index", 0)
    total = len(state.get("contracts", []))
    if idx < total:
        return "continue"
    return "done"


def tick_index(state: HeatmapState) -> dict:
    """Increment the contract index after the supervisor processes one."""
    return {"current_index": state.get("current_index", 0) + 1}


# Build the graph
builder = StateGraph(HeatmapState)

# Register nodes
builder.add_node("spend_agent", process_spend)
builder.add_node("contract_agent", process_contract)
builder.add_node("strategy_agent", process_strategy)
builder.add_node("risk_agent", process_risk)
builder.add_node("supervisor", process_supervisor)
builder.add_node("tick", tick_index)

# Define sequential chain per opportunity:
# spend → contract → strategy → risk → supervisor → tick → (loop or end)
builder.set_entry_point("spend_agent")
builder.add_edge("spend_agent", "contract_agent")
builder.add_edge("contract_agent", "strategy_agent")
builder.add_edge("strategy_agent", "risk_agent")
builder.add_edge("risk_agent", "supervisor")
builder.add_edge("supervisor", "tick")

builder.add_conditional_edges(
    "tick",
    should_continue,
    {
        "continue": "spend_agent",
        "done": END
    }
)

heatmap_graph = builder.compile()

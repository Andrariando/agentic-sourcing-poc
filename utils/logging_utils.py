"""
Logging utilities for agent actions.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from utils.schemas import AgentActionLog
from utils.state import PipelineState


def create_agent_log(
    case_id: str,
    dtp_stage: str,
    trigger_source: str,
    agent_name: str,
    task_name: str,
    model_used: str,
    token_input: int,
    token_output: int,
    estimated_cost_usd: float,
    cache_hit: bool,
    cache_key: Optional[str],
    input_hash: Optional[str],
    llm_input_payload: Dict[str, Any],
    output_payload: Dict[str, Any],
    output_summary: str,
    guardrail_events: list[str] = None
) -> AgentActionLog:
    """Create an AgentActionLog entry"""
    return AgentActionLog(
        timestamp=datetime.now().isoformat(),
        case_id=case_id,
        dtp_stage=dtp_stage,
        trigger_source=trigger_source,
        agent_name=agent_name,
        task_name=task_name,
        model_used=model_used,
        token_input=token_input,
        token_output=token_output,
        token_total=token_input + token_output,
        estimated_cost_usd=estimated_cost_usd,
        cache_hit=cache_hit,
        cache_key=cache_key,
        input_hash=input_hash,
        llm_input_payload=llm_input_payload,
        output_payload=output_payload,
        output_summary=output_summary,
        guardrail_events=guardrail_events or []
    )


def add_log_to_state(state: PipelineState, log: AgentActionLog) -> PipelineState:
    """Add log entry to state's activity_log"""
    state["activity_log"].append(log)
    return state



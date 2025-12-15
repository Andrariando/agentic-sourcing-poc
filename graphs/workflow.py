"""
LangGraph workflow for agentic sourcing pipeline.
Implements Supervisor coordination, specialist agents, and WAIT_FOR_HUMAN node.
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from utils.state import PipelineState
from utils.schemas import (
    CaseSummary, HumanDecision, BudgetState, AgentActionLog,
    StrategyRecommendation, SupplierShortlist, NegotiationPlan, SignalAssessment,
    SignalRegisterEntry
)
from utils.token_accounting import create_initial_budget_state, update_budget_state, calculate_cost
from utils.logging_utils import create_agent_log, add_log_to_state
from utils.caching import get_cache_meta
from agents.supervisor import SupervisorAgent
from agents.strategy_agent import StrategyAgent
from agents.supplier_agent import SupplierEvaluationAgent
from agents.negotiation_agent import NegotiationSupportAgent
from agents.signal_agent import SignalInterpretationAgent
from datetime import datetime
import json


# Lazy agent initialization - agents created on demand to avoid API key check at import time
_agent_cache = {}


def get_supervisor():
    """Get or create supervisor agent"""
    if "supervisor" not in _agent_cache:
        _agent_cache["supervisor"] = SupervisorAgent()
    return _agent_cache["supervisor"]


def get_strategy_agent(state: PipelineState):
    """Get strategy agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"strategy_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = StrategyAgent(tier=tier)
    return _agent_cache[cache_key]


def get_supplier_agent(state: PipelineState):
    """Get supplier agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"supplier_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = SupplierEvaluationAgent(tier=tier)
    return _agent_cache[cache_key]


def get_negotiation_agent(state: PipelineState):
    """Get negotiation agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"negotiation_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = NegotiationSupportAgent(tier=tier)
    return _agent_cache[cache_key]


def get_signal_agent(state: PipelineState):
    """Get signal agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"signal_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = SignalInterpretationAgent(tier=tier)
    return _agent_cache[cache_key]


def supervisor_node(state: PipelineState) -> PipelineState:
    """
    Supervisor node - Central coordinator for the agentic system.
    
    Responsibilities:
    1. Allocates tasks to specialized agents
    2. Reviews agent outputs
    3. Updates case summary (only Supervisor can do this)
    4. Decides if human approval is needed
    5. Coordinates with humans
    6. Routes to next agent or ends workflow
    """
    # Initialize loop detection if not present
    if "visited_agents" not in state:
        state["visited_agents"] = []
    if "iteration_count" not in state:
        state["iteration_count"] = 0
    
    # Increment iteration count
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    
    # Safety check: prevent infinite loops
    if state["iteration_count"] > 20:
        state["error_state"] = {
            "error": "Maximum iterations reached",
            "reason": "Workflow exceeded 20 Supervisor iterations. Possible infinite loop detected."
        }
        return state
    
    case_summary = state["case_summary"]
    latest_output = state.get("latest_agent_output")
    latest_agent_name = state.get("latest_agent_name", "Unknown")
    
    # Determine task description based on context
    task_description = "Coordinate Workflow"
    
    # Check if we're processing a human decision (injected externally)
    if state.get("human_decision"):
        task_description = "Process Human Decision"
        # Process the decision first
        state = process_human_decision(state)
        # Clear waiting flag and human_decision after processing
        state["waiting_for_human"] = False
        state["human_decision"] = None
        
        # If rejected, end here
        if state["case_summary"].status == "Rejected":
            # Log the rejection
            log = create_agent_log(
                case_id=case_summary.case_id,
                dtp_stage=state["dtp_stage"],
                trigger_source=state["trigger_source"],
                agent_name="Supervisor",
                task_name="Process Human Decision - Rejected",
                model_used="N/A (Supervisor Logic)",
                token_input=0,
                token_output=0,
                estimated_cost_usd=0.0,
                cache_hit=False,
                cache_key=None,
                input_hash=None,
                llm_input_payload={"decision": state.get("human_decision", {}).__dict__ if state.get("human_decision") else {}},
                output_payload={"status": "Rejected", "case_summary": state["case_summary"].__dict__},
                output_summary="Human decision: Rejected. Workflow terminated by Supervisor.",
                guardrail_events=[]
            )
            state = add_log_to_state(state, log)
            return state
    
    # If we just received output from a specialized agent, review it
    if latest_output:
        if isinstance(latest_output, StrategyRecommendation):
            task_description = "Review Strategy Recommendation & Update Case Summary"
        elif isinstance(latest_output, SupplierShortlist):
            task_description = "Review Supplier Shortlist & Update Case Summary"
        elif isinstance(latest_output, NegotiationPlan):
            task_description = "Review Negotiation Plan & Update Case Summary"
        elif isinstance(latest_output, SignalAssessment):
            task_description = "Review Signal Assessment & Update Case Summary"
    
    # Note: Human decision processing is now handled above in the task_description section
    
    # Supervisor updates case summary based on latest agent output
    # Update summary with findings
    key_findings = []
    recommended_action = None
    
    if latest_output:
        if isinstance(latest_output, StrategyRecommendation):
            key_findings = latest_output.rationale
            recommended_action = latest_output.recommended_strategy
        elif isinstance(latest_output, SupplierShortlist):
            key_findings = [f"Shortlisted {len(latest_output.shortlisted_suppliers)} suppliers"]
            recommended_action = latest_output.recommendation
        elif isinstance(latest_output, NegotiationPlan):
            key_findings = latest_output.negotiation_objectives
            recommended_action = "Proceed with negotiation"
        elif isinstance(latest_output, SignalAssessment):
            key_findings = latest_output.rationale
            recommended_action = latest_output.recommended_action
    
    # Update case summary (only Supervisor can do this)
    supervisor = get_supervisor()
    updated_summary = supervisor.update_case_summary(
        state,
        key_findings=key_findings,
        recommended_action=recommended_action
    )
    
    state["case_summary"] = updated_summary
    
    # Supervisor decides if human approval is needed
    # This is the key decision point where Supervisor coordinates with humans
    policy_context = state.get("dtp_policy_context", {})
    waiting_for_human = supervisor.should_wait_for_human(
        state["dtp_stage"],
        latest_output,
        policy_context
    )
    state["waiting_for_human"] = waiting_for_human
    
    # Supervisor determines next action
    user_intent = state.get("user_intent", "")
    next_agent = supervisor.determine_next_agent(state["dtp_stage"], latest_output, policy_context)
    
    # Create log entry for supervisor action
    output_summary = f"Supervisor reviewed case. Updated case summary. Status: {updated_summary.status}"
    
    if latest_agent_name != "Unknown":
        output_summary += f"\n• Received output from {latest_agent_name} agent"
        if latest_output:
            output_type = type(latest_output).__name__
            output_summary += f" ({output_type})"
    
    if waiting_for_human:
        output_summary += "\n• Decision: Waiting for human approval (HIL governance)"
    elif next_agent:
        output_summary += f"\n• Decision: Routing to {next_agent} agent"
    else:
        output_summary += f"\n• Decision: No further agent action needed for DTP-{state['dtp_stage']}"
        if user_intent:
            output_summary += f" (user asked: {user_intent[:40]}...)"
        # If terminal stage, mark completed
        if state["dtp_stage"] == "DTP-06":
            state["case_summary"].status = "Completed"
    
    log = create_agent_log(
        case_id=case_summary.case_id,
        dtp_stage=state["dtp_stage"],
        trigger_source=state["trigger_source"],
        agent_name="Supervisor",
        task_name=task_description,
        model_used="N/A (Supervisor Logic)",
        token_input=0,
        token_output=0,
        estimated_cost_usd=0.0,
        cache_hit=False,
        cache_key=None,
        input_hash=None,
        llm_input_payload={
            "latest_agent_output_type": type(latest_output).__name__ if latest_output else None,
            "latest_agent_name": latest_agent_name,
            "dtp_stage": state["dtp_stage"]
        },
        output_payload={
            "case_summary_updated": True,
            "status": updated_summary.status,
            "waiting_for_human": waiting_for_human,
            "key_findings_count": len(key_findings),
            "recommended_action": recommended_action
        },
        output_summary=output_summary,
        guardrail_events=[]
    )
    state = add_log_to_state(state, log)
    
    return state


def strategy_node(state: PipelineState) -> PipelineState:
    """Strategy Agent node (DTP-01)"""
    case_summary = state["case_summary"]
    user_intent = state.get("user_intent", "")
    budget_state = state["budget_state"]
    
    # Get agent with appropriate tier
    strategy_agent = get_strategy_agent(state)
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        # Use fallback
        fallback = strategy_agent.create_fallback_output(
            StrategyRecommendation,
            case_summary.case_id,
            case_summary.category_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "Strategy"
        state["error_state"] = {"error": "Budget exceeded", "used_fallback": True}
        return state
    
    try:
        # Call agent
        recommendation, llm_input, output_dict, input_tokens, output_tokens = strategy_agent.recommend_strategy(
            case_summary,
            user_intent,
            use_cache=True
        )
        
        # Update budget
        tier = 2 if state.get("use_tier_2") else 1
        updated_budget, budget_exceeded = update_budget_state(
            budget_state,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        state["budget_state"] = updated_budget
        
        # Create log
        cache_meta, _ = get_cache_meta(
            case_summary.case_id,
            "Strategy",
            user_intent.lower().strip(),
            case_summary,
            question_text=user_intent
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="Strategy",
            task_name="Recommend Strategy",
            model_used="gpt-4o" if tier == 2 else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=cache_meta.cache_hit,
            cache_key=cache_meta.cache_key,
            input_hash=cache_meta.input_hash,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Recommended: {recommendation.recommended_strategy}",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = recommendation
        state["latest_agent_name"] = "Strategy"
        
    except Exception as e:
        # Fallback
        fallback = strategy_agent.create_fallback_output(
            StrategyRecommendation,
            case_summary.case_id,
            case_summary.category_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "Strategy"
        state["error_state"] = {"error": str(e), "used_fallback": True}
    
    return state


def supplier_evaluation_node(state: PipelineState) -> PipelineState:
    """Supplier Evaluation Agent node (DTP-03/04)"""
    case_summary = state["case_summary"]
    budget_state = state["budget_state"]
    
    # Get agent with appropriate tier
    supplier_agent = get_supplier_agent(state)
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        fallback = supplier_agent.create_fallback_output(
            SupplierShortlist,
            case_summary.case_id,
            case_summary.category_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "SupplierEvaluation"
        return state
    
    try:
        shortlist, llm_input, output_dict, input_tokens, output_tokens = supplier_agent.evaluate_suppliers(
            case_summary,
            use_cache=True
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        updated_budget, budget_exceeded = update_budget_state(
            budget_state,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        state["budget_state"] = updated_budget
        
        cache_meta, _ = get_cache_meta(
            case_summary.case_id,
            "SupplierEvaluation",
            "supplier_evaluation",
            case_summary
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="SupplierEvaluation",
            task_name="Evaluate Suppliers",
            model_used="gpt-4o" if state.get("use_tier_2") else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=cache_meta.cache_hit,
            cache_key=cache_meta.cache_key,
            input_hash=cache_meta.input_hash,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Shortlisted {len(shortlist.shortlisted_suppliers)} suppliers",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = shortlist
        state["latest_agent_name"] = "SupplierEvaluation"
        
    except Exception as e:
        fallback = supplier_agent.create_fallback_output(
            SupplierShortlist,
            case_summary.case_id,
            case_summary.category_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "SupplierEvaluation"
        state["error_state"] = {"error": str(e), "used_fallback": True}
    
    return state


def negotiation_node(state: PipelineState) -> PipelineState:
    """Negotiation Support Agent node (DTP-04)"""
    case_summary = state["case_summary"]
    budget_state = state["budget_state"]
    
    # Get agent with appropriate tier
    negotiation_agent = get_negotiation_agent(state)
    
    # Get supplier_id from latest output or case summary
    supplier_id = case_summary.supplier_id
    if not supplier_id and state.get("latest_agent_output"):
        if isinstance(state["latest_agent_output"], SupplierShortlist):
            supplier_id = state["latest_agent_output"].top_choice_supplier_id
    
    if not supplier_id:
        state["error_state"] = {"error": "No supplier_id available for negotiation"}
        return state
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        fallback = negotiation_agent.create_fallback_output(
            NegotiationPlan,
            case_summary.case_id,
            case_summary.category_id,
            supplier_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "NegotiationSupport"
        return state
    
    try:
        plan, llm_input, output_dict, input_tokens, output_tokens = negotiation_agent.create_negotiation_plan(
            case_summary,
            supplier_id,
            use_cache=True
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        updated_budget, budget_exceeded = update_budget_state(
            budget_state,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        state["budget_state"] = updated_budget
        
        cache_meta, _ = get_cache_meta(
            case_summary.case_id,
            "NegotiationSupport",
            "negotiation_plan",
            case_summary,
            additional_inputs={"supplier_id": supplier_id}
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="NegotiationSupport",
            task_name="Create Negotiation Plan",
            model_used="gpt-4o" if tier == 2 else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=cache_meta.cache_hit,
            cache_key=cache_meta.cache_key,
            input_hash=cache_meta.input_hash,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Created negotiation plan for {supplier_id}",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = plan
        state["latest_agent_name"] = "NegotiationSupport"
        
    except Exception as e:
        fallback = negotiation_agent.create_fallback_output(
            NegotiationPlan,
            case_summary.case_id,
            case_summary.category_id,
            supplier_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "NegotiationSupport"
        state["error_state"] = {"error": str(e), "used_fallback": True}
    
    return state


def signal_interpretation_node(state: PipelineState, signal: dict) -> PipelineState:
    """Signal Interpretation Agent node"""
    case_summary = state["case_summary"]
    budget_state = state["budget_state"]
    
    # Get agent with appropriate tier
    signal_agent = get_signal_agent(state)
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        fallback = signal_agent.create_fallback_output(
            SignalAssessment,
            signal.get("signal_id", ""),
            signal.get("category_id", "")
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "SignalInterpretation"
        return state
    
    try:
        assessment, llm_input, output_dict, input_tokens, output_tokens = signal_agent.interpret_signal(
            signal,
            case_summary,
            use_cache=True
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        updated_budget, budget_exceeded = update_budget_state(
            budget_state,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        state["budget_state"] = updated_budget
        
        cache_meta, _ = get_cache_meta(
            case_summary.case_id,
            "SignalInterpretation",
            "signal_interpretation",
            case_summary,
            question_text=signal.get("description", "")
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="SignalInterpretation",
            task_name="Interpret Signal",
            model_used="gpt-4o" if tier == 2 else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=cache_meta.cache_hit,
            cache_key=cache_meta.cache_key,
            input_hash=cache_meta.input_hash,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Recommended: {assessment.recommended_action}",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = assessment
        state["latest_agent_name"] = "SignalInterpretation"
        
        # Persist to signal register
        signal_register = state.get("signal_register", [])
        signal_entry = SignalRegisterEntry(
            signal_type=signal.get("signal_type", "Unknown"),
            severity=signal.get("severity", "Low"),
            confidence=assessment.confidence,
            source="agent",
            timestamp=datetime.now().isoformat(),
            metadata={
                "contract_id": signal.get("contract_id"),
                "supplier_id": signal.get("supplier_id"),
                "recommended_action": assessment.recommended_action,
                "urgency_score": assessment.urgency_score,
            }
        )
        signal_register.append(signal_entry)
        state["signal_register"] = signal_register
        
    except Exception as e:
        fallback = signal_agent.create_fallback_output(
            SignalAssessment,
            signal.get("signal_id", ""),
            signal.get("category_id", "")
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "SignalInterpretation"
        state["error_state"] = {"error": str(e), "used_fallback": True}
    
    return state


def wait_for_human_node(state: PipelineState) -> PipelineState:
    """
    WAIT_FOR_HUMAN node - pauses workflow for human decision.
    
    This node ENDS the workflow. Human decision must be injected externally
    via inject_human_decision(), then workflow is re-invoked.
    """
    case_summary = state["case_summary"]

    # Capture which agent/output triggered the HIL pause for later analysis
    latest_agent_name = state.get("latest_agent_name")
    latest_output = state.get("latest_agent_output")
    latest_output_type = type(latest_output).__name__ if latest_output is not None else None

    # Log the wait state
    log = create_agent_log(
        case_id=case_summary.case_id,
        dtp_stage=state["dtp_stage"],
        trigger_source=state["trigger_source"],
        agent_name="Workflow",
        task_name="Wait for Human Decision",
        model_used="N/A (Workflow Pause)",
        token_input=0,
        token_output=0,
        estimated_cost_usd=0.0,
        cache_hit=False,
        cache_key=None,
        input_hash=None,
        llm_input_payload={
            "waiting_reason": "Human-in-the-loop decision required",
            "latest_agent_output_type": latest_output_type,
            "latest_agent_name": latest_agent_name,
        },
        output_payload={
            "status": "Paused",
            "waiting_for_human": True,
            "triggering_agent_name": latest_agent_name,
            "triggering_output_type": latest_output_type,
        },
        output_summary="Workflow paused - waiting for human decision. Human must inject decision externally via inject_human_decision().",
        guardrail_events=["Human-in-the-loop"]
    )
    state = add_log_to_state(state, log)
    
    # Mark that we're waiting - workflow will END here
    state["waiting_for_human"] = True
    return state


def check_human_decision(state: PipelineState) -> Literal["approved", "rejected", "waiting"]:
    """Check if human has made a decision"""
    human_decision = state.get("human_decision")
    if not human_decision:
        return "waiting"
    if human_decision.decision == "Approve":
        return "approved"
    return "rejected"


def process_human_decision(state: PipelineState) -> PipelineState:
    """Process human decision and continue workflow"""
    human_decision = state.get("human_decision")
    if not human_decision:
        return state
    
    case_summary = state["case_summary"]
    
    if human_decision.decision == "Approve":
        # Apply any edits from human
        if human_decision.edited_fields and state.get("latest_agent_output"):
            # Update output with edits (simplified)
            output = state["latest_agent_output"]
            for key, value in human_decision.edited_fields.items():
                if hasattr(output, key):
                    setattr(output, key, value)
        
        # Advance DTP stage if needed
        policy_context = state.get("dtp_policy_context", {})
        supervisor = get_supervisor()
        old_stage = state["dtp_stage"]
        new_stage = supervisor.advance_dtp_stage(old_stage, policy_context)
        state["dtp_stage"] = new_stage
        state["case_summary"].dtp_stage = new_stage
        
        state["waiting_for_human"] = False
        # If we reached terminal stage, mark completed; else in-progress
        state["case_summary"].status = "Completed" if new_stage == "DTP-06" else "In Progress"
        
        # Log the approval
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="Human",
            task_name="Approve Decision",
            model_used="N/A (Human Decision)",
            token_input=0,
            token_output=0,
            estimated_cost_usd=0.0,
            cache_hit=False,
            cache_key=None,
            input_hash=None,
            llm_input_payload={
                "decision": human_decision.decision,
                "reason": human_decision.reason,
                "edited_fields": human_decision.edited_fields or {}
            },
            output_payload={
                "status": "Approved",
                "dtp_stage_advanced": old_stage != new_stage,
                "old_stage": old_stage,
                "new_stage": new_stage
            },
            output_summary=f"Human approved decision. DTP stage: {old_stage} → {new_stage}",
            guardrail_events=[]
        )
        state = add_log_to_state(state, log)
    else:
        # Rejected - stay at current stage, clear latest output
        state["waiting_for_human"] = False
        state["case_summary"].status = "Rejected"
        # Don't clear latest_agent_output so user can see what was rejected
        
        # Log the rejection
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="Human",
            task_name="Reject Decision",
            model_used="N/A (Human Decision)",
            token_input=0,
            token_output=0,
            estimated_cost_usd=0.0,
            cache_hit=False,
            cache_key=None,
            input_hash=None,
            llm_input_payload={
                "decision": human_decision.decision,
                "reason": human_decision.reason
            },
            output_payload={
                "status": "Rejected",
                "workflow_terminated": True
            },
            output_summary=f"Human rejected decision. Reason: {human_decision.reason or 'No reason provided'}",
            guardrail_events=["Workflow Terminated"]
        )
        state = add_log_to_state(state, log)
    
    return state


def route_after_strategy(state: PipelineState) -> Literal["wait_for_human", "end"]:
    """Route after strategy recommendation"""
    if state.get("waiting_for_human"):
        return "wait_for_human"
    return "end"


def route_after_supplier(state: PipelineState) -> Literal["wait_for_human", "negotiation", "end"]:
    """Route after supplier evaluation"""
    if state.get("waiting_for_human"):
        return "wait_for_human"
    # Check if we need negotiation
    if state["dtp_stage"] == "DTP-04":
        return "negotiation"
    return "end"


def route_after_negotiation(state: PipelineState) -> Literal["wait_for_human", "end"]:
    """Route after negotiation plan"""
    if state.get("waiting_for_human"):
        return "wait_for_human"
    return "end"


# Build graph
def create_workflow_graph():
    """Create the LangGraph workflow"""
    workflow = StateGraph(PipelineState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("strategy", strategy_node)
    workflow.add_node("supplier_evaluation", supplier_evaluation_node)
    workflow.add_node("negotiation", negotiation_node)
    workflow.add_node("wait_for_human", wait_for_human_node)
    workflow.add_node("process_decision", process_human_decision)
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add edges - Supervisor is the central coordinator
    def route_from_supervisor(state: PipelineState) -> Literal["strategy", "supplier_evaluation", "negotiation", "wait_for_human", "end"]:
        """
        Supervisor routing logic - decides which agent to allocate task to.
        
        Flow:
        1. If waiting for human AND no decision yet → END (workflow paused, human must inject decision)
        2. If waiting for human AND has decision → Process decision, then route
        3. If just received agent output → Supervisor reviews it → Then decides: wait_for_human, next agent, or end
        4. If no agent output yet → Allocate task to appropriate agent
        """
        # Initialize visited_agents if not present
        visited_agents = state.get("visited_agents", [])
        
        # If Supervisor determined we need human approval AND no decision yet → END workflow
        # Human must inject decision externally via inject_human_decision()
        # Then workflow is re-invoked with human_decision in state
        if state.get("waiting_for_human") and not state.get("human_decision"):
            return "wait_for_human"  # Route to wait_for_human node, which will END the workflow
        
        # If we have a human decision, Supervisor will process it (handled in supervisor_node)
        # After processing, continue with normal routing
        
        dtp_stage = state["dtp_stage"]
        user_intent = state.get("user_intent", "").lower()
        latest_output = state.get("latest_agent_output")
        latest_agent_name = state.get("latest_agent_name")
        policy_context = state.get("dtp_policy_context", {})
        
        # If we just received output from an agent, Supervisor has already reviewed it
        # Now Supervisor decides next step based on the output
        if latest_output and latest_agent_name:
            # Check if Supervisor determined we need human approval
            supervisor = get_supervisor()
            waiting_for_human = supervisor.should_wait_for_human(dtp_stage, latest_output, policy_context)
            
            if waiting_for_human:
                # Supervisor requires human approval before proceeding
                # This will route to wait_for_human node, which ENDs the workflow
                return "wait_for_human"
            
            # Supervisor reviewed the output and determined next action
            next_agent = supervisor.determine_next_agent(dtp_stage, latest_output)
            
            # Loop prevention: Don't route to same agent-output combination twice
            agent_key = f"{latest_agent_name}_{type(latest_output).__name__}"
            if agent_key in visited_agents:
                # We've already processed this agent's output - end to prevent loop
                return "end"
            
            # Track this agent visit (keep last 5 to prevent loops)
            visited_agents.append(agent_key)
            if len(visited_agents) > 5:
                visited_agents = visited_agents[-5:]  # Keep only last 5
            state["visited_agents"] = visited_agents
            
            # If Supervisor says we need another agent, route there
            if next_agent == "Strategy":
                return "strategy"
            elif next_agent == "SupplierEvaluation":
                return "supplier_evaluation"
            elif next_agent == "NegotiationSupport":
                return "negotiation"
            else:
                # Supervisor determined no further agent action needed
                return "end"
        
        # No agent output yet - Supervisor allocates initial task
        # Priority 1: Check user intent for explicit requests (user intent overrides stage)
        if any(keyword in user_intent for keyword in ["strategy", "analyze", "recommend", "analysis", "what should"]):
            if dtp_stage in ["DTP-01", "DTP-02", "DTP-03"]:
                return "strategy"
        
        if any(keyword in user_intent for keyword in ["supplier", "evaluate", "sourcing", "market scan", "identify suppliers"]):
            if dtp_stage in ["DTP-02", "DTP-03", "DTP-04"]:
                return "supplier_evaluation"
        
        # Priority 2: Route based on DTP stage and case state
        if dtp_stage == "DTP-01":
            return "strategy"
        elif dtp_stage == "DTP-02":
            # DTP-02 (Planning) - check if we need to run strategy first
            if not latest_output or not isinstance(latest_output, StrategyRecommendation):
                return "strategy"
            elif any(keyword in user_intent for keyword in ["proceed", "next", "continue", "supplier", "evaluate"]):
                return "supplier_evaluation"
            else:
                return "end"
        elif dtp_stage in ["DTP-03", "DTP-04"]:
            return "supplier_evaluation"
        else:
            return "end"
    
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "strategy": "strategy",
            "supplier_evaluation": "supplier_evaluation",
            "negotiation": "negotiation",
            "wait_for_human": "wait_for_human",
            "end": END
        }
    )
    
    # CRITICAL ARCHITECTURE: All specialized agents MUST route back to Supervisor
    # This ensures Supervisor is always in control and can coordinate with humans
    # Flow: Supervisor → Agent → Supervisor → (Human/Next Agent/End)
    workflow.add_edge("strategy", "supervisor")  # Strategy agent reports back to Supervisor
    workflow.add_edge("supplier_evaluation", "supervisor")  # Supplier agent reports back to Supervisor
    workflow.add_edge("negotiation", "supervisor")  # Negotiation agent reports back to Supervisor
    
    # CRITICAL: wait_for_human should END the workflow (pause it)
    # Human decision must be injected externally via inject_human_decision()
    # Then workflow is re-invoked with the human_decision in state
    workflow.add_edge("wait_for_human", END)  # Pause workflow - human injects decision externally
    
    # Note: The conditional edge from supervisor (defined above) handles routing after:
    # - Initial task allocation
    # - Agent output review
    # - Human decision processing
    
    return workflow.compile()


# Global graph instance
workflow_graph = None

def get_workflow_graph():
    """Get or create workflow graph"""
    global workflow_graph
    if workflow_graph is None:
        workflow_graph = create_workflow_graph()
    return workflow_graph


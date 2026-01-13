"""
LangGraph workflow for agentic sourcing pipeline.
Implements Supervisor coordination, specialist agents, and WAIT_FOR_HUMAN node.
"""
from typing import Literal, Any, Tuple, Optional, Dict, List
from langgraph.graph import StateGraph, END
from utils.state import PipelineState
from utils.schemas import (
    CaseSummary, HumanDecision, BudgetState, AgentActionLog,
    StrategyRecommendation, SupplierShortlist, NegotiationPlan, SignalAssessment,
    SignalRegisterEntry, ClarificationRequest, OutOfScopeNotice, CaseTrigger,
    RFxDraft, ContractExtraction, ImplementationPlan
)
from utils.token_accounting import create_initial_budget_state, update_budget_state, calculate_cost
from utils.logging_utils import create_agent_log, add_log_to_state
from utils.caching import get_cache_meta
from agents.supervisor import SupervisorAgent
from agents.strategy_agent import StrategyAgent
from agents.supplier_agent import SupplierEvaluationAgent
from agents.negotiation_agent import NegotiationSupportAgent
from agents.signal_agent import SignalInterpretationAgent
from agents.case_clarifier_agent import CaseClarifierAgent
from agents.rfx_draft_agent import RFxDraftAgent
from agents.contract_support_agent import ContractSupportAgent
from agents.implementation_agent import ImplementationAgent
from utils.policy_loader import PolicyLoader
from utils.signal_aggregator import SignalAggregator
from utils.agent_validator import validate_agent_output, ValidationResult
from utils.contradiction_detector import detect_contradictions, Contradiction
from utils.case_memory import CaseMemory, update_memory_from_workflow_result
from utils.execution_constraints import ExecutionConstraints
from utils.constraint_compliance import (
    get_constraint_compliance_checker,
    generate_constraint_reflection,
    ComplianceStatus,
    ComplianceResult,
)
from datetime import datetime
import json
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser


# Lazy agent initialization - agents created on demand to avoid API key check at import time
_agent_cache = {}


def _is_error_output(output) -> bool:
    """
    Detect if an agent output is an error/fallback that should allow retry.
    This prevents loop prevention from blocking retries of failed operations.
    
    Returns True if the output appears to be a fallback/error output.
    """
    if output is None:
        return False
    
    # Check for SupplierShortlist errors
    if isinstance(output, SupplierShortlist):
        return (
            len(output.shortlisted_suppliers) == 0 and
            ("error" in output.comparison_summary.lower() or
             "fallback" in output.comparison_summary.lower() or
             "unable" in output.recommendation.lower())
        )
    
    # Check for StrategyRecommendation errors
    if isinstance(output, StrategyRecommendation):
        return (
            output.confidence < 0.5 and
            any("fallback" in r.lower() or "error" in r.lower() for r in (output.rationale or []))
        )
    
    # Check for NegotiationPlan errors
    if isinstance(output, NegotiationPlan):
        return (
            len(output.negotiation_objectives) == 0 or
            any("fallback" in obj.lower() for obj in output.negotiation_objectives)
        )
    
    # Check for RFxDraft errors
    if isinstance(output, RFxDraft):
        return (
            len(output.rfx_sections) == 0 or
            "fallback" in output.explanation.lower() or
            "error" in output.explanation.lower()
        )
    
    # Check for ContractExtraction errors
    if isinstance(output, ContractExtraction):
        return (
            len(output.extracted_terms) == 0 or
            any("fallback" in inc.lower() for inc in output.inconsistencies)
        )
    
    # Check for ImplementationPlan errors
    if isinstance(output, ImplementationPlan):
        return (
            len(output.rollout_steps) == 0 or
            "fallback" in output.explanation.lower() or
            "error" in output.explanation.lower()
        )
    
    # Check for SignalAssessment errors
    if isinstance(output, SignalAssessment):
        return (
            "fallback" in output.assessment.lower() or
            "unable" in output.assessment.lower()
        )
    
    return False


def _check_constraint_compliance(
    state: PipelineState,
    agent_output: Any,
    agent_name: str
) -> Tuple[ComplianceResult, str]:
    """
    PHASE 3: Check if agent output complies with all active ExecutionConstraints.
    
    ARCHITECTURAL INVARIANT:
    No execution output is valid unless it explicitly accounts for every active constraint.
    Silence is forbidden.
    
    Returns:
        Tuple of (ComplianceResult, required_reflection_text)
    """
    execution_constraints = state.get("execution_constraints")
    
    if not execution_constraints:
        return ComplianceResult(
            status=ComplianceStatus.NO_CONSTRAINTS,
            violations=[],
            addressed_constraints=[],
            required_acknowledgment="",
            blocking=False
        ), ""
    
    # Run compliance check
    checker = get_constraint_compliance_checker()
    result = checker.check_compliance(agent_output, execution_constraints, agent_name)
    
    # Generate required reflection text
    reflection = generate_constraint_reflection(execution_constraints)
    
    # Log compliance result
    if result.status == ComplianceStatus.NON_COMPLIANT:
        print(f"[WARNING] COMPLIANCE VIOLATION [{agent_name}]: {len(result.violations)} constraint(s) not addressed")
        for v in result.violations:
            print(f"   - {v.constraint_name}: {v.expected_behavior}")
    elif result.status == ComplianceStatus.COMPLIANT:
        print(f"[OK] COMPLIANT [{agent_name}]: All {len(result.addressed_constraints)} constraint(s) addressed")
    
    return result, reflection


def decide_next_agent_llm(
    state: PipelineState,
    user_intent: str
) -> Tuple[Optional[str], str]:
    """
    Decide next agent using LLM reasoning (Autonomy Layer).
    Used when deterministic rules have no prior output to guide them.
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None, "no_api_key_fallback"

        llm = ChatOpenAI(
            model="gpt-4o-mini", # Fast model for routing
            temperature=0,
            api_key=api_key
        )
        
        dtp_stage = state.get("dtp_stage", "DTP-01")
        has_output = state.get("latest_agent_output") is not None
        
        system_prompt = f"""You are the Sourcing Supervisor. Your job is to route user requests to the correct specialist agent.
        
Current Stage: {dtp_stage}
Has Prior Output: {has_output}
        
Available Agents & Capabilities:
- SignalInterpretation: Analyze spend, risks, market signals, costs, anomalies. (Use for: "Why are costs up?", "Check risks", "Scan signals")
- Strategy: Plan sourcing events, recommend renewal vs market test. (Use for: "Recommend strategy", "What should we do?")
- SupplierEvaluation: Score, rank, or compare suppliers. (Use for: "Compare suppliers", "Who is best?")
- RFxDraft: Create/Draft RFP, RFQ, RFI documents. (Use for: "Draft RFP", "Create requirements")
- NegotiationSupport: Plan negotiations, BATNA, leverage. (Use for: "Plan negotiation", "How to negotiate?")
- ContractSupport: Extract or review contract terms. (Use for: "Check contract", "Extract terms")
- Implementation: Plan rollout, KPIs, savings tracking. (Use for: "Implementation plan")

Routing Rules:
1. If the user asks a question that requires NEW data/analysis, call the relevant agent.
2. If the user asks "Why", "What", "How" about domain topics (spend, risk, strategy), CALL AN AGENT to get the answer. Do NOT assume we have it.
3. EXCEPTION: If 'Has Prior Output' is True AND the user asks to EXPLAIN/JUSTIFY that output (e.g. "Why did you say that?", "How did you calculate confidence?"), return "next_agent": null. The system will handle the explanation.
4. If the user just says "Hi" or checks status without asking for work, return "next_agent": null.

Return JSON ONLY:
{{
    "next_agent": "AgentName" or null,
    "reason": "Why you chose this agent"
}}
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"User Request: {user_intent}")
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "")
        
        result = json.loads(content)
        agent = result.get("next_agent")
        reason = result.get("reason", "LLM reasoning")
        
        # Map simple names to class/internal names if needed
        name_map = {
            "SignalInterpretation": "SignalInterpretation",
            "Strategy": "Strategy",
            "SupplierEvaluation": "SupplierEvaluation",
            "RFxDraft": "RFxDraft",
            "NegotiationSupport": "NegotiationSupport",
            "ContractSupport": "ContractSupport",
            "Implementation": "Implementation"
        }
        
        if agent in name_map:
            return name_map[agent], f"llm_route: {reason}"
            
        return None, "llm_no_route"
        
    except Exception as e:
        print(f"[WARNING] LLM Routing failed: {e}")
        return None, "llm_error_fallback"




# Import Tuple for type hint
from typing import Tuple


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


def get_case_clarifier_agent(state: PipelineState):
    """Get case clarifier agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"clarifier_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = CaseClarifierAgent(tier=tier)
    return _agent_cache[cache_key]


def get_rfx_draft_agent(state: PipelineState):
    """Get RFx draft agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"rfx_draft_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = RFxDraftAgent(tier=tier)
    return _agent_cache[cache_key]


def get_contract_support_agent(state: PipelineState):
    """Get contract support agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"contract_support_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = ContractSupportAgent(tier=tier)
    return _agent_cache[cache_key]


def get_implementation_agent(state: PipelineState):
    """Get implementation agent with appropriate tier"""
    tier = 2 if state.get("use_tier_2") else 1
    cache_key = f"implementation_{tier}"
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = ImplementationAgent(tier=tier)
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
    # PHASE 2: Validate agent output and detect contradictions
    if latest_output:
        if isinstance(latest_output, StrategyRecommendation):
            task_description = "Review Strategy Recommendation & Update Case Summary"
        elif isinstance(latest_output, SupplierShortlist):
            task_description = "Review Supplier Shortlist & Update Case Summary"
        elif isinstance(latest_output, RFxDraft):
            task_description = "Review RFx Draft & Update Case Summary"
        elif isinstance(latest_output, NegotiationPlan):
            task_description = "Review Negotiation Plan & Update Case Summary"
        elif isinstance(latest_output, ContractExtraction):
            task_description = "Review Contract Extraction & Update Case Summary"
        elif isinstance(latest_output, ImplementationPlan):
            task_description = "Review Implementation Plan & Update Case Summary"
        elif isinstance(latest_output, SignalAssessment):
            task_description = "Review Signal Assessment & Update Case Summary"
        elif isinstance(latest_output, ClarificationRequest):
            task_description = "Review Clarification Request"
        
        # PHASE 2 - OBJECTIVE C: Validate agent output in code
        policy_context_for_validation = state.get("dtp_policy_context", {})
        validation_context = {}
        if policy_context_for_validation:
            if hasattr(policy_context_for_validation, "allowed_strategies"):
                validation_context["allowed_strategies"] = policy_context_for_validation.allowed_strategies
            elif isinstance(policy_context_for_validation, dict):
                validation_context["allowed_strategies"] = policy_context_for_validation.get("allowed_strategies")
        
        validation_result = validate_agent_output(latest_agent_name, latest_output, validation_context)
        
        if not validation_result.is_valid:
            # Log validation violations
            state["validation_violations"] = validation_result.violations
            # Add to guardrail events
            if "guardrail_events" not in state:
                state["guardrail_events"] = []
            for violation in validation_result.violations:
                state["guardrail_events"].append(f"VALIDATION: {violation}")
        
        if validation_result.warnings:
            if "validation_warnings" not in state:
                state["validation_warnings"] = []
            state["validation_warnings"].extend(validation_result.warnings)
        
        # PHASE 2 - OBJECTIVE E: Detect contradictions
        # Get previous outputs from state history if available
        previous_outputs = []
        output_history = state.get("output_history", [])
        for hist in output_history[-5:]:  # Check last 5 outputs
            if hist.get("output") is not None:
                previous_outputs.append((hist.get("agent", "Unknown"), hist.get("output")))
        
        # Get memory state for contradiction checking
        case_memory = state.get("case_memory")
        memory_state = None
        if case_memory and hasattr(case_memory, "current_strategy"):
            memory_state = {
                "current_strategy": case_memory.current_strategy,
                "current_supplier_choice": case_memory.current_supplier_choice,
                "human_decisions": case_memory.human_decisions if hasattr(case_memory, "human_decisions") else []
            }
        
        contradictions = detect_contradictions(
            latest_output, latest_agent_name, previous_outputs, memory_state
        )
        
        if contradictions:
            # Store contradictions for surfacing to user
            state["detected_contradictions"] = [c.description for c in contradictions]
            # Add to guardrail events
            for c in contradictions:
                if "guardrail_events" not in state:
                    state["guardrail_events"] = []
                state["guardrail_events"].append(f"CONTRADICTION ({c.severity}): {c.description}")
    
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
        elif isinstance(latest_output, RFxDraft):
            key_findings = [f"RFx draft created with {len(latest_output.rfx_sections)} sections"]
            recommended_action = "Review RFx draft completeness"
        elif isinstance(latest_output, NegotiationPlan):
            key_findings = latest_output.negotiation_objectives
            recommended_action = "Proceed with negotiation"
        elif isinstance(latest_output, ContractExtraction):
            key_findings = [f"Extracted {len(latest_output.extracted_terms)} contract terms"]
            recommended_action = "Review contract extraction"
        elif isinstance(latest_output, ImplementationPlan):
            key_findings = [f"Implementation plan with {len(latest_output.rollout_steps)} steps"]
            recommended_action = "Proceed with implementation"
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
    
    # PHASE 2 - OBJECTIVE A: Update case memory after agent output
    case_memory = state.get("case_memory")
    if case_memory is None:
        from utils.case_memory import create_case_memory
        case_memory = create_case_memory(case_summary.case_id)
        state["case_memory"] = case_memory
    
    if latest_output and latest_agent_name:
        update_memory_from_workflow_result(
            case_memory,
            latest_agent_name,
            latest_output,
            user_intent=state.get("user_intent")
        )
        
        # Store output in history for contradiction detection
        if "output_history" not in state:
            state["output_history"] = []
        state["output_history"].append({
            "agent": latest_agent_name,
            "output": latest_output,
            "output_type": type(latest_output).__name__,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 10 outputs
        if len(state["output_history"]) > 10:
            state["output_history"] = state["output_history"][-10:]
    
    # Load policy context with trigger type for renewal constraints
    policy_loader = PolicyLoader()
    trigger_type = state.get("trigger_type")  # From CaseTrigger if proactive
    policy_context = state.get("dtp_policy_context", {})
    
    # If policy context is not loaded, load it now
    if not policy_context or (isinstance(policy_context, dict) and not policy_context):
        policy_context = policy_loader.load_policy_for_stage(
            state["dtp_stage"],
            case_summary.category_id,
            trigger_type
        )
        state["dtp_policy_context"] = policy_context
    
    # Enhanced routing with confidence and capability checks
    user_intent = state.get("user_intent", "")
    
    # HYBRID ROUTING STRATEGY (Rules > LLM)
    routing_source = "DETERMINISTIC_RULES" # Default
    
    # 1. Always try Deterministic Rules first (Maintains DTP Sequence & Guardrails)
    next_agent, routing_reason, clarification_request = supervisor.determine_next_agent_with_confidence(
        state["dtp_stage"],
        latest_output,
        policy_context,
        trigger_type,
        user_intent=user_intent
    )
    
    # 2. If Rules provided no direction (e.g. unhandled question or empty state), use LLM Autonomy
    if not next_agent and user_intent and not clarification_request:
        # Check rule-based overrides first (e.g., explicit status check)
        agent_llm, reason_llm = decide_next_agent_llm(state, user_intent)
        if agent_llm:
            next_agent = agent_llm
            routing_reason = reason_llm
            routing_source = "LLM_REASONING_AUTONOMY"
            # Verify capability again for safety (Guardian Check)
            if latest_output: # Only relevant if we are acting on output, but here we are routing
                 pass 
    
    # Check if clarification is needed
    needs_clarification = False
    if latest_output:
        confidence = getattr(latest_output, "confidence", None)
        missing_fields = []  # Could be populated from validation
        needs_clarification = supervisor.should_request_clarification(
            case_summary,
            latest_output,
            confidence,
            missing_fields
        )
    
    # If clarification needed, set up for clarifier agent
    if needs_clarification and routing_reason in ["low_confidence_clarification", "medium_confidence_policy_requires_human"]:
        state["clarification_reason"] = routing_reason
        if confidence is not None:
            state["missing_fields"] = []  # Could be enhanced with actual missing fields
        next_agent = "CaseClarifier"
    
    # Supervisor decides if human approval is needed
    waiting_for_human, wait_reason = supervisor.should_wait_for_human(
        state["dtp_stage"],
        latest_output,
        policy_context
    )
    state["waiting_for_human"] = waiting_for_human
    if waiting_for_human:
        state["wait_reason"] = wait_reason
        # CRITICAL FIX: Persist this status so ChatService doesn't clear output on reload
        updated_summary.status = "Waiting for Human Decision"
        state["case_summary"] = updated_summary
    
    # Create log entry for supervisor action
    output_summary = f"Supervisor reviewed case. Updated case summary. Status: {updated_summary.status}"
    
    if latest_agent_name != "Unknown":
        output_summary += f"\n• Received output from {latest_agent_name} agent"
        if latest_output:
            output_type = type(latest_output).__name__
            output_summary += f" ({output_type})"
    
    if waiting_for_human:
        output_summary += f"\n• Decision: Waiting for human approval (HIL governance) - {wait_reason}"
    elif next_agent == "CaseClarifier":
        output_summary += f"\n• Decision: Requesting clarification ({routing_reason})"
        output_summary += f"\n• Routing Source: {routing_source}"
    elif next_agent:
        output_summary += f"\n• Decision: Routing to {next_agent} agent ({routing_reason})"
        output_summary += f"\n• Routing Source: {routing_source}"
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
        model_used="N/A (Supervisor Logic)" if routing_source != "LLM_REASONING_AUTONOMY" else "gpt-4o-mini",
        token_input=0, # Minimal for routing
        token_output=0,
        estimated_cost_usd=0.0,
        cache_hit=False,
        cache_key=None,
        input_hash=None,
        llm_input_payload={
            "latest_agent_output_type": type(latest_output).__name__ if latest_output else None,
            "latest_agent_name": latest_agent_name,
            "dtp_stage": state["dtp_stage"],
            "user_intent": user_intent
        },
        output_payload={
            "case_summary_updated": True,
            "status": updated_summary.status,
            "waiting_for_human": waiting_for_human,
            "key_findings_count": len(key_findings),
            "recommended_action": recommended_action,
            "routing_decision": {
                "source": routing_source,
                "next_agent": next_agent,
                "reason": routing_reason
            }
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
        # Get policy constraints for renewal cases
        policy_context = state.get("dtp_policy_context", {})
        trigger_type = state.get("trigger_type")  # From CaseTrigger if proactive case
        allowed_strategies = None
        
        if policy_context:
            if isinstance(policy_context, dict):
                allowed_strategies = policy_context.get("allowed_strategies")
            else:
                allowed_strategies = getattr(policy_context, "allowed_strategies", None)
        
        # PHASE 3: Get execution constraints (binding user preferences)
        execution_constraints = state.get("execution_constraints")
        
        # Call agent with policy constraints AND execution constraints
        conversation_history = state.get("conversation_history")
        recommendation, llm_input, output_dict, input_tokens, output_tokens = strategy_agent.recommend_strategy(
            case_summary,
            user_intent,
            use_cache=True,
            allowed_strategies=allowed_strategies,
            trigger_type=trigger_type,
            execution_constraints=execution_constraints,
            conversation_history=conversation_history
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
        
        # PHASE 3: Run constraint compliance check (MANDATORY)
        compliance_result, reflection = _check_constraint_compliance(state, recommendation, "Strategy")
        state["constraint_compliance_status"] = compliance_result.status.value
        state["constraint_violations"] = [f"{v.constraint_name}: {v.expected_behavior}" for v in compliance_result.violations]
        state["constraint_reflection"] = reflection

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
        print(f"[WARNING] SupplierEvaluation budget exceeded: {budget_state.tokens_used} tokens used")
        fallback = supplier_agent.create_fallback_output(
            SupplierShortlist,
            case_summary.case_id,
            case_summary.category_id,
            error_msg="budget limit exceeded (3000 tokens)"
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "SupplierEvaluation"
        return state
    
    try:
        # PHASE 3: Get execution constraints (binding user preferences)
        execution_constraints = state.get("execution_constraints")
        
        shortlist, llm_input, output_dict, input_tokens, output_tokens = supplier_agent.evaluate_suppliers(
            case_summary,
            use_cache=True,
            execution_constraints=execution_constraints
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
        
        # PHASE 3: Run constraint compliance check (MANDATORY)
        compliance_result, reflection = _check_constraint_compliance(state, shortlist, "SupplierEvaluation")
        state["constraint_compliance_status"] = compliance_result.status.value
        state["constraint_violations"] = [f"{v.constraint_name}: {v.expected_behavior}" for v in compliance_result.violations]
        state["constraint_reflection"] = reflection

    except Exception as e:
        print(f"[WARNING] SupplierEvaluation workflow node exception: {type(e).__name__}: {str(e)}")
        fallback = supplier_agent.create_fallback_output(
            SupplierShortlist,
            case_summary.case_id,
            case_summary.category_id,
            error_msg=f"{type(e).__name__}: {str(e)[:100]}"
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
        
        # PHASE 3: Run constraint compliance check (MANDATORY)
        compliance_result, reflection = _check_constraint_compliance(state, plan, "NegotiationSupport")
        state["constraint_compliance_status"] = compliance_result.status.value
        state["constraint_violations"] = [f"{v.constraint_name}: {v.expected_behavior}" for v in compliance_result.violations]
        state["constraint_reflection"] = reflection

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


def rfx_draft_node(state: PipelineState) -> PipelineState:
    """RFx Draft Agent node (DTP-03) - Table 3 aligned"""
    case_summary = state["case_summary"]
    budget_state = state["budget_state"]
    
    # Get agent with appropriate tier
    rfx_agent = get_rfx_draft_agent(state)
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        fallback = rfx_agent.create_fallback_output(
            RFxDraft,
            case_summary.case_id,
            case_summary.category_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "RFxDraft"
        return state
    
    try:
        rfx_draft, llm_input, output_dict, input_tokens, output_tokens = rfx_agent.create_rfx_draft(
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
            "RFxDraft",
            "rfx_draft",
            case_summary
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="RFxDraft",
            task_name="Create RFx Draft",
            model_used="gpt-4o" if tier == 2 else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=cache_meta.cache_hit,
            cache_key=cache_meta.cache_key,
            input_hash=cache_meta.input_hash,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Created RFx draft with {len(rfx_draft.rfx_sections)} sections",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = rfx_draft
        state["latest_agent_name"] = "RFxDraft"
        
        # PHASE 3: Run constraint compliance check (MANDATORY)
        compliance_result, reflection = _check_constraint_compliance(state, rfx_draft, "RFxDraft")
        state["constraint_compliance_status"] = compliance_result.status.value
        state["constraint_violations"] = [f"{v.constraint_name}: {v.expected_behavior}" for v in compliance_result.violations]
        state["constraint_reflection"] = reflection

    except Exception as e:
        fallback = rfx_agent.create_fallback_output(
            RFxDraft,
            case_summary.case_id,
            case_summary.category_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "RFxDraft"
        state["error_state"] = {"error": str(e), "used_fallback": True}

    return state


def contract_support_node(state: PipelineState) -> PipelineState:
    """Contract Support Agent node (DTP-04/05) - Table 3 aligned"""
    case_summary = state["case_summary"]
    budget_state = state["budget_state"]
    
    # Get agent with appropriate tier
    contract_agent = get_contract_support_agent(state)
    
    # Get supplier_id from latest output or case summary
    supplier_id = case_summary.supplier_id
    if not supplier_id and state.get("latest_agent_output"):
        if isinstance(state["latest_agent_output"], NegotiationPlan):
            supplier_id = state["latest_agent_output"].supplier_id
        elif isinstance(state["latest_agent_output"], SupplierShortlist):
            supplier_id = state["latest_agent_output"].top_choice_supplier_id
    
    if not supplier_id:
        state["error_state"] = {"error": "No supplier_id available for contract extraction"}
        return state
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        fallback = contract_agent.create_fallback_output(
            ContractExtraction,
            case_summary.case_id,
            case_summary.category_id,
            supplier_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "ContractSupport"
        return state
    
    try:
        extraction, llm_input, output_dict, input_tokens, output_tokens = contract_agent.extract_contract_terms(
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
            "ContractSupport",
            "contract_extraction",
            case_summary,
            additional_inputs={"supplier_id": supplier_id}
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="ContractSupport",
            task_name="Extract Contract Terms",
            model_used="gpt-4o" if tier == 2 else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=cache_meta.cache_hit,
            cache_key=cache_meta.cache_key,
            input_hash=cache_meta.input_hash,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Extracted contract terms for {supplier_id}",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = extraction
        state["latest_agent_name"] = "ContractSupport"
        
        # PHASE 3: Run constraint compliance check (MANDATORY)
        compliance_result, reflection = _check_constraint_compliance(state, extraction, "ContractSupport")
        state["constraint_compliance_status"] = compliance_result.status.value
        state["constraint_violations"] = [f"{v.constraint_name}: {v.expected_behavior}" for v in compliance_result.violations]
        state["constraint_reflection"] = reflection

    except Exception as e:
        fallback = contract_agent.create_fallback_output(
            ContractExtraction,
            case_summary.case_id,
            case_summary.category_id,
            supplier_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "ContractSupport"
        state["error_state"] = {"error": str(e), "used_fallback": True}

    return state


def implementation_node(state: PipelineState) -> PipelineState:
    """Implementation Agent node (DTP-05/06) - Table 3 aligned"""
    case_summary = state["case_summary"]
    budget_state = state["budget_state"]
    
    # Get agent with appropriate tier
    implementation_agent = get_implementation_agent(state)
    
    # Get supplier_id from latest output or case summary
    supplier_id = case_summary.supplier_id
    if not supplier_id and state.get("latest_agent_output"):
        if isinstance(state["latest_agent_output"], ContractExtraction):
            supplier_id = state["latest_agent_output"].supplier_id
        elif isinstance(state["latest_agent_output"], NegotiationPlan):
            supplier_id = state["latest_agent_output"].supplier_id
    
    if not supplier_id:
        state["error_state"] = {"error": "No supplier_id available for implementation plan"}
        return state
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        fallback = implementation_agent.create_fallback_output(
            ImplementationPlan,
            case_summary.case_id,
            case_summary.category_id,
            supplier_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "Implementation"
        return state
    
    try:
        implementation_plan, llm_input, output_dict, input_tokens, output_tokens = implementation_agent.create_implementation_plan(
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
            "Implementation",
            "implementation_plan",
            case_summary,
            additional_inputs={"supplier_id": supplier_id}
        )
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="Implementation",
            task_name="Create Implementation Plan",
            model_used="gpt-4o" if tier == 2 else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=cache_meta.cache_hit,
            cache_key=cache_meta.cache_key,
            input_hash=cache_meta.input_hash,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Created implementation plan with {len(implementation_plan.rollout_steps)} steps",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = implementation_plan
        state["latest_agent_name"] = "Implementation"
        
        # PHASE 3: Run constraint compliance check (MANDATORY)
        compliance_result, reflection = _check_constraint_compliance(state, implementation_plan, "Implementation")
        state["constraint_compliance_status"] = compliance_result.status.value
        state["constraint_violations"] = [f"{v.constraint_name}: {v.expected_behavior}" for v in compliance_result.violations]
        state["constraint_reflection"] = reflection

    except Exception as e:
        fallback = implementation_agent.create_fallback_output(
            ImplementationPlan,
            case_summary.case_id,
            case_summary.category_id,
            supplier_id
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "Implementation"
        state["error_state"] = {"error": str(e), "used_fallback": True}

    return state


def case_clarifier_node(state: PipelineState) -> PipelineState:
    """Case Clarifier Agent node - generates targeted questions for humans"""
    case_summary = state["case_summary"]
    budget_state = state["budget_state"]
    latest_output = state.get("latest_agent_output")
    
    # Get agent with appropriate tier
    clarifier_agent = get_case_clarifier_agent(state)
    
    # Build context for clarification
    context = {
        "reason": state.get("clarification_reason", "Information needed for decision"),
        "confidence": getattr(latest_output, "confidence", None) if latest_output else None,
        "missing_fields": state.get("missing_fields", []),
        "policy_ambiguity": state.get("policy_ambiguity"),
        "multiple_paths": state.get("multiple_paths", [])
    }
    
    # Check budget
    if budget_state.tokens_used >= 3000:
        fallback = clarifier_agent.create_fallback_output(
            ClarificationRequest,
            case_summary.case_id,
            case_summary.category_id,
            context.get("reason", "Information needed")
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "CaseClarifier"
        return state
    
    try:
        clarification, llm_input, output_dict, input_tokens, output_tokens = clarifier_agent.request_clarification(
            case_summary,
            latest_output,
            context,
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
        
        tier = 2 if state.get("use_tier_2") else 1
        cost = calculate_cost(tier, input_tokens, output_tokens)
        log = create_agent_log(
            case_id=case_summary.case_id,
            dtp_stage=state["dtp_stage"],
            trigger_source=state["trigger_source"],
            agent_name="CaseClarifier",
            task_name="Request Clarification",
            model_used="gpt-4o" if tier == 2 else "gpt-4o-mini",
            token_input=input_tokens,
            token_output=output_tokens,
            estimated_cost_usd=cost,
            cache_hit=False,
            cache_key=None,
            input_hash=None,
            llm_input_payload=llm_input,
            output_payload=output_dict,
            output_summary=f"Clarification requested: {clarification.reason}",
            guardrail_events=["Budget exceeded"] if budget_exceeded else []
        )
        state = add_log_to_state(state, log)
        
        state["latest_agent_output"] = clarification
        state["latest_agent_name"] = "CaseClarifier"
        
    except Exception as e:
        fallback = clarifier_agent.create_fallback_output(
            ClarificationRequest,
            case_summary.case_id,
            case_summary.category_id,
            context.get("reason", "Information needed")
        )
        state["latest_agent_output"] = fallback
        state["latest_agent_name"] = "CaseClarifier"
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
        
        # Advance DTP stage if needed (with validation)
        policy_context = state.get("dtp_policy_context", {})
        supervisor = get_supervisor()
        old_stage = state["dtp_stage"]
        new_stage, error_msg = supervisor.advance_dtp_stage(old_stage, policy_context)
        
        if error_msg:
            # Transition validation failed - log error but don't advance
            state["error_state"] = {"error": "DTP transition validation failed", "reason": error_msg}
            state["case_summary"].status = "In Progress"  # Stay at current stage
        else:
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
    
    # Add nodes (Table 3 aligned)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("strategy", strategy_node)
    workflow.add_node("supplier_evaluation", supplier_evaluation_node)  # Supplier Scoring Agent (DTP-02/03)
    workflow.add_node("rfx_draft", rfx_draft_node)  # RFx Draft Agent (DTP-03)
    workflow.add_node("negotiation", negotiation_node)  # Negotiation Support Agent (DTP-04)
    workflow.add_node("contract_support", contract_support_node)  # Contract Support Agent (DTP-04/05)
    workflow.add_node("implementation", implementation_node)  # Implementation Agent (DTP-05/06)
    workflow.add_node("case_clarifier", case_clarifier_node)
    workflow.add_node("wait_for_human", wait_for_human_node)
    workflow.add_node("process_decision", process_human_decision)
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add edges - Supervisor is the central coordinator
    def route_from_supervisor(state: PipelineState) -> Literal["strategy", "supplier_evaluation", "rfx_draft", "negotiation", "contract_support", "implementation", "case_clarifier", "wait_for_human", "end"]:
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
            # Use enhanced routing with confidence and capability checks
            supervisor = get_supervisor()
            trigger_type = state.get("trigger_type")
            next_agent, routing_reason, clarification_request = supervisor.determine_next_agent_with_confidence(
                dtp_stage, latest_output, policy_context, trigger_type
            )
            
            # Check if clarification is needed
            if routing_reason in ["low_confidence_clarification", "medium_confidence_policy_requires_human"]:
                return "case_clarifier"
            
            # Check if Supervisor determined we need human approval
            waiting_for_human, wait_reason = supervisor.should_wait_for_human(dtp_stage, latest_output, policy_context)
            
            if waiting_for_human:
                # Supervisor requires human approval before proceeding
                state["wait_reason"] = wait_reason
                return "wait_for_human"
            
            # Loop prevention: Don't route to same agent-output combination twice
            agent_key = f"{latest_agent_name}_{type(latest_output).__name__}"
            is_error_output = _is_error_output(latest_output)
            
            # If error output detected, END the workflow immediately
            # The error will be shown in UI - user can fix issue and use "Reset Case State" to retry
            if is_error_output:
                print(f"[WARNING] Error output detected from {latest_agent_name} - ending workflow to show error to user")
                return "end"
            
            if agent_key in visited_agents:
                # We've already processed this agent's output - end to prevent loop
                return "end"
            
            # Track this agent visit (keep last 5 to prevent loops)
            visited_agents.append(agent_key)
            if len(visited_agents) > 5:
                visited_agents = visited_agents[-5:]  # Keep only last 5
            state["visited_agents"] = visited_agents
            
            # If Supervisor says we need another agent, route there (Table 3 alignment)
            if next_agent == "Strategy":
                return "strategy"
            elif next_agent == "SupplierEvaluation":
                return "supplier_evaluation"
            elif next_agent == "RFxDraft":
                return "rfx_draft"
            elif next_agent == "NegotiationSupport":
                return "negotiation"
            elif next_agent == "ContractSupport":
                return "contract_support"
            elif next_agent == "Implementation":
                return "implementation"
            elif next_agent == "CaseClarifier":
                return "case_clarifier"
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
            "rfx_draft": "rfx_draft",
            "negotiation": "negotiation",
            "contract_support": "contract_support",
            "implementation": "implementation",
            "case_clarifier": "case_clarifier",
            "wait_for_human": "wait_for_human",
            "end": END
        }
    )
    
    # CRITICAL ARCHITECTURE: All specialized agents MUST route back to Supervisor
    # This ensures Supervisor is always in control and can coordinate with humans
    # Flow: Supervisor → Agent → Supervisor → (Human/Next Agent/End)
    workflow.add_edge("strategy", "supervisor")  # Strategy agent reports back to Supervisor
    workflow.add_edge("supplier_evaluation", "supervisor")  # Supplier Scoring agent reports back to Supervisor
    workflow.add_edge("rfx_draft", "supervisor")  # RFx Draft agent reports back to Supervisor
    workflow.add_edge("negotiation", "supervisor")  # Negotiation Support agent reports back to Supervisor
    workflow.add_edge("contract_support", "supervisor")  # Contract Support agent reports back to Supervisor
    workflow.add_edge("implementation", "supervisor")  # Implementation agent reports back to Supervisor
    workflow.add_edge("case_clarifier", "supervisor")  # Case Clarifier reports back to Supervisor
    
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


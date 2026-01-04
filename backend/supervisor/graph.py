"""
Supervisor LangGraph workflow with governance enforcement.
"""
from typing import Literal, Optional, Dict, Any
from datetime import datetime
import json

from langgraph.graph import StateGraph, END

from backend.supervisor.state import SupervisorState, StateManager
from backend.supervisor.router import IntentRouter
from shared.constants import UserIntent, CaseStatus


class SupervisorGraph:
    """
    Central Supervisor graph that orchestrates the agentic workflow.
    
    CRITICAL GOVERNANCE RULES:
    1. Supervisor loads state before every action
    2. Intent is classified first
    3. Invalid transitions are blocked
    4. Retrievals are filtered by stage relevance
    5. Human approval required for stage changes
    6. No agent may update state directly
    """
    
    def __init__(self):
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph(SupervisorState)
        
        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("validate_action", self._validate_action_node)
        workflow.add_node("execute_agent", self._execute_agent_node)
        workflow.add_node("check_approval", self._check_approval_node)
        workflow.add_node("process_decision", self._process_decision_node)
        workflow.add_node("format_response", self._format_response_node)
        
        # Entry point
        workflow.set_entry_point("classify_intent")
        
        # Edges
        workflow.add_edge("classify_intent", "validate_action")
        
        workflow.add_conditional_edges(
            "validate_action",
            self._route_after_validation,
            {
                "execute": "execute_agent",
                "blocked": "format_response",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "execute_agent",
            self._route_after_execution,
            {
                "needs_approval": "check_approval",
                "done": "format_response"
            }
        )
        
        workflow.add_conditional_edges(
            "check_approval",
            self._route_after_approval_check,
            {
                "waiting": END,  # Pause workflow
                "approved": "process_decision",
                "rejected": "format_response"
            }
        )
        
        workflow.add_edge("process_decision", "format_response")
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def _classify_intent_node(self, state: SupervisorState) -> SupervisorState:
        """Classify user intent."""
        intent = IntentRouter.classify_intent(state["user_intent"])
        
        new_state = dict(state)
        new_state["intent_classification"] = intent.value
        
        # Log intent classification
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "intent_classification",
            "intent": intent.value,
            "user_message": state["user_intent"][:100],
            "agent_name": "Supervisor"
        }
        new_state["activity_log"] = state.get("activity_log", []) + [log_entry]
        
        return SupervisorState(**new_state)
    
    def _validate_action_node(self, state: SupervisorState) -> SupervisorState:
        """Validate if the requested action is allowed."""
        intent = UserIntent(state["intent_classification"])
        dtp_stage = state["dtp_stage"]
        
        # Check if intent is allowed at this stage
        is_valid, error_msg = StateManager.validate_intent_for_stage(dtp_stage, intent)
        
        new_state = dict(state)
        
        if not is_valid:
            new_state["blocked_reason"] = error_msg
            new_state["allowed_actions"] = []
        else:
            new_state["blocked_reason"] = None
            new_state["allowed_actions"] = IntentRouter.get_allowed_agents(intent, dtp_stage)
        
        return SupervisorState(**new_state)
    
    def _execute_agent_node(self, state: SupervisorState) -> SupervisorState:
        """Execute appropriate agent based on intent and stage."""
        # This is a placeholder - actual agent execution is done by services
        # The graph just orchestrates the flow
        
        intent = UserIntent(state["intent_classification"])
        allowed_agents = state.get("allowed_actions", [])
        
        new_state = dict(state)
        
        if not allowed_agents:
            new_state["latest_agent_output"] = {
                "message": "No agents available for this action at the current stage.",
                "stage": state["dtp_stage"]
            }
            new_state["latest_agent_name"] = "Supervisor"
            return SupervisorState(**new_state)
        
        # For now, mark that agent execution should happen
        # Actual execution is handled by ChatService
        new_state["latest_agent_name"] = allowed_agents[0] if allowed_agents else None
        
        return SupervisorState(**new_state)
    
    def _check_approval_node(self, state: SupervisorState) -> SupervisorState:
        """Check if human approval is needed."""
        intent = UserIntent(state["intent_classification"])
        agent_name = state.get("latest_agent_name")
        
        needs_approval = IntentRouter.requires_human_approval(intent, agent_name)
        
        new_state = dict(state)
        new_state["waiting_for_human"] = needs_approval
        
        if needs_approval:
            new_state["status"] = CaseStatus.WAITING_HUMAN.value
        
        return SupervisorState(**new_state)
    
    def _process_decision_node(self, state: SupervisorState) -> SupervisorState:
        """Process human decision (approve/reject)."""
        human_decision = state.get("human_decision")
        
        if not human_decision:
            return state
        
        new_state = dict(state)
        decision_type = human_decision.get("decision", "").lower()
        
        if decision_type == "approve":
            # Advance stage if applicable
            can_advance, error = StateManager.can_advance_stage(state, True)
            if can_advance:
                new_state, _ = StateManager.advance_stage(SupervisorState(**new_state))
            new_state["status"] = CaseStatus.IN_PROGRESS.value
        else:
            # Rejected
            new_state["status"] = CaseStatus.IN_PROGRESS.value
        
        new_state["waiting_for_human"] = False
        
        # Log decision
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "human_decision",
            "decision": decision_type,
            "reason": human_decision.get("reason"),
            "agent_name": "Human"
        }
        new_state["activity_log"] = state.get("activity_log", []) + [log_entry]
        
        return SupervisorState(**new_state)
    
    def _format_response_node(self, state: SupervisorState) -> SupervisorState:
        """Format response for user."""
        # Response formatting is handled by ChatService
        return state
    
    def _route_after_validation(
        self,
        state: SupervisorState
    ) -> Literal["execute", "blocked", "end"]:
        """Route after validation."""
        if state.get("blocked_reason"):
            return "blocked"
        
        if state.get("allowed_actions"):
            return "execute"
        
        return "end"
    
    def _route_after_execution(
        self,
        state: SupervisorState
    ) -> Literal["needs_approval", "done"]:
        """Route after agent execution."""
        intent = UserIntent(state["intent_classification"])
        agent_name = state.get("latest_agent_name")
        
        if IntentRouter.requires_human_approval(intent, agent_name):
            return "needs_approval"
        
        return "done"
    
    def _route_after_approval_check(
        self,
        state: SupervisorState
    ) -> Literal["waiting", "approved", "rejected"]:
        """Route after approval check."""
        if state.get("waiting_for_human"):
            human_decision = state.get("human_decision")
            if not human_decision:
                return "waiting"  # Still waiting
            
            if human_decision.get("decision", "").lower() == "approve":
                return "approved"
            else:
                return "rejected"
        
        return "approved"  # No approval needed
    
    def invoke(self, state: SupervisorState, config: Optional[Dict] = None) -> SupervisorState:
        """Invoke the workflow."""
        config = config or {"recursion_limit": 25}
        return self.graph.invoke(state, config)


# Singleton instance
_supervisor_graph = None


def get_supervisor_graph() -> SupervisorGraph:
    """Get or create supervisor graph singleton."""
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = SupervisorGraph()
    return _supervisor_graph






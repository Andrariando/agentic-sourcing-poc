"""
Chat/Copilot service with Supervisor governance.
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime

from backend.services.case_service import get_case_service
from backend.supervisor.state import SupervisorState, StateManager
from backend.supervisor.router import IntentRouter
from backend.supervisor.graph import get_supervisor_graph
from backend.agents.strategy import StrategyAgent
from backend.agents.supplier_eval import SupplierEvaluationAgent
from backend.agents.negotiation import NegotiationAgent
from backend.agents.signal import SignalAgent
from shared.constants import UserIntent, CaseStatus
from shared.schemas import ChatResponse


class ChatService:
    """
    Chat/Copilot service.
    
    CRITICAL: All chat interactions go through the Supervisor.
    The Supervisor:
    1. Loads case state
    2. Classifies intent
    3. Validates action
    4. Routes to appropriate agent
    5. Enforces human approval where required
    """
    
    def __init__(self):
        self.case_service = get_case_service()
        self.supervisor = get_supervisor_graph()
        
        # Agent instances
        self._agents = {
            "Strategy": StrategyAgent(tier=1),
            "SupplierEvaluation": SupplierEvaluationAgent(tier=1),
            "NegotiationSupport": NegotiationAgent(tier=1),
            "SignalInterpretation": SignalAgent(tier=1)
        }
    
    def process_message(
        self,
        case_id: str,
        user_message: str,
        use_tier_2: bool = False
    ) -> ChatResponse:
        """
        Process user message with Supervisor governance.
        
        Flow:
        1. Load case state
        2. Classify intent
        3. Validate action for stage
        4. If valid, execute appropriate agent
        5. Check if human approval needed
        6. Return response with context
        """
        # STEP 1: Load case state
        state = self.case_service.get_case_state(case_id)
        if not state:
            return ChatResponse(
                case_id=case_id,
                user_message=user_message,
                assistant_message="Case not found.",
                intent_classified="UNKNOWN",
                dtp_stage="",
                waiting_for_human=False,
                timestamp=datetime.now().isoformat()
            )
        
        # STEP 2: Update state with user message
        state["user_intent"] = user_message
        
        # STEP 3: Classify intent
        intent = IntentRouter.classify_intent(user_message)
        state["intent_classification"] = intent.value
        
        # STEP 4: Validate action for stage
        is_valid, blocked_reason = StateManager.validate_intent_for_stage(
            state["dtp_stage"],
            intent
        )
        
        if not is_valid:
            explanation = IntentRouter.format_gating_explanation(
                intent, state["dtp_stage"], blocked_reason
            )
            return ChatResponse(
                case_id=case_id,
                user_message=user_message,
                assistant_message=explanation,
                intent_classified=intent.value,
                dtp_stage=state["dtp_stage"],
                waiting_for_human=False,
                timestamp=datetime.now().isoformat()
            )
        
        # STEP 5: Get allowed agents and execute
        allowed_agents = IntentRouter.get_allowed_agents(intent, state["dtp_stage"])
        
        if not allowed_agents:
            return ChatResponse(
                case_id=case_id,
                user_message=user_message,
                assistant_message=f"No actions available at the current stage ({state['dtp_stage']}).",
                intent_classified=intent.value,
                dtp_stage=state["dtp_stage"],
                waiting_for_human=False,
                timestamp=datetime.now().isoformat()
            )
        
        # STEP 6: Execute primary agent
        agent_name = self._select_agent(user_message, allowed_agents, state["dtp_stage"])
        agent = self._agents.get(agent_name)
        
        agent_result = None
        if agent:
            case_context = {
                "case_id": case_id,
                "category_id": state["category_id"],
                "supplier_id": state.get("supplier_id"),
                "contract_id": state.get("contract_id"),
                "dtp_stage": state["dtp_stage"]
            }
            agent_result = agent.execute(case_context, user_message)
        
        # STEP 7: Update state with agent output
        if agent_result:
            state["latest_agent_output"] = agent_result.get("output")
            state["latest_agent_name"] = agent_result.get("agent_name")
            state["retrieval_context"] = agent_result.get("retrieval_context")
        
        # STEP 8: Check if human approval needed
        needs_approval = IntentRouter.requires_human_approval(intent, agent_name)
        
        if needs_approval:
            state["waiting_for_human"] = True
            state["status"] = CaseStatus.WAITING_HUMAN.value
        
        # STEP 9: Save state
        self.case_service.save_case_state(state)
        
        # STEP 10: Format response
        assistant_message = self._format_response(
            intent, agent_result, state, needs_approval
        )
        
        return ChatResponse(
            case_id=case_id,
            user_message=user_message,
            assistant_message=assistant_message,
            intent_classified=intent.value,
            agents_called=[agent_name] if agent_name else [],
            tokens_used=agent_result.get("tokens_used", 0) if agent_result else 0,
            dtp_stage=state["dtp_stage"],
            waiting_for_human=needs_approval,
            workflow_summary={
                "agent": agent_name,
                "retrieval_context": agent_result.get("retrieval_context") if agent_result else None
            },
            retrieval_context=agent_result.get("retrieval_context") if agent_result else None,
            timestamp=datetime.now().isoformat()
        )
    
    def process_decision(
        self,
        case_id: str,
        decision: str,
        reason: Optional[str] = None,
        edited_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process human decision (approve/reject)."""
        state = self.case_service.get_case_state(case_id)
        if not state:
            return {"success": False, "message": "Case not found"}
        
        if not state.get("waiting_for_human"):
            return {"success": False, "message": "Case not waiting for decision"}
        
        # Update state with decision
        state["human_decision"] = {
            "decision": decision,
            "reason": reason,
            "edited_fields": edited_fields or {},
            "timestamp": datetime.now().isoformat()
        }
        
        if decision.lower() == "approve":
            # Advance stage if applicable
            can_advance, _ = StateManager.can_advance_stage(state, True)
            if can_advance:
                state, _ = StateManager.advance_stage(state)
            state["status"] = CaseStatus.IN_PROGRESS.value
        else:
            state["status"] = CaseStatus.IN_PROGRESS.value
        
        state["waiting_for_human"] = False
        
        # Save state
        self.case_service.save_case_state(state)
        
        return {
            "success": True,
            "decision": decision,
            "new_dtp_stage": state["dtp_stage"],
            "message": f"Decision '{decision}' processed successfully"
        }
    
    def _select_agent(
        self,
        user_message: str,
        allowed_agents: list,
        dtp_stage: str
    ) -> Optional[str]:
        """Select best agent for the request."""
        message_lower = user_message.lower()
        
        # Keyword-based selection
        if "strategy" in message_lower or "recommend" in message_lower:
            if "Strategy" in allowed_agents:
                return "Strategy"
        
        if "supplier" in message_lower or "evaluate" in message_lower:
            if "SupplierEvaluation" in allowed_agents:
                return "SupplierEvaluation"
        
        if "negotiat" in message_lower:
            if "NegotiationSupport" in allowed_agents:
                return "NegotiationSupport"
        
        if "signal" in message_lower or "alert" in message_lower:
            if "SignalInterpretation" in allowed_agents:
                return "SignalInterpretation"
        
        # Default to first available
        return allowed_agents[0] if allowed_agents else None
    
    def _format_response(
        self,
        intent: UserIntent,
        agent_result: Optional[Dict],
        state: SupervisorState,
        needs_approval: bool
    ) -> str:
        """Format response for user."""
        if not agent_result:
            return "I couldn't complete that request. Please try again."
        
        output = agent_result.get("output", {})
        
        # Build response based on agent type
        agent_name = agent_result.get("agent_name", "")
        
        if agent_name == "Strategy":
            strategy = output.get("recommended_strategy", "Monitor")
            rationale = output.get("rationale", [])
            
            response = f"**Strategy Recommendation: {strategy}**\n\n"
            if rationale:
                response += "**Rationale:**\n"
                for r in rationale[:3]:
                    response += f"• {r}\n"
            
            if output.get("grounded_in"):
                response += f"\n*Grounded in {len(output['grounded_in'])} documents*"
        
        elif agent_name == "SupplierEvaluation":
            suppliers = output.get("shortlisted_suppliers", [])
            response = f"**Supplier Evaluation**\n\n"
            if suppliers:
                response += f"Shortlisted {len(suppliers)} suppliers:\n"
                for s in suppliers[:3]:
                    response += f"• {s.get('name', s.get('supplier_id', 'Unknown'))}: {s.get('score', 'N/A')}/10\n"
            else:
                response += "No suppliers found matching criteria.\n"
            response += f"\n{output.get('recommendation', '')}"
        
        elif agent_name == "NegotiationSupport":
            objectives = output.get("negotiation_objectives", [])
            response = f"**Negotiation Plan**\n\n"
            if objectives:
                response += "**Objectives:**\n"
                for obj in objectives[:3]:
                    response += f"• {obj}\n"
            
            leverage = output.get("leverage_points", [])
            if leverage:
                response += "\n**Leverage Points:**\n"
                for lp in leverage[:2]:
                    response += f"• {lp}\n"
        
        else:
            # Generic response
            response = json.dumps(output, indent=2)
        
        # Add approval notice if needed
        if needs_approval:
            response += "\n\n---\n⚠️ **Awaiting your approval** to proceed. Please review and approve or reject."
        
        return response


# Singleton
_chat_service = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


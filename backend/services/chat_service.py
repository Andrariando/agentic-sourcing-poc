"""
Chat/Copilot service with Supervisor governance.

CONVERSATIONAL DESIGN:
- STATUS intent: Summarize current state (no agent call)
- EXPLAIN intent: Explain existing recommendation (no new analysis)
- EXPLORE intent: Explore alternatives (may call agent)
- DECIDE intent: Process approval/rejection OR request new analysis

ARTIFACT PACK FLOW:
- Agents now return ArtifactPacks instead of simple JSON
- ArtifactPacks are persisted via CaseService
- UI receives artifacts, next_actions, and risks

CONVERSATION MEMORY:
- Optional conversation history with cost-aware context management
- Enabled via ENABLE_CONVERSATION_MEMORY environment variable
- Backward compatible (graceful degradation if disabled)
"""
import json
import re
import os
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Import feature flags
try:
    from backend.services.feature_flags import ENABLE_ROUTING_LOGS, ENABLE_CLARIFIER_FALLBACK
except ImportError:
    ENABLE_ROUTING_LOGS = True
    ENABLE_CLARIFIER_FALLBACK = True

from backend.services.case_service import get_case_service
from backend.supervisor.state import SupervisorState, StateManager
from backend.supervisor.router import IntentRouter
from backend.supervisor.router import IntentRouter
from shared.constants import DTP_STAGE_NAMES, AgentName, ArtifactType
from utils.schemas import (
    StrategyRecommendation, SupplierShortlist, NegotiationPlan, 
    RFxDraft, ContractExtraction, ImplementationPlan, ClarificationRequest,
    SignalAssessment, AgentDialogue
)
from shared.schemas import (
    ChatResponse, ArtifactPack, NextAction, CaseStatus, Artifact, RiskItem,
    ExecutionMetadata, TaskExecutionDetail
)
from shared.constants import UserIntent, UserGoal
from shared.decision_definitions import DTP_DECISIONS

# Import new official agents
from backend.agents import (
    SupervisorAgent,
    SourcingSignalAgent,
    SupplierScoringAgent,
    RfxDraftAgent,
    NegotiationSupportAgent,
    ContractSupportAgent,
    ImplementationAgent,
)
# Legacy agents for backward compatibility
from backend.agents.strategy import StrategyAgent
from backend.agents.supplier_eval import SupplierEvaluationAgent
from backend.agents.negotiation import NegotiationAgent
from backend.agents.signal import SignalAgent

# ============================================================================
# FIX 1: Centralized Agent-to-ArtifactType Mapping
# This provides robust artifact type detection regardless of agent naming conventions
# ============================================================================
AGENT_TO_ARTIFACT_TYPE = {
    # Strategy variants
    "Strategy": ArtifactType.STRATEGY_RECOMMENDATION,
    "STRATEGY": ArtifactType.STRATEGY_RECOMMENDATION,
    "StrategyAgent": ArtifactType.STRATEGY_RECOMMENDATION,
    
    # Signal variants
    "SOURCING_SIGNAL": ArtifactType.SIGNAL_REPORT,
    "SourcingSignal": ArtifactType.SIGNAL_REPORT,
    "SignalInterpretation": ArtifactType.SIGNAL_REPORT,
    "Signal": ArtifactType.SIGNAL_REPORT,
    
    # Supplier Evaluation variants
    "SupplierEvaluation": ArtifactType.SUPPLIER_SHORTLIST,
    "SUPPLIER_SCORING": ArtifactType.SUPPLIER_SHORTLIST,
    "SupplierScoring": ArtifactType.SUPPLIER_SHORTLIST,
    
    # RFx Draft variants
    "RFxDraft": ArtifactType.RFX_DRAFT_PACK,
    "RFX_DRAFT": ArtifactType.RFX_DRAFT_PACK,
    "RfxDraft": ArtifactType.RFX_DRAFT_PACK,
    
    # Negotiation variants
    "NegotiationSupport": ArtifactType.NEGOTIATION_PLAN,
    "NEGOTIATION_SUPPORT": ArtifactType.NEGOTIATION_PLAN,
    "Negotiation": ArtifactType.NEGOTIATION_PLAN,
    
    # Contract Support variants
    "ContractSupport": ArtifactType.KEY_TERMS_EXTRACT,
    "CONTRACT_SUPPORT": ArtifactType.KEY_TERMS_EXTRACT,
    "Contract": ArtifactType.KEY_TERMS_EXTRACT,
    
    # Implementation variants
    "Implementation": ArtifactType.IMPLEMENTATION_CHECKLIST,
    "IMPLEMENTATION": ArtifactType.IMPLEMENTATION_CHECKLIST,
    "ImplementationAgent": ArtifactType.IMPLEMENTATION_CHECKLIST,
}

# FIX 3: String to AgentName enum mapping for ArtifactBuilder integration
STRING_TO_AGENT_NAME = {
    "Strategy": AgentName.SOURCING_SIGNAL,  # Strategy maps to sourcing signal's domain
    "STRATEGY": AgentName.SOURCING_SIGNAL,
    "SOURCING_SIGNAL": AgentName.SOURCING_SIGNAL,
    "SourcingSignal": AgentName.SOURCING_SIGNAL,
    "Signal": AgentName.SOURCING_SIGNAL,
    "SupplierEvaluation": AgentName.SUPPLIER_SCORING,
    "SUPPLIER_SCORING": AgentName.SUPPLIER_SCORING,
    "SupplierScoring": AgentName.SUPPLIER_SCORING,
    "RFxDraft": AgentName.RFX_DRAFT,
    "RFX_DRAFT": AgentName.RFX_DRAFT,
    "RfxDraft": AgentName.RFX_DRAFT,
    "NegotiationSupport": AgentName.NEGOTIATION_SUPPORT,
    "NEGOTIATION_SUPPORT": AgentName.NEGOTIATION_SUPPORT,
    "Negotiation": AgentName.NEGOTIATION_SUPPORT,
    "ContractSupport": AgentName.CONTRACT_SUPPORT,
    "CONTRACT_SUPPORT": AgentName.CONTRACT_SUPPORT,
    "Contract": AgentName.CONTRACT_SUPPORT,
    "Implementation": AgentName.IMPLEMENTATION,
    "IMPLEMENTATION": AgentName.IMPLEMENTATION,
    "Supervisor": AgentName.SUPERVISOR,
}

def get_agent_name_enum(agent_str: str) -> Optional[AgentName]:
    """Convert string agent name to AgentName enum, or None if not found."""
    return STRING_TO_AGENT_NAME.get(agent_str)


def check_stage_readiness(case, state: dict) -> dict:
    """
    Check if case has prerequisites for current DTP stage.
    
    Returns:
        dict with keys:
            - ready: bool - True if all prerequisites met
            - missing: List[str] - Human-readable list of missing items
            - stage: str - Current DTP stage
            - description: str - Stage description
    """
    from shared.stage_prereqs import STAGE_PREREQS, get_stage_description
    
    stage = state.get("dtp_stage", "DTP-01")
    prereqs = STAGE_PREREQS.get(stage, {})
    missing = []
    
    # 1. Check required case fields
    for field in prereqs.get("case_fields", []):
        if not getattr(case, field, None):
            missing.append(f"Case field '{field}' is required")
    
    # 2. Check required human decisions (with .answer validation)
    human_decisions = state.get("human_decision") or {}
    for decision_key in prereqs.get("human_decisions", []):
        parts = decision_key.split(".")
        if len(parts) != 2:
            continue
        stage_part, question_id = parts
        stage_decisions = human_decisions.get(stage_part) or {}
        decision_obj = stage_decisions.get(question_id)
        
        # Must exist, not None, and have non-empty answer
        if not decision_obj:
            missing.append(f"Decision '{question_id}' from {stage_part} not answered")
        elif not decision_obj.get("answer"):
            missing.append(f"Decision '{question_id}' from {stage_part} has empty answer")
    
    # 3. Check required context fields (AND logic)
    case_context = state.get("case_context") or {}
    for field in prereqs.get("context_fields", []):
        value = case_context.get(field)
        if not value:
            missing.append(f"Context '{field}' is required for this stage")
    
    # 4. Check context fields with OR logic (e.g., DTP-04 finalists OR selected)
    or_fields = prereqs.get("context_fields_or", [])
    if or_fields:
        has_any = any(case_context.get(f) for f in or_fields)
        if not has_any:
            or_list = " or ".join([f"'{f}'" for f in or_fields])
            missing.append(f"Need at least one of: {or_list}")
    
    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "stage": stage,
        "description": get_stage_description(stage)
    }


class ChatService:
    """
    Chat/Copilot service with conversational intelligence.
    
    Key behaviors:
    1. Don't run agents for every message
    2. Handle STATUS/EXPLAIN without new analysis
    3. Detect approval/rejection in natural language
    4. Provide varied, contextual responses
    5. Return ArtifactPacks from agent executions
    6. NEW: Support conversation memory with cost-aware context management
    """
    
    def __init__(self):
        self.case_service = get_case_service()
        self.supervisor = SupervisorAgent(tier=1)
        
        # Feature flag for conversation memory
        # Enable conversation memory by default for better ChatGPT-like experience
        self.enable_conversation_memory = os.getenv(
            "ENABLE_CONVERSATION_MEMORY", "true"
        ).lower() == "true"
        
        # Initialize conversation context manager if enabled
        if self.enable_conversation_memory:
            try:
                from backend.services.conversation_context import ConversationContextManager
                self.conversation_manager = ConversationContextManager(self.case_service)
                logger.info("Conversation memory enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize conversation manager: {e}")
                self.conversation_manager = None
                self.enable_conversation_memory = False
        else:
            self.conversation_manager = None
        
        # New official agent instances
        self._official_agents = {
            AgentName.SOURCING_SIGNAL.value: SourcingSignalAgent(tier=1),
            AgentName.SUPPLIER_SCORING.value: SupplierScoringAgent(tier=1),
            AgentName.RFX_DRAFT.value: RfxDraftAgent(tier=1),
            AgentName.NEGOTIATION_SUPPORT.value: NegotiationSupportAgent(tier=1),
            AgentName.CONTRACT_SUPPORT.value: ContractSupportAgent(tier=1),
            AgentName.IMPLEMENTATION.value: ImplementationAgent(tier=1),
        }
        
        # Legacy agent instances (for backward compatibility)
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
        Process user message using LLM-first conversational approach.
        
        This is the GPT-like experience where:
        1. LLM analyzes what user wants
        2. Decides if agent is needed or can answer directly
        3. Generates natural, non-templated responses
        4. Asks for more data if needed
        5. Preserves conversation memory
        """
        from backend.services.llm_responder import get_llm_responder
        
        # Generate trace_id for this request
        trace_id = str(uuid.uuid4())
        
        # Log incoming message if routing logs enabled
        if ENABLE_ROUTING_LOGS:
            logger.info(f"[{trace_id}] CHAT_INPUT case={case_id} message={user_message[:100]}...")
        
        # 1. Load case state
        state = self.case_service.get_case_state(case_id)
        if not state:
            logger.warning(f"[{trace_id}] Case not found: {case_id}")
            return self._create_response(
                case_id, user_message, "Case not found.", "UNKNOWN", "", trace_id=trace_id
            )
        
        # 2. Get conversation history for memory
        conversation_history = []
        if self.conversation_manager and self.enable_conversation_memory:
            try:
                conversation_history = self.conversation_manager.get_relevant_context(
                    case_id=case_id,
                    current_message=user_message,
                    max_tokens=1500
                )
            except Exception as e:
                logger.warning(f"Failed to retrieve conversation context: {e}")
                conversation_history = []
        
        # 3. Save user message to memory
        if self.conversation_manager and self.enable_conversation_memory:
            try:
                self.conversation_manager.save_message(
                    case_id=case_id,
                    role="user",
                    content=user_message,
                    metadata={"trace_id": trace_id}
                )
            except Exception as e:
                logger.warning(f"[{trace_id}] Failed to save user message: {e}")
        
        # 4. Build case context for LLM
        case_context = {
            "case_id": case_id,
            "case_name": state.get("name", "Unnamed Case"),
            "summary": state.get("summary_text", ""),
            "key_findings": state.get("key_findings", []),
            "dtp_stage": state.get("dtp_stage", "DTP-01"),
            "category_id": state.get("category_id", "Unknown"),
            "status": state.get("status", "In Progress"),
            "latest_agent_output": state.get("latest_agent_output"),
            "latest_agent_name": state.get("latest_agent_name"),
            "waiting_for_human": state.get("waiting_for_human", False)
        }
        
        # 5. Use LLM to analyze intent
        responder = get_llm_responder()
        intent = responder.analyze_intent(user_message, case_context, conversation_history)
        
        logger.info(f"[{trace_id}] LLM Intent Analysis: {intent}")
        
        # 6. Execute based on intent
        assistant_message = ""
        agents_called = []
        action_taken = None

        # --- NEW: PROACTIVE DECISION LOGIC (Critique 3 & 7) ---
        # If waiting for human, hijack the flow to drive the decision process
        # BUT: Allow task requests (EXPLORE/DO intents) to bypass and execute agents
        intent_summary = intent.get("intent_summary", "").upper()
        is_task_request = intent_summary in ["EXPLORE", "DO", "ANALYZE"] or intent.get("requires_agent_action", False)
        
        # Check for keywords that indicate user wants to DO something, not answer a question
        task_keywords = ["prepare", "generate", "create", "draft", "analyze", "help me with", "what should", "give me", "show me"]
        message_looks_like_task = any(kw in user_message.lower() for kw in task_keywords)
        
        if state.get("waiting_for_human") and not is_task_request and not message_looks_like_task:
             pass # Already waiting
        elif intent.get("is_progression"):
             # User wants to proceed -> Force decision mode
             state["waiting_for_human"] = True
             state["status"] = "Waiting for Human Decision"
             self.case_service.save_case_state(state) # CRITICAL: Persist waiting state immediately
             logger.info(f"[{trace_id}] Proactive progression detected. Setting waiting_for_human=True and status='Waiting for Human Decision'")

        if state.get("waiting_for_human") and not is_task_request and not message_looks_like_task:
             current_stage = state.get("dtp_stage", "DTP-01")
             stage_def = DTP_DECISIONS.get(current_stage)
             
             if stage_def:
                # 1. Check if user answered a pending question
                # We need to identify WHICH question was pending. 
                # Ideally, we look at what's answered vs what's required.
                human_decisions = state.get("human_decision") or {}
                current_answers = human_decisions.get(current_stage) or {}
                
                # Find the first unanswered required question (in order)
                pending_question = None
                for q in stage_def.get("questions", []):
                    # Check dependency
                    if "dependency" in q:
                         dep_key, dep_val = list(q["dependency"].items())[0]
                         parent_ans_obj = current_answers.get(dep_key)
                         if not parent_ans_obj or parent_ans_obj.get("answer") != dep_val:
                             continue # Skip if dependency not met

                    if q["id"] not in current_answers:
                        pending_question = q
                        break
                
                # If we found a pending question AND the user's message looks like an answer
                if pending_question:
                    # Parse Answer
                    parsed_answer = None
                    
                    if pending_question["type"] == "choice":
                        # Strict Scaffolding: Expect "1" or "2" or exact text match
                        # Build mapping
                        options = pending_question["options"]
                        valid_map = {}
                        for idx, opt in enumerate(options, 1):
                            valid_map[str(idx)] = opt["value"] # "1" -> "Yes"
                            valid_map[opt["value"].lower()] = opt["value"] # "yes" -> "Yes"
                            valid_map[opt["label"].lower()] = opt["value"] # "yes, proceed..." -> "Yes"
                        
                        # Add natural language synonyms for common answers
                        # Map approval-like words to "Yes" if it exists
                        if any(opt["value"] == "Yes" for opt in options):
                            for synonym in ["approve", "proceed", "confirm", "confirmed", "ok", "okay", "sure"]:
                                valid_map[synonym] = "Yes"
                        # Map rejection-like words to "No" if it exists  
                        if any(opt["value"] == "No" for opt in options):
                            for synonym in ["reject", "decline", "cancel", "no thanks", "not now"]:
                                valid_map[synonym] = "No"
                        
                        clean_input = user_message.strip().lower()
                        # Remove trailing punctuation
                        clean_input = clean_input.rstrip(".,!")
                        
                        if clean_input in valid_map:
                            parsed_answer = valid_map[clean_input]
                    else:
                        # Free text (fallback for DTP-04 supplier name etc)
                        parsed_answer = user_message.strip()
                    
                    if parsed_answer:
                        # VALID ANSWER: Store it rich
                        if "human_decision" not in state or not isinstance(state["human_decision"], dict):
                            state["human_decision"] = {}
                        if current_stage not in state["human_decision"]:
                            state["human_decision"][current_stage] = {}
                            
                        state["human_decision"][current_stage][pending_question["id"]] = {
                            "answer": parsed_answer,
                            "decided_by_role": "User", # hardcoded for now
                            "timestamp": datetime.now().isoformat(),
                            "status": "final",
                            "confidence": "high"
                        }
                        
                        # Add activity log
                        if "activity_log" not in state: state["activity_log"] = []
                        state["activity_log"].append({
                            "timestamp": datetime.now().isoformat(),
                            "case_id": case_id,
                            "agent_name": "User",
                            "task_name": "Proactive Answer",
                            "output_summary": f"User answered {pending_question['id']} = {parsed_answer}",
                            "trigger_source": "Chat"
                        })
                        
                        self.case_service.save_case_state(state)
                        
                        # SYNC SUPPLIER_ID: If user answered award_supplier_id, update case.supplier_id
                        if pending_question["id"] == "award_supplier_id":
                            try:
                                self.case_service.update_case(case_id, {"supplier_id": parsed_answer})
                                logger.info(f"[SYNC] Updated supplier_id to {parsed_answer} for case {case_id}")
                            except Exception as e:
                                logger.warning(f"Failed to sync supplier_id: {e}")
                        
                        # COMPLETE CASE: If user confirmed contract_signed at DTP-06, mark case complete
                        if pending_question["id"] == "contract_signed" and current_stage == "DTP-06" and parsed_answer == "Yes":
                            try:
                                self.case_service.update_case(case_id, {"status": "Completed"})
                                state["status"] = "Completed"
                                logger.info(f"[COMPLETE] Case {case_id} marked as Completed (contract signed)")
                            except Exception as e:
                                logger.warning(f"Failed to mark case complete: {e}")
                        
                        # Re-evaluate to get the *NEXT* question immediately
                        # Refresh state copy
                        current_answers = state["human_decision"][current_stage]
                        
                        next_question = None
                        for q in stage_def.get("questions", []):
                             if "dependency" in q:
                                 dep_key, dep_val = list(q["dependency"].items())[0]
                                 parent_ans_obj = current_answers.get(dep_key)
                                 if not parent_ans_obj or parent_ans_obj.get("answer") != dep_val:
                                     continue 
                             if q["id"] not in current_answers:
                                 next_question = q
                                 break
                        
                        if next_question:
                             # Ask the next question
                             response = f"**Saved.**\n\nNext: {next_question['text']}\n"
                             if next_question["type"] == "choice":
                                 for i, opt in enumerate(next_question['options'], 1):
                                     response += f"{i}. {opt['label']}\n"
                                 response += "\n_(Please reply with the number)_"
                             
                             return self._create_response(case_id, user_message, response, "DECIDE", state.get("dtp_stage", "DTP-01"), waiting=True)
                        else:
                             # All done! Ask for confirmation
                             response = "**All questions answered.**\n\nSummary of your decisions:\n"
                             for q in stage_def["questions"]:
                                 # (Simplified summary generation)
                                 ans_obj = current_answers.get(q["id"])
                                 if ans_obj:
                                    response += f"- {q['text']}: **{ans_obj['answer']}**\n"
                             
                             response += "\n**Do you want to confirm and proceed to the next stage?** (Yes/No)"
                             return self._create_response(case_id, user_message, response, "DECIDE", state.get("dtp_stage"), waiting=True)

                    else:
                        # INVALID ANSWER: Scaffolding error
                        if pending_question["type"] == "choice":
                            options_text = ", ".join([f"'{opt['value']}'" for opt in pending_question["options"]])
                            response = f"I didn't catch that. Please answer **{pending_question['text']}** by choosing one of the options:\n\n"
                            for i, opt in enumerate(pending_question['options'], 1):
                                response += f"{i}. {opt['label']}\n"
                            return self._create_response(case_id, user_message, response, "DECIDE", state.get("dtp_stage"), waiting=True)

                # 2. If no pending question found (or we just finished), handle "Confirm"
                # If we are here, it means all required questions are likely answered (or none found)
                # Check for "Confirm" / "Yes" to final approval
                if any(kw in user_message.lower() for kw in ["yes", "confirm", "proceed", "approve"]):
                     # Call process_decision
                     result = self.process_decision(case_id, "Approve")
                     if result["success"]:
                        new_stage = result.get('new_dtp_stage') or state.get("dtp_stage", "DTP-01")
                        return self._create_response(case_id, user_message, f"Confirmed! moving to {new_stage}", "DECIDE", new_stage, waiting=False)
                     else:
                        return self._create_response(case_id, user_message, result["message"], "DECIDE", state.get("dtp_stage", "DTP-01"), waiting=True)

                # 3. Fallback: If just entering this state or lost context, ask the first pending question
                # (Same logic as above for finding pending_question)
                pending_question = None
                human_decisions_2 = state.get("human_decision") or {}
                current_answers = human_decisions_2.get(current_stage) or {}
                for q in stage_def.get("questions", []):
                    if "dependency" in q:
                         dep_key, dep_val = list(q["dependency"].items())[0]
                         parent_ans_obj = current_answers.get(dep_key)
                         if not parent_ans_obj or parent_ans_obj.get("answer") != dep_val:
                             continue
                    if q["id"] not in current_answers:
                        pending_question = q
                        break
                
                if pending_question:
                     response = f"**Decision Required: {stage_def.get('title')}**\n\n{pending_question['text']}\n"
                     if pending_question["type"] == "choice":
                         for i, opt in enumerate(pending_question['options'], 1):
                             response += f"{i}. {opt['label']}\n"
                         response += "\n_(Please reply with the number)_"
                     
                     # SAVE STATE: Ensure waiting_for_human is persisted
                     self.case_service.save_case_state(state)
                     
                     return self._create_response(case_id, user_message, response, "DECIDE", state.get("dtp_stage", "DTP-01"), waiting=True)


        # --- END NEW PROACTIVE LOGIC ---

        
        if intent.get("is_approval") and state.get("waiting_for_human"):
            # ... (approval logic remains same) ...
            print(f"[DEBUG LLM-FIRST] Detected approval via LLM")
            result = self.process_decision(case_id, "Approve")
            print(f"[DEBUG LLM-FIRST] process_decision result: {result}")
            assistant_message = responder.generate_approval_response(result, case_context)
            action_taken = f"Approved. Result: {result}"
            
        elif intent.get("is_rejection") and state.get("waiting_for_human"):
            # ... (rejection logic remains same) ...
            result = self.process_decision(case_id, "Reject", reason=user_message)
            assistant_message = responder.generate_rejection_response(case_context, user_message)
            action_taken = "Rejected"
            
        elif intent.get("needs_data"):
            # ... (data request logic remains same) ...
            assistant_message = responder.generate_data_request(
                intent.get("missing_info", "more details"),
                case_context
            )
            action_taken = "Requested more data"
            
        elif intent.get("needs_agent"):
            # PREFLIGHT CHECK: Validate case is ready for current stage
            case = self.case_service.get_case(case_id)  # Get case object for readiness check
            readiness = check_stage_readiness(case, state)
            if not readiness["ready"]:
                missing_items = "\n".join([f"• {m}" for m in readiness["missing"]])
                block_message = (
                    f"⚠️ **Cannot proceed with {readiness['description']}**\n\n"
                    f"The following prerequisites are missing:\n{missing_items}\n\n"
                    f"Please complete these requirements before continuing with this stage."
                )
                logger.warning(f"[PREFLIGHT] Case {case_id} blocked at {readiness['stage']}: {readiness['missing']}")
                return self._create_response(
                    case_id, user_message, block_message, 
                    "BLOCKED", readiness["stage"], waiting=False
                )
            
            # ... (agent logic remains same) ...
            print(f"[DEBUG LLM-FIRST] Running agent workflow, hint: {intent.get('agent_hint')}")
            
            # Explicitly clear waiting state for NEW work
            state["waiting_for_human"] = False
            # state["human_decision"] = None # FIX: Do NOT clear historical decisions
            state["latest_agent_output"] = None
            state["latest_agent_name"] = None
            
            result = self.process_message_langgraph(
                case_id=case_id,
                user_message=user_message,
                use_tier_2=use_tier_2,
                case_state=state
            )
            assistant_message = result.assistant_message
            agents_called = result.agents_called or []
            
        else:
            # Direct LLM response (Question/Chat)
            assistant_message = responder.generate_response(
                user_message=user_message,
                case_context=case_context,
                agent_output=state.get("latest_agent_output"),
                conversation_history=conversation_history
            )
            
            # CRITICAL ENHANCEMENT: If waiting for human compliance/approval, 
            # and user just asked a question, gently remind them.
            if state.get("waiting_for_human"):
                assistant_message += "\n\n(By the way, I'm still waiting for your decision on the recommendation above. Let me know if you'd like to proceed!)"
            
            action_taken = "Direct LLM response"
            
            # LOGGING FIX: Add explicit log entry for Direct LLM response so user sees it in UI
            if "activity_log" not in state or state["activity_log"] is None:
                state["activity_log"] = []
            
            # Create a simplified log entry for the Copilot's direct action
            direct_log = {
                "log_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "case_id": case_id,
                "dtp_stage": state.get("dtp_stage", "Unknown"),
                "agent_name": "Copilot",
                "task_name": "Direct Response",
                "model_used": "gpt-4o-mini",
                "output_summary": assistant_message,
                "reasoning_log": {
                    "thinking": "User asked a question that could be answered directly from context.",
                    "intent_detected": intent.get("intent_summary", "Question"),
                    "action": "Answered directly without specialist agent"
                }
            }
            state["activity_log"].append(direct_log)
            
            # CRITICAL FIX: Save state to persist activity log to database
            
            # UNIFIED AUDIT TRAIL: Also save as ArtifactPack to ensure it appears in detailed Audit Trail
            try:
                copilot_artifact = Artifact(
                    artifact_id=str(uuid.uuid4()),
                    type=ArtifactType.AUDIT_LOG_EVENT.value,
                    title="Copilot Response",
                    content={"message": assistant_message},
                    content_text=assistant_message,
                    created_at=datetime.now().isoformat(),
                    created_by_agent="Copilot"
                )
                
                copilot_pack = ArtifactPack(
                    pack_id=str(uuid.uuid4()),
                    artifacts=[copilot_artifact],
                    agent_name="Copilot",
                    created_at=datetime.now().isoformat(),
                    execution_metadata=ExecutionMetadata(
                        agent_name="Copilot",
                        dtp_stage=state.get("dtp_stage", "Unknown"),
                        execution_timestamp=datetime.now().isoformat(),
                        total_tokens_used=len(assistant_message.split()) // 3, # Rough heuristic (1.3 tokens per word approx)
                        estimated_cost_usd=(len(assistant_message.split()) // 3 / 1000) * 0.0006, # Approx cost for gpt-4o-mini output
                        task_details=[
                            TaskExecutionDetail(
                                task_name="Direct Response",
                                execution_order=1,
                                status="completed",
                                started_at=datetime.now().isoformat(),
                                completed_at=datetime.now().isoformat(),
                                output_summary=assistant_message,
                                tokens_used=len(assistant_message.split()) // 3,
                                grounding_sources=[]
                            )
                        ],
                        user_message=user_message or "",
                        intent_classified=intent.get("intent_summary", "Question"),
                        model_used="gpt-4o-mini"
                    )
                )
                self.case_service.save_artifact_pack(case_id, copilot_pack)
            except Exception as e:
                logger.error(f"Failed to save Copilot artifact pack: {e}")

            self.case_service.save_case_state(state)
        
        # 7. Save assistant response to memory
        if self.conversation_manager and self.enable_conversation_memory:
            try:
                self.conversation_manager.save_message(
                    case_id=case_id,
                    role="assistant",
                    content=assistant_message,
                    metadata={
                        "trace_id": trace_id,
                        "intent": intent.get("intent_summary"),
                        "action_taken": action_taken
                    }
                )
            except Exception as e:
                logger.warning(f"[{trace_id}] Failed to save assistant message: {e}")
        
        # 8. Return response
        return self._create_response(
            case_id=case_id,
            user_message=user_message,
            assistant_message=assistant_message,
            intent=intent.get("intent_summary", "UNKNOWN"),
            dtp_stage=state.get("dtp_stage", "DTP-01"),
            waiting=state.get("waiting_for_human", False),
            trace_id=trace_id,
            agents_called=agents_called
        )
        return response
    
    def _create_response(
        self,
        case_id: str,
        user_message: str,
        assistant_message: str,
        intent: str,
        dtp_stage: str,
        waiting: bool = False,
        trace_id: str = None,
        agents_called: List[str] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Create a ChatResponse object from the processing results.
        """
        return ChatResponse(
            case_id=case_id,
            user_message=user_message,
            assistant_message=assistant_message,
            intent_classified=intent,
            dtp_stage=dtp_stage,
            agents_called=agents_called or [],
            tokens_used=0,  # TODO: Track actual tokens
            waiting_for_human=waiting,
            timestamp=datetime.now().isoformat(),
            trace_id=trace_id
        )
    
    def _check_for_approval(
        self,
        message: str,
        case_id: str,
        state: SupervisorState
    ) -> Optional[ChatResponse]:
        """Check if the message contains approval or rejection."""
        message_lower = message.lower().strip()
        
        # Approval patterns
        approval_patterns = [
            r'\byes\b', r'\bapprove\b', r'\bproceed\b', r'\bgo ahead\b',
            r'\bok\b', r'\bokay\b', r'\bconfirm\b', r'\baccept\b',
            r'\bagree\b', r'\blet\'?s do it\b', r'\bsounds good\b'
        ]
        
        # Rejection patterns
        rejection_patterns = [
            r'\bno\b', r'\breject\b', r'\bcancel\b', r'\bstop\b',
            r'\bdon\'?t\b', r'\bdecline\b', r'\brefuse\b',
            r'\bwait\b', r'\bhold\b', r'\bnot yet\b'
        ]
        
        is_approval = any(re.search(p, message_lower) for p in approval_patterns)
        is_rejection = any(re.search(p, message_lower) for p in rejection_patterns)
        
        if is_approval and not is_rejection:
            # Process approval
            print(f"[DEBUG APPROVE] Detected approval for case {case_id}")
            result = self.process_decision(case_id, "Approve")
            print(f"[DEBUG APPROVE] process_decision result: {result}")
            if result["success"]:
                new_stage = result.get("new_dtp_stage", state["dtp_stage"])
                print(f"[DEBUG APPROVE] New DTP stage: {new_stage}")
                stage_name = DTP_STAGE_NAMES.get(new_stage, new_stage)
                
                response = f"Decision approved. The case has advanced to **{new_stage} - {stage_name}**.\n\n"
                response += "You can now proceed with the next phase of the sourcing process. "
                response += "Ask me about the next steps or what actions are available."
                
                return self._create_response(
                    case_id, message, response, "DECIDE", new_stage,
                    waiting=False
                )
        
        elif is_rejection:
            # Process rejection
            result = self.process_decision(case_id, "Reject")
            if result["success"]:
                response = "Decision noted. The recommendation has been rejected.\n\n"
                response += "The case remains at the current stage. You can:\n"
                response += "- Ask me to explore alternative strategies\n"
                response += "- Request a revised analysis\n"
                response += "- Provide specific feedback on what to change"
                
                return self._create_response(
                    case_id, message, response, "DECIDE", state["dtp_stage"],
                    waiting=False
                )
        
        return None  # Not an approval/rejection
    
    def _handle_status_intent(
        self,
        case_id: str,
        message: str,
        state: SupervisorState,
        trace_id: str = ""
    ) -> ChatResponse:
        """Handle STATUS intent - summarize current state without running agents."""
        dtp_stage = state["dtp_stage"]
        stage_name = DTP_STAGE_NAMES.get(dtp_stage, dtp_stage)
        status = state.get("status", "Unknown")
        message_lower = message.lower().strip()
        
        # Check if user is giving an affirmative/action response (wants analysis, not just status)
        affirmative_patterns = [
            r'\byes\b', r'\byeah\b', r'\bsure\b', r'\bplease\b',
            r'\banalyze\b', r'\bstart\b', r'\bdo it\b', r'\bproceed\b',
            r'tell me everything', r'show me everything', r'full analysis'
        ]
        
        # If user says "yes" or similar AND there's no recommendation yet, run analysis
        if not state.get("latest_agent_output"):
            if any(re.search(p, message_lower) for p in affirmative_patterns):
                return self._run_agent_analysis(case_id, message, state)
        
        # Build status summary
        response = f"**Current Status: {status}**\n\n"
        response += f"**Stage:** {dtp_stage} - {stage_name}\n"
        response += f"**Category:** {state.get('category_id', 'N/A')}\n"
        
        if state.get("supplier_id"):
            response += f"**Supplier:** {state['supplier_id']}\n"
        
        # Include latest recommendation if available
        if state.get("latest_agent_output"):
            output = state["latest_agent_output"]
            if output.get("recommended_strategy"):
                response += f"\n**Current Recommendation:** {output['recommended_strategy']}\n"
        
        # Add waiting for approval notice OR provide contextual next step
        if state.get("waiting_for_human"):
            response += "\n**Action Required:** This case is awaiting your approval to proceed. "
            response += "You can approve the recommendation or request changes."
        elif not state.get("latest_agent_output"):
            # No analysis yet - offer to run one
            response += "\n\nNo analysis has been run yet. Would you like me to **analyze this case** and provide a recommendation?"
        else:
            # Have output - offer specific follow-up based on output type
            agent_name = state.get("latest_agent_name", "")
            if "Strategy" in agent_name or "SOURCING_SIGNAL" in agent_name:
                response += "\n\nWould you like me to **explain the rationale** or **explore alternatives**?"
            elif "Supplier" in agent_name or "SUPPLIER_SCORING" in agent_name:
                response += "\n\nWould you like to **review supplier details** or **proceed to negotiation**?"
            else:
                response += "\n\nHow can I help you move forward?"
        
        return self._create_response(
            case_id, message, response, "STATUS", dtp_stage,
            waiting=state.get("waiting_for_human", False),
            trace_id=trace_id
        )
    
    def _handle_explain_intent(
        self,
        case_id: str,
        message: str,
        state: SupervisorState,
        trace_id: str = ""
    ) -> ChatResponse:
        """Handle EXPLAIN intent - explain existing recommendation."""
        dtp_stage = state["dtp_stage"]
        message_lower = message.lower().strip()
        
        # Check if message is actually an action request (should be DECIDE, not EXPLAIN)
        # Only treat as action request if it's a command, not a question
        # Questions like "What should I define?" are EXPLAIN, not DECIDE
        action_keywords = [
            "scan", "score", "draft", "support", "extract", "generate", "create",
            "recommend", "evaluate", "analyze", "prepare", "compare", "validate",
            "check", "build", "define", "track"
        ]
        # Check if it's a question (starts with what/which/how/when/where/why or contains "should I")
        is_question = (
            message_lower.startswith(("what", "which", "how", "when", "where", "why")) or
            "should i" in message_lower or "should we" in message_lower or
            "can you" in message_lower or "could you" in message_lower
        )
        # Only treat as action request if it's NOT a question AND contains action keywords
        is_action_request = not is_question and any(kw in message_lower for kw in action_keywords)
        
        if is_action_request:
            # This is actually a CREATE/DECIDE request - route to agent execution
            # Get conversation history for context
            conversation_history = []
            if self.conversation_manager and self.enable_conversation_memory:
                try:
                    conversation_history = self.conversation_manager.get_relevant_context(
                        case_id=case_id,
                        current_message=message,
                        max_tokens=1500
                    )
                except Exception as e:
                    logger.warning(f"Failed to retrieve conversation context: {e}")
            return self._run_agent_analysis(case_id, message, state, conversation_history, False)
        
        # Safety Net: If user asks "Why" about domain topics but we have no output, treat as analysis request
        # e.g., "Why are costs increasing?" -> Run SourcingSignalAgent
        domain_keywords = ['cost', 'spend', 'budget', 'increasing', 'rising', 'performance', 'score', 'signal', 'risk', 'trend', 'why']
        is_domain_question = any(kw in message_lower for kw in domain_keywords)
        
        if not state.get("latest_agent_output") and is_domain_question and ('?' in message or 'why' in message_lower):
             return self._run_agent_analysis(case_id, message, state)
        
        if not state.get("latest_agent_output"):
            # Check if user is giving an affirmative response (e.g., "yes", "tell me everything")
            # This means they want us to actually run analysis
            affirmative_patterns = [
                r'\byes\b', r'\byeah\b', r'\bsure\b', r'\bplease\b', r'\bok\b', r'\bokay\b',
                r'\bgo\b', r'\bdo it\b', r'\bproceed\b', r'\banalyze\b', r'\bstart\b',
                r'tell me', r'show me', r'everything', r'all\b', r'full\b'
            ]
            
            if any(re.search(p, message_lower) for p in affirmative_patterns):
                # User wants analysis - run the appropriate agent
                return self._run_agent_analysis(case_id, message, state)
            
            response = "No recommendation has been generated yet for this case.\n\n"
            response += "Would you like me to analyze this case and provide a strategy recommendation? Just say 'yes' or 'analyze this case'."
            return self._create_response(case_id, message, response, "EXPLAIN", dtp_stage, trace_id=trace_id)
        
        output = state["latest_agent_output"]
        agent_name = state.get("latest_agent_name", "Unknown")
        
        # Extract topic to understand what aspect user is asking about
        topic = self._extract_explanation_topic(message)
        
        # Check if user is asking about RFI/RFx requirements but latest output is from different agent
        # If asking about requirements and we're at DTP-03, they probably want RFx Draft info
        if topic == "requirements" and ("rfi" in message_lower or "rfx" in message_lower or "rfp" in message_lower):
            if agent_name not in ["RFX_DRAFT", "RfxDraft"]:
                # User is asking about RFI/RFx requirements but we don't have RFx Draft output
                # Check if we have any RFx artifact packs
                case_state = self.case_service.get_case_state(case_id)
                if case_state:
                    # Try to find RFx Draft artifact pack
                    all_packs = self.case_service.get_all_artifact_packs(case_id)
                    rfx_packs = [p for p in all_packs if p.agent_name in ["RFX_DRAFT", "RfxDraft"]]
                    if rfx_packs:
                        # Use the most recent RFx pack
                        latest_rfx_pack = rfx_packs[-1]
                        artifact_pack = latest_rfx_pack
                        # Extract output from artifact pack
                        if artifact_pack.artifacts:
                            # Build response from RFx artifact pack
                            response = "**RFI/RFx Requirements Status**\n\n"
                            has_missing = False
                            missing_info_list = []
                            missing_sections_list = []
                            completeness_score = 100
                            
                            for artifact in artifact_pack.artifacts:
                                if artifact.type == "RFX_PATH":
                                    if artifact.content:
                                        missing_info_list = artifact.content.get("missing_info", [])
                                    # Check content_text for indicators
                                    if artifact.content_text:
                                        if ("not fully defined" in artifact.content_text.lower() or 
                                            "requirements not" in artifact.content_text.lower() or
                                            "gather information" in artifact.content_text.lower()):
                                            has_missing = True
                                            if not missing_info_list:
                                                # Extract from content_text if available
                                                if "Requirements not fully defined" in artifact.content_text:
                                                    if "RFI to gather information" in artifact.content_text:
                                                        missing_info_list = ["Requirements not fully defined - RFI to gather information"]
                                elif artifact.type == "RFX_DRAFT_PACK":
                                    if artifact.content:
                                        missing_sections_list = artifact.content.get("missing_sections", [])
                                        completeness_score = artifact.content.get("completeness_score", 100)
                                        if completeness_score == 0 or completeness_score < 50:
                                            has_missing = True
                            
                            # Build response based on findings
                            # Completeness of 0% is a strong indicator
                            if has_missing or missing_info_list or missing_sections_list or completeness_score == 0:
                                response += "**Requirements are not fully defined.**\n\n"
                                if missing_info_list:
                                    for info in missing_info_list[:5]:
                                        response += f"- {info}\n"
                                elif completeness_score == 0:
                                    response += "- Requirements need to be defined before proceeding with the RFx\n"
                                    response += "- RFI is recommended to gather information from suppliers\n"
                                if missing_sections_list:
                                    response += "\n**Missing sections:**\n"
                                    for section in missing_sections_list[:5]:
                                        response += f"- {section}\n"
                                if completeness_score == 0:
                                    response += f"\n**Note:** The draft is {completeness_score}% complete, indicating requirements need to be defined.\n"
                            else:
                                response += "All requirements appear to be defined. The draft is ready for review.\n"
                            return self._create_response(case_id, message, response, "EXPLAIN", state["dtp_stage"], agents_called=["RFX_DRAFT"])
                    else:
                        # No RFx Draft has been run yet
                        response = "I don't have RFI/RFx requirements information yet. "
                        if state["dtp_stage"] in ["DTP-03", "DTP-04", "DTP-05"]:
                            response += "Would you like me to draft an RFx? Just say 'Draft RFx' or 'Create RFx draft'."
                        else:
                            response += f"RFx drafting is typically done at DTP-03 stage. You're currently at {state['dtp_stage']}. "
                            response += "Would you like me to proceed with RFx drafting?"
                        return self._create_response(case_id, message, response, "EXPLAIN", state["dtp_stage"])
        
        # Build explanation based on what was asked
        message_lower = message.lower()
        
        if "why" in message_lower or "reason" in message_lower or topic == "rationale":
            # Explain the rationale
            strategy = output.get("recommended_strategy", "N/A")
            rationale = output.get("rationale", [])
            
            response = f"The **{strategy}** strategy was recommended because:\n\n"
            if rationale:
                for i, r in enumerate(rationale, 1):
                    response += f"{i}. {r}\n"
            else:
                response += "No detailed rationale was recorded for this recommendation."
            
            if output.get("risk_assessment"):
                response += f"\n**Risk Assessment:** {output['risk_assessment']}"
        
        elif "risk" in message_lower:
            # Focus on risks
            risk = output.get("risk_assessment", "No specific risks identified.")
            response = f"**Risk Assessment:**\n\n{risk}"
        
        elif "confidence" in message_lower:
            confidence = output.get("confidence", 0)
            response = f"The recommendation has a **{confidence:.0%} confidence level**.\n\n"
            if confidence >= 0.8:
                response += "This indicates high certainty based on the available data."
            elif confidence >= 0.6:
                response += "This indicates moderate certainty. Additional data could improve the recommendation."
            else:
                response += "This indicates lower certainty. Consider gathering more information."
        
        else:
            # General explanation - handle different agent outputs
            response = f"**Analysis from {agent_name} Agent**\n\n"
            
            # Handle SourcingSignal agent output (support enum and legacy names)
            if agent_name in ["SOURCING_SIGNAL", "SourcingSignal", "SignalInterpretation"]:
                signals = output.get("signals", [])
                urgency = output.get("urgency_score", 0)
                summary = output.get("summary", "")
                
                if summary:
                    response += f"{summary}\n\n"
                
                if signals:
                    response += f"**Detected {len(signals)} Signals** (Urgency: {urgency}/10)\n\n"
                    for s in signals[:5]:
                        severity = s.get("severity", "medium")
                        msg = s.get("message", "Signal detected")
                        response += f"- [{severity.upper()}] {msg}\n"
                else:
                    response += "No significant signals detected at this time.\n"
            
            # Handle SupplierScoring agent output (support enum and legacy names)
            elif agent_name in ["SUPPLIER_SCORING", "SupplierScoring"]:
                shortlist = output.get("shortlisted_suppliers", [])
                recommendation = output.get("recommendation", "")
                
                if recommendation:
                    response += f"{recommendation}\n\n"
                
                if shortlist:
                    response += f"**Shortlisted {len(shortlist)} Suppliers:**\n"
                    for s in shortlist[:5]:
                        name = s.get("supplier_name", s.get("supplier_id", "Unknown"))
                        score = s.get("total_score", 0)
                        response += f"- {name}: {score:.1f}/10\n"
            
            # Handle RfxDraft agent output (support enum and legacy names)
            elif agent_name in ["RFX_DRAFT", "RfxDraft"]:
                # Try to get detailed info from artifact pack
                case_state = self.case_service.get_case_state(case_id)
                artifact_pack = None
                if case_state:
                    latest_pack_id = case_state.get("latest_artifact_pack_id")
                    if latest_pack_id and topic in ["requirements", "sections", "completeness"]:
                        artifact_pack = self.case_service.get_artifact_pack(latest_pack_id)
                
                rfx_type = output.get("rfx_type", "RFx")
                sections = output.get("sections", [])
                completeness = output.get("completeness_score", 0)
                
                # Topic-based responses
                if topic == "requirements":
                    # Extract requirements-related info from artifacts or output
                    missing_info = output.get("missing_info", [])
                    missing_sections = output.get("missing_sections", [])
                    incomplete_sections = output.get("incomplete_sections", [])
                    has_missing_requirements = False
                    
                    if artifact_pack:
                        # Extract from artifact content - check both content dict and content_text
                        for artifact in artifact_pack.artifacts:
                            if artifact.type == "RFX_PATH":
                                if artifact.content:
                                    missing_info = artifact.content.get("missing_info", missing_info)
                                # Also check content_text for "Requirements not fully defined" or similar
                                if artifact.content_text and ("not fully defined" in artifact.content_text.lower() or 
                                                               "requirements not" in artifact.content_text.lower() or
                                                               "gather information" in artifact.content_text.lower()):
                                    has_missing_requirements = True
                                    # Extract missing info from content_text if not in content dict
                                    if not missing_info and "Requirements not fully defined" in artifact.content_text:
                                        # Try to extract the reason from content_text
                                        if "RFI to gather information" in artifact.content_text:
                                            missing_info = ["Requirements not fully defined - RFI to gather information"]
                            elif artifact.type == "RFX_DRAFT_PACK":
                                if artifact.content:
                                    missing_sections = artifact.content.get("missing_sections", missing_sections)
                                    incomplete_sections = artifact.content.get("incomplete_sections", incomplete_sections)
                                    # Check completeness score from content
                                    pack_completeness = artifact.content.get("completeness_score", completeness)
                                    if pack_completeness == 0 or pack_completeness < 50:
                                        has_missing_requirements = True
                                    completeness = pack_completeness  # Use the pack's completeness score
                    
                    # Also check completeness score - 0% means requirements are not defined
                    if completeness == 0:
                        has_missing_requirements = True
                    
                    response += f"**{rfx_type} Draft - Requirements Status**\n\n"
                    
                    # Determine if requirements are missing based on multiple indicators
                    # Completeness of 0% is a strong indicator that requirements are not defined
                    if has_missing_requirements or missing_sections or missing_info or completeness == 0:
                        response += "**Requirements are not fully defined.**\n\n"
                        if missing_info:
                            for info in missing_info[:5]:
                                response += f"- {info}\n"
                        elif completeness == 0:
                            # If completeness is 0%, requirements are definitely not defined
                            response += "- Requirements need to be defined before proceeding with the RFx\n"
                            response += "- RFI is recommended to gather information from suppliers\n"
                        if missing_sections:
                            response += "\n**Missing sections:**\n"
                            for section in missing_sections[:5]:
                                response += f"- {section}\n"
                        if incomplete_sections:
                            response += "\n**Incomplete sections:**\n"
                            for section in incomplete_sections[:5]:
                                response += f"- {section}\n"
                        # Add completeness info if 0%
                        if completeness == 0:
                            response += f"\n**Note:** The draft is {completeness}% complete, indicating requirements need to be defined.\n"
                    else:
                        response += "All requirements appear to be defined. The draft is ready for review.\n"
                
                elif topic == "sections":
                    response += f"**{rfx_type} Draft - Sections**\n\n"
                    if sections:
                        response += f"**Assembled {len(sections)} sections:**\n"
                        for section in sections[:10]:
                            section_name = section if isinstance(section, str) else section.get("name", section.get("title", str(section)))
                            response += f"- {section_name}\n"
                    else:
                        response += "No sections have been assembled yet.\n"
                
                elif topic == "completeness":
                    response += f"**{rfx_type} Draft - Completeness: {completeness}%**\n\n"
                    missing_sections = output.get("missing_sections", [])
                    incomplete_sections = output.get("incomplete_sections", [])
                    
                    if artifact_pack:
                        for artifact in artifact_pack.artifacts:
                            if artifact.type == "RFX_DRAFT_PACK" and artifact.content:
                                missing_sections = artifact.content.get("missing_sections", missing_sections)
                                incomplete_sections = artifact.content.get("incomplete_sections", incomplete_sections)
                    
                    # Check if draft is actually complete (completeness > 0 AND no missing/incomplete sections)
                    if completeness == 0:
                        # Draft is not complete - provide actionable steps
                        response += "**The draft is not complete.**\n\n"
                        if artifact_pack and artifact_pack.next_actions:
                            response += "**Recommended Next Steps:**\n"
                            for action in artifact_pack.next_actions[:5]:
                                response += f"- {action.label}\n"
                        else:
                            response += "**To complete the draft:**\n"
                            if missing_sections:
                                response += f"- Add {len(missing_sections)} missing sections\n"
                            if incomplete_sections:
                                response += f"- Complete {len(incomplete_sections)} incomplete sections\n"
                            if not missing_sections and not incomplete_sections:
                                response += "- Define requirements before proceeding\n"
                                response += "- Consider running RFI to gather information from suppliers\n"
                    elif missing_sections or incomplete_sections:
                        # Draft is partially complete but has missing/incomplete sections
                        response += "**To complete the draft:**\n"
                        if artifact_pack and artifact_pack.next_actions:
                            for action in artifact_pack.next_actions[:5]:
                                response += f"- {action.label}\n"
                        else:
                            if missing_sections:
                                response += f"- Add {len(missing_sections)} missing sections\n"
                            if incomplete_sections:
                                response += f"- Complete {len(incomplete_sections)} incomplete sections\n"
                    else:
                        # Draft is complete
                        response += "The draft is complete and ready for review.\n"
                
                else:
                    # General explanation
                    response += f"**{rfx_type} Draft** - {completeness}% complete\n\n"
                    if sections:
                        response += f"Assembled {len(sections)} sections.\n"
            
            # Handle NegotiationSupport agent output (support enum and legacy names)
            elif agent_name in ["NEGOTIATION_SUPPORT", "NegotiationSupport"]:
                targets = output.get("target_terms", {})
                leverage = output.get("leverage_points", [])
                
                if targets:
                    price = targets.get("price_target", 0)
                    response += f"**Target Price:** ${price:,.0f}\n\n"
                
                if leverage:
                    response += f"**{len(leverage)} Leverage Points Identified**\n"
            
            # Handle ContractSupport agent output (support enum and legacy names)
            elif agent_name in ["CONTRACT_SUPPORT", "ContractSupport"]:
                key_terms = output.get("key_terms", {})
                is_compliant = output.get("is_compliant", True)
                
                response += f"**Compliance Status:** {'Compliant' if is_compliant else 'Issues Found'}\n\n"
                if key_terms:
                    response += "Key contract terms extracted and validated.\n"
            
            # Handle Implementation agent output (support enum and legacy names)
            elif agent_name in ["IMPLEMENTATION", "Implementation"]:
                annual = output.get("annual_savings", 0)
                total = output.get("total_savings", 0)
                checklist = output.get("checklist", [])
                
                response += f"**Projected Savings**\n"
                response += f"- Annual: ${annual:,.0f}\n"
                response += f"- Total: ${total:,.0f}\n\n"
                if checklist:
                    response += f"Rollout checklist with {len(checklist)} phases prepared.\n"
            
            # Fallback for Strategy agent or unknown
            else:
                strategy = output.get("recommended_strategy", "N/A")
                confidence = output.get("confidence", 0)
                rationale = output.get("rationale", [])
                
                response += f"Recommends **{strategy}** with {confidence:.0%} confidence.\n\n"
                
                if rationale:
                    response += "**Key Factors:**\n"
                    for r in rationale[:3]:
                        response += f"- {r}\n"
            
            response += "\nWould you like me to explain any specific aspect in more detail?"
        
        return self._create_response(
            case_id, message, response, "EXPLAIN", dtp_stage,
            agents_called=[agent_name] if agent_name else []
        )
    
    def _extract_explanation_topic(self, message: str) -> str:
        """
        Extract what aspect of the output the user is asking about.
        
        Returns: "requirements", "risks", "completeness", "sections", "rationale", "suppliers", "general"
        """
        message_lower = message.lower()
        
        # Requirements topic
        if any(kw in message_lower for kw in ["requirements", "requirement", "not defined", "not fully defined", 
                                               "undefined", "missing requirements", "what requirements"]):
            return "requirements"
        
        # Sections topic
        if any(kw in message_lower for kw in ["sections", "section", "what sections", "which sections"]):
            return "sections"
        
        # Completeness topic - includes "how to complete" questions
        if any(kw in message_lower for kw in ["completeness", "complete", "how complete", "how finished", 
                                               "how to complete", "how can we complete", "how do i complete",
                                               "how can i complete", "how to finish", "how can we finish"]):
            return "completeness"
        
        # Risks topic
        if any(kw in message_lower for kw in ["risk", "risks", "issues", "problems", "concerns"]):
            return "risks"
        
        # Rationale topic
        if any(kw in message_lower for kw in ["why", "reason", "rationale", "because", "explain why"]):
            return "rationale"
        
        # Suppliers topic
        if any(kw in message_lower for kw in ["suppliers", "supplier", "scoring", "scores", "shortlist"]):
            return "suppliers"
        
        # General (default)
        return "general"
    
    def _handle_explore_intent(
        self,
        case_id: str,
        message: str,
        state: SupervisorState,
        trace_id: str = ""
    ) -> ChatResponse:
        """Handle EXPLORE intent - explore alternatives without state change."""
        dtp_stage = state["dtp_stage"]
        message_lower = message.lower()
        
        # Check what alternative they're asking about
        if "alternative" in message_lower or "other option" in message_lower:
            current_strategy = None
            if state.get("latest_agent_output"):
                current_strategy = state["latest_agent_output"].get("recommended_strategy")
            
            all_strategies = ["Renew", "Renegotiate", "RFx", "Monitor", "Terminate"]
            other_strategies = [s for s in all_strategies if s != current_strategy]
            
            response = f"**Alternative Strategies to Consider:**\n\n"
            for strat in other_strategies:
                if strat == "Renew":
                    response += "- **Renew:** Extend the current contract with existing terms\n"
                elif strat == "Renegotiate":
                    response += "- **Renegotiate:** Modify terms with the current supplier\n"
                elif strat == "RFx":
                    response += "- **RFx:** Open competitive bidding to the market\n"
                elif strat == "Monitor":
                    response += "- **Monitor:** Delay decision and continue monitoring\n"
                elif strat == "Terminate":
                    response += "- **Terminate:** End the relationship with current supplier\n"
            
            response += "\nWould you like me to analyze any of these alternatives in detail?"
        
        elif "what if" in message_lower:
            # Hypothetical scenario
            response = "I can help you explore that scenario.\n\n"
            response += "Based on the current case data, here are some considerations:\n\n"
            
            if state.get("latest_agent_output"):
                output = state["latest_agent_output"]
                response += f"- Current recommendation: {output.get('recommended_strategy', 'N/A')}\n"
                response += f"- Risk level: {output.get('risk_assessment', 'Not assessed')}\n"
            
            response += "\nNote: Exploring alternatives does not change the current recommendation. "
            response += "You would need to request a new analysis to change the recommendation."
        
        else:
            # General exploration
            response = "I can help you explore options for this case.\n\n"
            response += "You can ask me:\n"
            response += "- What are the alternatives to the current recommendation?\n"
            response += "- What if we chose a different strategy?\n"
            response += "- What are the risks of each option?\n"
            response += "\nThis exploration won't change the case state."
        
        return self._create_response(
            case_id, message, response, "EXPLORE", dtp_stage, trace_id=trace_id
        )
    
    def _handle_decide_intent(
        self,
        case_id: str,
        message: str,
        state: SupervisorState,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        use_tier_2: bool = False,
        trace_id: str = ""
    ) -> ChatResponse:
        """Handle DECIDE intent - either process decision or run agent."""
        dtp_stage = state["dtp_stage"]
        message_lower = message.lower()
        
        # Check if they're asking for new analysis
        needs_analysis = any(kw in message_lower for kw in [
            "recommend", "analyze", "suggest", "strategy", "evaluate"
        ])
        
        if needs_analysis:
            # Run appropriate agent
            return self._run_agent_analysis(case_id, message, state, conversation_history, use_tier_2)
        
        # If already waiting and they say something like "proceed"
        if state.get("waiting_for_human"):
            return self._create_response(
                case_id, message,
                "The case is awaiting your decision. Please click **Approve** or **Request Revision** in the Decision panel, "
                "or you can say 'yes, approve' or 'reject the recommendation'.",
                "DECIDE", dtp_stage, waiting=True
            )
        
        # Otherwise provide guidance
        response = "What decision would you like to make?\n\n"
        response += "You can:\n"
        response += "- Ask me to **recommend a strategy** for this case\n"
        response += "- Ask me to **evaluate suppliers** (at DTP-03)\n"
        response += "- Ask me to **create a negotiation plan** (at DTP-04)\n"
        
        return self._create_response(case_id, message, response, "DECIDE", dtp_stage, trace_id=trace_id)
    
    def _handle_general_intent(
        self,
        case_id: str,
        message: str,
        state: SupervisorState,
        trace_id: str = ""
    ) -> ChatResponse:
        """Handle general/unknown intent with helpful response."""
        dtp_stage = state["dtp_stage"]
        stage_name = DTP_STAGE_NAMES.get(dtp_stage, dtp_stage)
        message_lower = message.lower().strip()
        
        # Check if user is giving an affirmative/action response
        affirmative_patterns = [
            r'\byes\b', r'\byeah\b', r'\bsure\b', r'\bplease\b',
            r'\banalyze\b', r'\bstart\b', r'\bdo it\b', r'\bproceed\b',
            r'tell me everything', r'show me everything', r'everything'
        ]
        
        # If no recommendation yet and user says "yes" or similar, run analysis
        if not state.get("latest_agent_output"):
            if any(re.search(p, message_lower) for p in affirmative_patterns):
                # Get conversation history if enabled
                conversation_history = []
                if self.conversation_manager and self.enable_conversation_memory:
                    try:
                        conversation_history = self.conversation_manager.get_relevant_context(
                            case_id, message, max_tokens=1500
                        )
                    except Exception:
                        pass
                return self._run_agent_analysis(case_id, message, state, conversation_history, False)
        
        response = f"I'm here to help with case {case_id}.\n\n"
        response += f"Currently at **{dtp_stage} - {stage_name}**.\n\n"
        response += "I can help you:\n"
        response += "- **Get status:** 'What is the current status?'\n"
        response += "- **Understand:** 'Why is this strategy recommended?'\n"
        response += "- **Explore:** 'What are the alternatives?'\n"
        response += "- **Decide:** 'Recommend a strategy for this case'\n"
        
        if state.get("waiting_for_human"):
            response += "\n**Note:** This case is awaiting your approval decision."
        
        return self._create_response(case_id, message, response, "UNKNOWN", dtp_stage, trace_id=trace_id)
    
    def _run_agent_analysis(
        self,
        case_id: str,
        message: str,
        state: SupervisorState,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        use_tier_2: bool = False
    ) -> ChatResponse:
        """Run agent analysis when explicitly requested."""
        dtp_stage = state["dtp_stage"]
        
        # Use hybrid two-level intent classification (rules + LLM)
        classification_context = {
            "dtp_stage": dtp_stage,
            "category_id": state.get("category_id"),
            "has_existing_output": bool(state.get("latest_agent_output")),
            "status": state.get("status"),
            "waiting_for_human": state.get("waiting_for_human", False)
        }
        
        intent_result = IntentRouter.classify_intent_hybrid(message, classification_context)
        
        # Log classification result for debugging
        logger.debug(
            f"Intent classification: user_goal={intent_result.user_goal}, "
            f"work_type={intent_result.work_type}, confidence={intent_result.confidence:.2f}, "
            f"rationale={intent_result.rationale}"
        )
        
        # Get action plan from intent
        action_plan = IntentRouter.get_action_plan(intent_result, dtp_stage)
        
        # Log action plan for debugging
        logger.debug(
            f"Action plan: agent={action_plan.agent_name}, tasks={len(action_plan.tasks)}, "
            f"approval_required={action_plan.approval_required}"
        )
        
        # Try new official agents first
        agent = self._official_agents.get(action_plan.agent_name)
        
        if agent:
            return self._run_official_agent(
                case_id, message, state, agent, action_plan, intent_result, conversation_history, use_tier_2
            )
        
        # Fall back to legacy agents
    
    def process_message_langgraph(
        self,
        case_id: str,
        user_message: str,
        use_tier_2: bool = False,
        case_state: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """
        Process a user message using the unified LangGraph workflow.
        
        Args:
            case_id: The ID of the case context
            user_message: The raw natural language message from the user
            use_tier_2: Whether to use more powerful (expensive) models
            
        Returns:
            ChatResponse: Structured response including natural language, artifacts, and metadata
        """
        # 1. Get or create case state
        # If case_state is provided (from frontend session), use it directly
        if case_state is not None:
            # Convert Case object to dict if needed
            if hasattr(case_state, "model_dump"):
                state = case_state.model_dump()
            elif hasattr(case_state, "__dict__"):
                state = vars(case_state)
            else:
                state = dict(case_state) if case_state else {}
        else:
            state = self.case_service.get_case_state(case_id)
            
        if not state:
            # Create minimal state for new conversations
            state = {
                "case_id": case_id,
                "dtp_stage": "DTP-01",
                "category_id": "General",
                "trigger_source": "User",
                "status": "In Progress",
                "activity_log": [],
                "chat_history": []
            }

        # 2. Check for manual override / basic intents that don't need full workflow (optional optimization)
        # For now, we route EVERYTHING through LangGraph for consistency, 
        # unless it's a simple "ping" which the graph handles anyway.

        # 3. Prepare initial state for workflow
        # We need to map the stored case state to the PipelineState expected by LangGraph
        from utils.state import PipelineState
        from utils.schemas import BudgetState, ChatMessage
        
        # Initialize budget if missing
        if "budget_state" not in state:
             # Create default budget state
             state["budget_state"] = BudgetState(
                 total_budget_usd=10.0,
                 total_cost_usd=0.0,
                 tokens_used=0,
                 model_usage={}
             )
        
        # UPDATE CHAT HISTORY (USER)
        # Ensure chat_history exists (handles legacy cases)
        if "chat_history" not in state:
            state["chat_history"] = []
        
        # Add User message
        new_user_msg = ChatMessage(role="user", content=user_message)
        # We append as dict to state because CaseService.get_case_state returns dict
        # and we want to serialize it easily later
        state["chat_history"].append(new_user_msg.model_dump())
        
        # Map DB state to PipelineState 
        # Note: In a real prod env, we might need a more robust mapper. 
        # Here we assume state keys mostly match PipelineState.
        workflow_state = dict(state)
        
        # CRITICAL MAPPING FIX:
        # SupervisorState does NOT have a "case_summary" key. 
        # PipelineState expects it. We must CONSTRUCT it from flat fields.
        if "case_summary" not in workflow_state:
            from shared.schemas import CaseSummary
            workflow_state["case_summary"] = CaseSummary(
                case_id=workflow_state.get("case_id", case_id),
                name=workflow_state.get("name", "Unnamed Case"),
                category_id=workflow_state.get("category_id", "UNKNOWN"),
                contract_id=workflow_state.get("contract_id"),
                supplier_id=workflow_state.get("supplier_id"),
                dtp_stage=workflow_state.get("dtp_stage", "DTP-01"),
                trigger_source=workflow_state.get("trigger_source", "User"),
                status=workflow_state.get("status", "In Progress"),
                created_date=workflow_state.get("created_date", ""),
                updated_date=workflow_state.get("updated_date", ""),
                summary_text=workflow_state.get("summary_text", ""),
                key_findings=workflow_state.get("key_findings", []),
                recommended_action=workflow_state.get("recommended_action")
            )
            
        # Map chat history to simplified format for Agents if needed
        # PipelineState expects List[Dict[str, str]]
        if "chat_history" in workflow_state:
            workflow_state["conversation_history"] = [
                {"role": m.get("role"), "content": m.get("content")} 
                for m in workflow_state["chat_history"]
            ]
            
        workflow_state["user_intent"] = user_message
        workflow_state["use_tier_2"] = use_tier_2

        # ISSUE #1 FIX: Only clear transient state for explicit NEW WORK requests
        # Previously, this cleared output on EVERY message where waiting_for_human=False,
        # which caused the loop after approval (output was cleared, Supervisor re-ran agent)
        # Now we only clear for explicit new analysis requests, NOT status/explain/follow-up
        intent_lower = user_message.lower()
        
        # Keywords that indicate user wants NEW analysis (should clear old output)
        is_new_work_request = any(kw in intent_lower for kw in [
            "analyze", "run", "create", "generate", "start", "begin", "new", 
            "scan", "evaluate", "assess", "check signals", "find suppliers"
        ])
        
        # Keywords that indicate status/explain/follow-up (should preserve output)
        is_status_or_question = any(kw in intent_lower for kw in [
            "what", "why", "how", "status", "explain", "tell me about", 
            "show", "summary", "details", "next", "?"
        ])
        
        # Only clear if it's a new work request AND NOT a question/status check
        should_clear_state = is_new_work_request and not is_status_or_question
        
        if not workflow_state.get("waiting_for_human") and should_clear_state:
            workflow_state["latest_agent_output"] = None
            workflow_state["latest_agent_name"] = None
            workflow_state["visited_agents"] = []
        
        # Ensure critical fields exist
        if "visited_agents" not in workflow_state:
            workflow_state["visited_agents"] = []
        if "iteration_count" not in workflow_state:
            workflow_state["iteration_count"] = 0
            
        # 4. Run the Workflow
        try:
            final_state = self._run_workflow(workflow_state)
            
            # 5. Generate Response using ResponseAdapter (MOVED BEFORE SAVE)
            # This decouples the "what happened" (state) from "what we say" (chat)
            from utils.response_adapter import get_response_adapter
            adapter = get_response_adapter()
            
            # Extract necessary context for the adapter
            latest_output = final_state.get("latest_agent_output")
            case_memory = final_state.get("case_memory")
            waiting_for_human = final_state.get("waiting_for_human", False)
            contradictions = final_state.get("detected_contradictions", [])
            constraint_reflection = final_state.get("constraint_reflection")
            constraint_violations = final_state.get("constraint_violations")
            
            # Helper to convert state dict to what adapter expects (if needed)
            case_context_dict = {
                "case_id": case_id,
                "dtp_stage": final_state.get("dtp_stage"),
                "status": final_state.get("status"),
                "category_id": final_state.get("category_id")
            }
            
            assistant_message = adapter.generate_response(
                output=latest_output,
                case_state=case_context_dict,
                memory=case_memory,
                user_intent=user_message,
                waiting_for_human=waiting_for_human,
                contradictions=contradictions,
                constraint_reflection=constraint_reflection,
                constraint_violations=constraint_violations
            )
            
            # UPDATE CHAT HISTORY (ASSISTANT)
            # Add Assistant response to history before saving
            new_ai_msg = ChatMessage(role="assistant", content=assistant_message)
            if "chat_history" not in final_state:
                final_state["chat_history"] = []
            final_state["chat_history"].append(new_ai_msg.model_dump())
            
            # 6. Persist updated state (WITH HISTORY)
            # CRITICAL: Map PipelineState back to SupervisorState format
            # CaseService.save_case_state expects top-level 'status', 'dtp_stage', etc.
            # PipelineState has these in 'case_summary' object
            case_summary = final_state.get("case_summary")
            if case_summary:
                if hasattr(case_summary, "status"):
                    final_state["status"] = case_summary.status
                if hasattr(case_summary, "dtp_stage"):
                    final_state["dtp_stage"] = case_summary.dtp_stage
            # Ensure status exists (fallback)
            if "status" not in final_state:
                final_state["status"] = "In Progress"

            # 6.5 CRITICAL: Persist Agent Output as ArtifactPack (for Audit Trail)
            latest_output = final_state.get("latest_agent_output")
            latest_agent = final_state.get("latest_agent_name")
            
            # DEBUG LOGGING: Track artifact creation flow
            logger.info(f"[ARTIFACT DEBUG] Checking artifact creation conditions:")
            logger.info(f"[ARTIFACT DEBUG]   latest_output present: {latest_output is not None}")
            logger.info(f"[ARTIFACT DEBUG]   latest_output type: {type(latest_output).__name__ if latest_output else 'None'}")
            logger.info(f"[ARTIFACT DEBUG]   latest_agent: {latest_agent}")
            logger.info(f"[ARTIFACT DEBUG]   condition pass: {bool(latest_output and latest_agent and latest_agent != 'Supervisor')}")
            
            if latest_output and latest_agent and latest_agent != "Supervisor":
                try:
                    # FIX 1: Use centralized mapping for artifact type detection
                    # First try direct mapping lookup (handles all agent name variants)
                    art_type = AGENT_TO_ARTIFACT_TYPE.get(latest_agent)
                    
                    # Fallback: Check isinstance for Pydantic model types
                    if art_type is None:
                        if isinstance(latest_output, StrategyRecommendation):
                            art_type = ArtifactType.STRATEGY_RECOMMENDATION
                        elif isinstance(latest_output, SupplierShortlist):
                            art_type = ArtifactType.SUPPLIER_SHORTLIST
                        elif isinstance(latest_output, RFxDraft):
                            art_type = ArtifactType.RFX_DRAFT_PACK
                        elif isinstance(latest_output, NegotiationPlan):
                            art_type = ArtifactType.NEGOTIATION_PLAN
                        elif isinstance(latest_output, ContractExtraction):
                            art_type = ArtifactType.KEY_TERMS_EXTRACT
                        elif isinstance(latest_output, ImplementationPlan):
                            art_type = ArtifactType.IMPLEMENTATION_CHECKLIST
                        elif isinstance(latest_output, SignalAssessment):
                            art_type = ArtifactType.SIGNAL_REPORT
                        elif isinstance(latest_output, AgentDialogue):
                            art_type = ArtifactType.AUDIT_LOG_EVENT
                        else:
                            art_type = ArtifactType.AUDIT_LOG_EVENT  # Final fallback
                    
                    logger.info(f"[ARTIFACT DEBUG] Creating artifact for agent: {latest_agent}, type: {art_type.value}")

                    # Get metadata from last activity log (or create synthetic one)
                    act_log = final_state.get("activity_log", [])
                    last_log = act_log[-1] if act_log else None
                    
                    # FALLBACK: Create synthetic log if workflow didn't provide one
                    if not last_log and latest_output:
                        # Create a synthetic log entry from available data
                        output_summary = ""
                        if hasattr(latest_output, "recommendation"):
                            output_summary = str(latest_output.recommendation)
                        elif hasattr(latest_output, "explanation"):
                            output_summary = str(latest_output.explanation)
                        elif hasattr(latest_output, "assessment_summary"):
                            output_summary = str(latest_output.assessment_summary)
                        elif isinstance(latest_output, AgentDialogue):
                            output_summary = f"[Dialogue] {latest_output.message}"
                        else:
                            output_summary = f"Output from {latest_agent}"
                        
                        last_log = {
                            "agent_name": latest_agent,
                            "task_name": f"{latest_agent} Execution",
                            "timestamp": datetime.now().isoformat(),
                            "dtp_stage": final_state.get("dtp_stage", "Unknown"),
                            "output_summary": output_summary,
                            "token_total": 0,
                            "documents_retrieved": [],
                            "output_payload": {"reasoning_log": latest_output.reasoning} if isinstance(latest_output, AgentDialogue) else {}
                        }
                        # Add to state so it persists
                        if "activity_log" not in final_state:
                            final_state["activity_log"] = []
                        final_state["activity_log"].append(last_log)
                    
                    metadata = None
                    if last_log:
                        # Handle both dict and object
                        log_dict = last_log if isinstance(last_log, dict) else last_log.__dict__
                        
                        # Extract reasoning log if available
                        out_payload = log_dict.get("output_payload", {})
                        reasoning_log = out_payload.get("reasoning_log")
                        
                        summary_text = log_dict.get("output_summary", "")
                        if reasoning_log:
                            # Format reasoning log as markdown for better readability
                            summary_text += "\n\n**Reasoning Trace:**\n"
                            if isinstance(reasoning_log, dict):
                                if "thinking" in reasoning_log:
                                    summary_text += f"**Thinking:** {reasoning_log['thinking']}\n"
                                if "decision_factors" in reasoning_log:
                                    summary_text += f"\n**Decision Factors:**\n"
                                    for factor in reasoning_log['decision_factors']:
                                        summary_text += f"- {factor}\n"
                                if "rationale" in reasoning_log:
                                    summary_text += f"\n**Rationale:**\n"
                                    for r in reasoning_log['rationale']:
                                        if isinstance(r, str):
                                            summary_text += f"- {r}\n"
                            else:
                                summary_text += str(reasoning_log)

                        task_detail = TaskExecutionDetail(
                            task_name=log_dict.get("task_name", "Execute"),
                            execution_order=1,
                            status="completed",
                            started_at=log_dict.get("timestamp"),
                            completed_at=log_dict.get("timestamp"),
                            tokens_used=log_dict.get("token_total", 0),
                            output_summary=summary_text,
                            grounding_sources=log_dict.get("documents_retrieved", [])
                        )
                        
                        metadata = ExecutionMetadata(
                            agent_name=log_dict.get("agent_name", latest_agent),
                            dtp_stage=log_dict.get("dtp_stage", final_state.get("dtp_stage", "Unknown")),
                            execution_timestamp=log_dict.get("timestamp", datetime.now().isoformat()),
                            total_tokens_used=log_dict.get("token_total", 0),
                            estimated_cost_usd=log_dict.get("estimated_cost_usd", 0.0),
                            documents_retrieved=log_dict.get("documents_retrieved", []),
                            task_details=[task_detail],
                            user_message=user_message,
                            intent_classified=final_state.get("intent_classification", ""),
                            model_used=log_dict.get("model_used", "Unknown")
                        )

                    # Create Artifact
                    # Convert Pydantic output to dict if needed
                    content_dict = latest_output
                    if hasattr(latest_output, "model_dump"):
                        content_dict = latest_output.model_dump()
                    elif hasattr(latest_output, "__dict__"):
                        content_dict = latest_output.__dict__

                    artifact = Artifact(
                        artifact_id=str(uuid.uuid4()),
                        type=art_type.value if hasattr(art_type, "value") else str(art_type),
                        title=f"{latest_agent} Output",
                        content=content_dict if isinstance(content_dict, dict) else {"raw": str(content_dict)},
                        created_at=datetime.now().isoformat(),
                        created_by_agent=latest_agent
                    )
                    
                    pack = ArtifactPack(
                        pack_id=str(uuid.uuid4()),
                        artifacts=[artifact],
                        agent_name=latest_agent,
                        created_at=datetime.now().isoformat(),
                        execution_metadata=metadata
                    )
                    
                    # Save pack
                    self.case_service.save_artifact_pack(case_id, pack)
                    final_state["latest_artifact_pack_id"] = pack.pack_id
                    logger.info(f"[ARTIFACT DEBUG] SUCCESS: Saved artifact pack {pack.pack_id} for agent {latest_agent}")
                    
                except Exception as e:
                    logger.error(f"[ARTIFACT DEBUG] FAILED to create artifact pack: {e}")
                    import traceback
                    logger.error(f"[ARTIFACT DEBUG] Traceback: {traceback.format_exc()}")
                    
                    # FIX 2: Add error visibility - surface failures to activity log
                    if "activity_log" not in final_state:
                        final_state["activity_log"] = []
                    final_state["activity_log"].append({
                        "timestamp": datetime.now().isoformat(),
                        "case_id": case_id,
                        "agent_name": "System",
                        "task_name": "Artifact Creation Error",
                        "output_summary": f"Failed to save artifact for {latest_agent}: {str(e)}",
                        "dtp_stage": final_state.get("dtp_stage", "Unknown"),
                        "output_payload": {"error": str(e), "agent": latest_agent}
                    })
            else:
                logger.warning(f"[ARTIFACT DEBUG] SKIPPED artifact creation: output={latest_output is not None}, agent={latest_agent}")

            # 6.6 NEW: Persist Supervisor Audit Log
            # Ensure Supervisor actions (routing, state updates) are visible in Audit Trail
            act_log = final_state.get("activity_log", [])
            if act_log:
                last_entry = act_log[-1]
                # Handle both dict and object
                entry_agent = last_entry.get("agent_name") if isinstance(last_entry, dict) else getattr(last_entry, "agent_name", "Unknown")
                
                if entry_agent == "Supervisor":
                    try:
                        entry_dict = last_entry if isinstance(last_entry, dict) else last_entry.__dict__
                        
                        sup_artifact = Artifact(
                            artifact_id=str(uuid.uuid4()),
                            type=ArtifactType.AUDIT_LOG_EVENT.value,
                            title="Supervisor Action",
                            content=entry_dict.get("output_payload", {}),
                            content_text=entry_dict.get("output_summary", "Supervisor executed action"),
                            created_at=datetime.now().isoformat(),
                            created_by_agent="Supervisor"
                        )
                        
                        # Create generic task detail for transparency
                        task_detail = TaskExecutionDetail(
                            task_name=entry_dict.get("task_name", "Coordinate Workflow"),
                            execution_order=1,
                            status="completed",
                            started_at=entry_dict.get("timestamp", datetime.now().isoformat()),
                            completed_at=entry_dict.get("timestamp", datetime.now().isoformat()),
                            tokens_used=entry_dict.get("token_total", 0),
                            output_summary=entry_dict.get("output_summary", ""),
                            grounding_sources=[]
                        )
                        
                        sup_pack = ArtifactPack(
                            pack_id=str(uuid.uuid4()),
                            artifacts=[sup_artifact],
                            agent_name="Supervisor",
                            created_at=datetime.now().isoformat(),
                            execution_metadata=ExecutionMetadata(
                                agent_name="Supervisor",
                                dtp_stage=final_state.get("dtp_stage", "Unknown"),
                                execution_timestamp=datetime.now().isoformat(),
                                total_tokens_used=entry_dict.get("token_total", 0),
                                task_details=[task_detail],
                                user_message=user_message or "",
                                intent_classified=final_state.get("intent_classification", "")
                            )
                        )
                        self.case_service.save_artifact_pack(case_id, sup_pack)
                    except Exception as e:
                        logger.error(f"Failed to save Supervisor artifact: {e}")

            self.case_service.save_case_state(final_state)
            
            # 7. Construct and return structured ChatResponse
            # Handle budget_state as either dict or Pydantic object
            budget_state = final_state.get("budget_state")
            if budget_state is None:
                tokens_used = 0
            elif isinstance(budget_state, dict):
                tokens_used = budget_state.get("tokens_used", 0)
            elif hasattr(budget_state, "tokens_used"):
                tokens_used = budget_state.tokens_used
            else:
                tokens_used = 0
                
            return self._create_response(
                case_id=case_id,
                user_message=user_message,
                assistant_message=assistant_message,
                intent=final_state.get("intent_classification", "UNKNOWN"), # Graph should set this
                dtp_stage=final_state.get("dtp_stage", "DTP-01"),
                agents_called=self._extract_agents_called(final_state),
                tokens=tokens_used,
                waiting=waiting_for_human,
                retrieval=final_state.get("retrieval_context"),
                workflow_summary=self._build_workflow_summary(final_state)
            )
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return self._create_error_response(case_id, user_message, str(e))

    def _run_workflow(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the LangGraph workflow.
        """
        from graphs.workflow import get_workflow_graph
        
        # Get the compiled graph
        app = get_workflow_graph()
        
        # Invoke the graph
        # config can include thread_id for checkpointer if we use it
        config = {"recursion_limit": 50} 
        
        final_state = app.invoke(initial_state, config)
        return final_state

    def _extract_agents_called(self, state: Dict[str, Any]) -> List[str]:
        """Extract list of unique agents called from activity log."""
        log = state.get("activity_log", [])
        agents = []
        for entry in log:
            if isinstance(entry, dict):
                agent = entry.get("agent_name")
            elif hasattr(entry, "agent_name"):
                agent = entry.agent_name
            else:
                agent = None
            if agent:
                agents.append(agent)
        return list(set(agents))

    def _build_workflow_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Build summary metadata for the frontend."""
        log = state.get("activity_log", [])
        return {
            "total_steps": len(log),
            "agents_visited": self._extract_agents_called(state),
            "final_agent": state.get("latest_agent_name"),
            "trace_id": state.get("trace_id", str(uuid.uuid4()))
        }

    def _create_error_response(self, case_id: str, user_message: str, error_msg: str) -> ChatResponse:
        """Create a standardized error response."""
        return ChatResponse(
            case_id=case_id,
            user_message=user_message,
            assistant_message=f"I encountered an error while processing your request: {error_msg}. Please try again.",
            intent_classified="ERROR",
            agents_called=[],
            tokens_used=0,
            dtp_stage="UNKNOWN",
            waiting_for_human=False,
            workflow_summary={"error": True},
            retrieval_context=None,
            timestamp=datetime.now().isoformat()
        )

    # ... keep existing _create_response for compatibility or updated usage ...
    def _create_response(
        self,
        case_id: str,
        user_message: str,
        assistant_message: str,
        intent: str,
        dtp_stage: str,
        agents_called: List[str] = None,
        tokens: int = 0,
        waiting: bool = False,
        retrieval: Dict = None,
        workflow_summary: Dict = None,
        trace_id: str = ""
    ) -> ChatResponse:
        """Create standardized response."""
        # Build workflow_summary if not provided
        if workflow_summary is None:
            workflow_summary = {"retrieval": retrieval} if retrieval else {}
        
        # Include trace_id in workflow_summary for debugging
        if trace_id:
            workflow_summary["trace_id"] = trace_id
        
        return ChatResponse(
            case_id=case_id,
            user_message=user_message,
            assistant_message=assistant_message,
            intent_classified=intent,
            agents_called=agents_called or [],
            tokens_used=tokens,
            dtp_stage=dtp_stage,
            waiting_for_human=waiting,
            workflow_summary=workflow_summary,
            retrieval_context=retrieval,
            timestamp=datetime.now().isoformat()
        )


    def process_decision(
        self,
        case_id: str,
        decision: str,
        reason: Optional[str] = None,
        edited_fields: Optional[Dict[str, Any]] = None,
        decision_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process human decision (approve/reject) with semantic validation and rich object storage.
        """
        state = self.case_service.get_case_state(case_id)
        if not state:
            return {"success": False, "message": "Case not found"}
        
        # 1. Update Decision Data (Merged from Console)
        current_stage = state.get("dtp_stage", "DTP-01")
        
        # Initialize nested structure if needed
        if "human_decision" not in state or not isinstance(state["human_decision"], dict):
            state["human_decision"] = {}
        if current_stage not in state["human_decision"]:
            state["human_decision"][current_stage] = {}
        
        # Merge new data if provided
        if decision_data:
            # Enrich with metadata (Ownership & Completeness)
            enriched_data = {}
            for k, v in decision_data.items():
                # Allow simple values or full objects, normalize to full object
                if isinstance(v, dict) and "answer" in v:
                    enriched_data[k] = v # Already rich
                else:
                    enriched_data[k] = {
                        "answer": v,
                        "decided_by_role": "User", # Placeholder for role-based auth
                        "timestamp": datetime.now().isoformat(),
                        "status": "final"
                    }
            
            state["human_decision"][current_stage].update(enriched_data)
        
        # 2. Semantic Validation (CRITICAL: Block if incomplete)
        if decision == "Approve":
            stage_def = DTP_DECISIONS.get(current_stage)
            if stage_def:
                human_decisions = state.get("human_decision") or {}
                current_answers = human_decisions.get(current_stage) or {}
                missing_questions = []
                
                for q in stage_def.get("questions", []):
                    if q.get("required", False):
                        # check dependency
                        if "dependency" in q:
                            dep_key, dep_val = list(q["dependency"].items())[0]
                            # Check if dependency matches answer
                            parent_ans_obj = current_answers.get(dep_key) or {}
                            parent_ans = parent_ans_obj.get("answer")
                            if parent_ans != dep_val:
                                continue # dependency not met, so not required
                        
                        if q["id"] not in current_answers:
                            missing_questions.append(q["text"])
                
                if missing_questions:
                    return {
                        "success": False,
                        "message": f"Cannot approve yet. Please answer the following: {', '.join(missing_questions)}"
                    }

        # 3. Path Enforcement (e.g. Terminate if sourcing not required)
        # This checks "critical_path" in definitions
        if decision == "Approve":
             current_answers = state["human_decision"].get(current_stage, {})
             stage_def = DTP_DECISIONS.get(current_stage)
             if stage_def:
                 for q in stage_def.get("questions", []):
                     if "critical_path" in q:
                         ans_obj = current_answers.get(q["id"])
                         if ans_obj:
                             ans_val = ans_obj.get("answer")
                             action = q["critical_path"].get(ans_val)
                             if action == "TERMINATE":
                                 # Special termination logic
                                  state["status"] = "Cancelled"
                                  self.case_service.save_case_state(state)
                                  return {
                                      "success": True, 
                                      "decision": "Terminated", 
                                      "message": f"Case terminated based on decision: {q['text']} = {ans_val}"
                                  }

        # 4. Proceed with Standard Flow
        # We need to inject the decision into the state and then run the graph
        # The Supervisor node handles 'human_decision' present in state
        
        # Log the high-level decision
        state["activity_log"].append({
            "timestamp": datetime.now().isoformat(),
            "case_id": case_id,
            "agent_name": "User",
            "task_name": "Decision",
            "output_summary": f"User {decision}d stage {current_stage}",
            "decision_details": decision_data 
        })
        
        self.case_service.save_case_state(state) # Save intermediate state

        # CRITICAL FIX: Construct case_summary before running workflow
        # The workflow graph nodes access state["case_summary"] directly
        if "case_summary" not in state:
            from shared.schemas import CaseSummary
            state["case_summary"] = CaseSummary(
                case_id=state.get("case_id", case_id),
                name=state.get("name", "Unnamed Case"),
                category_id=state.get("category_id", "UNKNOWN"),
                contract_id=state.get("contract_id"),
                supplier_id=state.get("supplier_id"),
                dtp_stage=state.get("dtp_stage", "DTP-01"),
                trigger_source=state.get("trigger_source", "User"),
                status=state.get("status", "In Progress"),
                created_date=state.get("created_date", ""),
                updated_date=state.get("updated_date", ""),
                summary_text=state.get("summary_text", ""),
                key_findings=state.get("key_findings", []),
                recommended_action=state.get("recommended_action")
            )

        # CRITICAL FIX: Ensure budget_state is initialized for workflow
        # The workflow graph nodes access state["budget_state"] directly
        if "budget_state" not in state:
            from utils.token_accounting import create_initial_budget_state
            state["budget_state"] = create_initial_budget_state()

        # Run workflow to let Supervisor process the decision
        try:
            # We pass a flag to tell the graph this is a decision event
            state["last_human_action"] = "approve_decision" if decision == "Approve" else "reject_decision"
            
            logger.info(f"[DEBUG process_decision] INPUT human_decision: {json.dumps(state.get('human_decision', {}), default=str)}")
            final_state = self._run_workflow(state)
            logger.info(f"[DEBUG process_decision] OUTPUT human_decision: {json.dumps(final_state.get('human_decision', {}), default=str)}")
            print(f"[DEBUG process_decision] State dtp_stage AFTER workflow: {final_state.get('dtp_stage')}")
            
            # Map CaseSummary back to top-level for persistence
            if "case_summary" in final_state:
                summary = final_state["case_summary"]
                if hasattr(summary, "status"):
                     final_state["status"] = summary.status
                if hasattr(summary, "dtp_stage"):
                     final_state["dtp_stage"] = summary.dtp_stage
            
            # Fallback for status
            if "status" not in final_state:
                 final_state["status"] = "In Progress"
                 
            self.case_service.save_case_state(final_state)
            
            return {
                "success": True,
                "decision": decision,
                "new_dtp_stage": final_state.get("dtp_stage"),
                "message": f"Decision '{decision}' processed successfully."
            }
        except Exception as e:
            logger.error(f"Error processing decision via workflow: {e}")
            return {"success": False, "message": f"Error processing decision: {e}"}

# Singleton
_chat_service = None

def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

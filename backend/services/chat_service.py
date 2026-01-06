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
from shared.constants import UserIntent, UserGoal, CaseStatus, DTP_STAGE_NAMES, AgentName
from shared.schemas import ChatResponse, ArtifactPack

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
        Process user message conversationally.
        
        NEW: If conversation memory enabled, retrieve context and save messages.
        NEW: Generate trace_id for request tracking and logging.
        """
        # Generate trace_id for this request
        trace_id = str(uuid.uuid4())
        
        # Log incoming message if routing logs enabled
        if ENABLE_ROUTING_LOGS:
            logger.info(f"[{trace_id}] CHAT_INPUT case={case_id} message={user_message[:100]}...")
        
        # Load case state
        state = self.case_service.get_case_state(case_id)
        if not state:
            logger.warning(f"[{trace_id}] Case not found: {case_id}")
            return self._create_response(
                case_id, user_message, "Case not found.", "UNKNOWN", "", trace_id=trace_id
            )
        
        # NEW: Get conversation context (if enabled)
        conversation_history = []
        if self.conversation_manager and self.enable_conversation_memory:
            try:
                conversation_history = self.conversation_manager.get_relevant_context(
                    case_id=case_id,
                    current_message=user_message,
                    max_tokens=1500  # Configurable
                )
            except Exception as e:
                # Graceful degradation: log error, continue without context
                logger.warning(f"Failed to retrieve conversation context: {e}")
                conversation_history = []
        
        # Check for approval/rejection in natural language
        if state.get("waiting_for_human"):
            approval_response = self._check_for_approval(user_message, case_id, state)
            if approval_response:
                # Save user message if conversation memory enabled
                if self.conversation_manager and self.enable_conversation_memory:
                    try:
                        self.conversation_manager.save_message(
                            case_id=case_id,
                            role="user",
                            content=user_message,
                            metadata={"intent": "APPROVAL_REJECTION"}
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save user message: {e}")
                return approval_response
        
        # Enhanced classification context with conversation history
        classification_context = {
            "dtp_stage": state["dtp_stage"],
            "has_existing_output": bool(state.get("latest_agent_output")),
            "category_id": state.get("category_id"),
            "status": state.get("status"),
            "waiting_for_human": state.get("waiting_for_human", False),
            # NEW: Enhanced context for better intent classification
            "latest_agent_name": state.get("latest_agent_name"),
            "conversation_history": conversation_history[:3] if conversation_history else [],  # Last 3 messages
            "conversation_length": len(conversation_history) if conversation_history else 0
        }
        
        # Classify intent with fallback handling
        fallback_used = False
        try:
            intent = IntentRouter.classify_intent(user_message, classification_context)
        except Exception as e:
            logger.error(f"[{trace_id}] Intent classification failed: {e}", exc_info=True)
            intent = UserIntent.EXPLAIN  # Safe fallback
            fallback_used = True
        
        # Log routing decision
        if ENABLE_ROUTING_LOGS:
            logger.info(f"[{trace_id}] ROUTING intent={intent.value} fallback_used={fallback_used}")
        
        # NEW: Save user message to database (if enabled)
        if self.conversation_manager and self.enable_conversation_memory:
            try:
                self.conversation_manager.save_message(
                    case_id=case_id,
                    role="user",
                    content=user_message,
                    metadata={
                        "intent": intent.value if hasattr(intent, 'value') else str(intent),
                        "use_tier_2": use_tier_2,
                        "trace_id": trace_id
                    }
                )
            except Exception as e:
                logger.warning(f"[{trace_id}] Failed to save user message: {e}")
                # Continue processing - message saving is non-critical
        
        # Handle different intents appropriately
        if intent == UserIntent.STATUS:
            response = self._handle_status_intent(case_id, user_message, state, trace_id)
        elif intent == UserIntent.EXPLAIN:
            response = self._handle_explain_intent(case_id, user_message, state, trace_id)
        elif intent == UserIntent.EXPLORE:
            response = self._handle_explore_intent(case_id, user_message, state, trace_id)
        elif intent == UserIntent.DECIDE:
            response = self._handle_decide_intent(case_id, user_message, state, conversation_history, use_tier_2, trace_id)
        else:
            # Default: provide helpful context
            response = self._handle_general_intent(case_id, user_message, state, trace_id)
        
        # NEW: Save assistant response (if enabled)
        if self.conversation_manager and self.enable_conversation_memory:
            try:
                self.conversation_manager.save_message(
                    case_id=case_id,
                    role="assistant",
                    content=response.assistant_message,
                    metadata={
                        "intent": response.intent_classified,
                        "agents_called": response.agents_called,
                        "tokens_used": response.tokens_used
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to save assistant message: {e}")
        
        return response
    
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
            result = self.process_decision(case_id, "Approve")
            if result["success"]:
                new_stage = result.get("new_dtp_stage", state["dtp_stage"])
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
        allowed_agents = IntentRouter.get_allowed_agents(UserIntent.DECIDE, dtp_stage)
        
        if not allowed_agents:
            return self._create_response(
                case_id, message,
                f"No analysis available at stage {dtp_stage}.",
                "DECIDE", dtp_stage
            )
        
        # Select and run legacy agent
        agent_name = self._select_agent(message, allowed_agents, dtp_stage)
        legacy_agent = self._agents.get(agent_name)
        
        if not legacy_agent:
            return self._create_response(
                case_id, message,
                "Unable to run analysis at this time.",
                "DECIDE", dtp_stage
            )
        
        case_context = {
            "case_id": case_id,
            "category_id": state.get("category_id"),
            "supplier_id": state.get("supplier_id"),
            "contract_id": state.get("contract_id"),
            "dtp_stage": dtp_stage
        }
        
        agent_result = legacy_agent.execute(case_context, message)
        
        # Update state
        if agent_result:
            state["latest_agent_output"] = agent_result.get("output")
            state["latest_agent_name"] = agent_result.get("agent_name")
            state["waiting_for_human"] = True
            state["status"] = CaseStatus.WAITING_HUMAN.value
            self.case_service.save_case_state(state)
        
        # Format response
        response = self._format_agent_response(agent_result)
        
        return self._create_response(
            case_id, message, response, "DECIDE", dtp_stage,
            agents_called=[agent_name],
            tokens=agent_result.get("tokens_used", 0) if agent_result else 0,
            waiting=True,
            retrieval=agent_result.get("retrieval_context") if agent_result else None
        )
    
    def _run_official_agent(
        self,
        case_id: str,
        message: str,
        state: SupervisorState,
        agent,
        action_plan,
        intent_result,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        use_tier_2: bool = False
    ) -> ChatResponse:
        """Run an official agent that returns ArtifactPack."""
        dtp_stage = state["dtp_stage"]
        
        case_context = {
            "case_id": case_id,
            "category_id": state.get("category_id"),
            "supplier_id": state.get("supplier_id"),
            "contract_id": state.get("contract_id"),
            "dtp_stage": dtp_stage,
            # Add estimated values for implementation agent
            "new_contract_value": state.get("latest_agent_output", {}).get("annual_value", 450000) if state.get("latest_agent_output") else 450000,
            "old_contract_value": 500000,
            "term_years": 3,
        }
        
        # NEW: Add conversation history if available (optional)
        if conversation_history:
            case_context["conversation_history"] = conversation_history
        
        # NEW: Estimate cost before execution (if conversation memory enabled)
        if self.conversation_manager and self.enable_conversation_memory:
            try:
                estimated_tokens, estimated_cost = self.conversation_manager.estimate_execution_cost(
                    conversation_history=conversation_history or [],
                    user_message=message,
                    agent_name=action_plan.agent_name,
                    use_tier_2=use_tier_2
                )
                
                # Check budget (configurable threshold)
                max_cost_per_message = float(os.getenv("MAX_COST_PER_MESSAGE", "1.0"))  # $1 default
                if estimated_cost > max_cost_per_message:
                    # Suggest more specific question or return cost warning
                    intent_for_response = self._map_user_goal_to_intent(intent_result.user_goal)
                    return self._create_response(
                        case_id, message,
                        f"⚠️ Estimated cost (${estimated_cost:.2f}) exceeds limit (${max_cost_per_message:.2f}). "
                        f"Please try a more specific question.",
                        intent_for_response, dtp_stage
                    )
            except Exception as e:
                logger.warning(f"Cost estimation failed: {e}")
                # Continue without cost check (backward compatible)
        
        # Execute agent
        agent_result = agent.execute(case_context, message)
        
        if not agent_result.get("success"):
            # Map user_goal to old intent format for _create_response
            intent_for_response = self._map_user_goal_to_intent(intent_result.user_goal)
            return self._create_response(
                case_id, message,
                "Analysis could not be completed. Please try again.",
                intent_for_response, dtp_stage
            )
        
        # Get artifact pack
        artifact_pack = agent_result.get("artifact_pack")
        
        # Persist artifact pack
        if artifact_pack:
            try:
                success = self.case_service.save_artifact_pack(case_id, artifact_pack)
                if not success:
                    logger.warning(f"Failed to save artifact pack {artifact_pack.pack_id} for case {case_id}")
            except Exception as e:
                logger.error(f"Error saving artifact pack: {e}", exc_info=True)
        
        # Update state
        state["latest_agent_output"] = agent_result.get("output", {})
        state["latest_agent_name"] = agent_result.get("agent_name")
        state["waiting_for_human"] = action_plan.approval_required
        if action_plan.approval_required:
            state["status"] = CaseStatus.WAITING_HUMAN.value
        # Update latest_artifact_pack_id in state (save_artifact_pack already updated the case in DB)
        if artifact_pack:
            state["latest_artifact_pack_id"] = artifact_pack.pack_id
        self.case_service.save_case_state(state)
        
        # Format response from artifact pack
        response = self._format_artifact_pack_response(artifact_pack)
        
        # Map user_goal to old intent format for _create_response
        intent_for_response = self._map_user_goal_to_intent(intent_result.user_goal)
        
        return self._create_response(
            case_id, message, response,
            intent_for_response, dtp_stage,
            agents_called=[action_plan.agent_name],
            tokens=agent_result.get("tokens_used", 0),
            waiting=action_plan.approval_required,
            retrieval=agent_result.get("retrieval_context") if agent_result else None,
            workflow_summary={
                "artifact_pack_id": artifact_pack.pack_id if artifact_pack else None,
                "artifacts_created": len(artifact_pack.artifacts) if artifact_pack else 0,
                "next_actions": len(artifact_pack.next_actions) if artifact_pack else 0,
            }
        )
    
    def _format_artifact_pack_response(self, pack: Optional[ArtifactPack]) -> str:
        """Format artifact pack as conversational response."""
        if not pack:
            return "Analysis complete."
        
        response_parts = []
        agent_name = pack.agent_name if pack else ""
        
        # Agent-specific introduction
        if "SOURCING_SIGNAL" in agent_name or "Signal" in agent_name:
            response_parts.append("**Sourcing Signal Analysis Complete**")
            response_parts.append("")
            if pack.artifacts:
                response_parts.append(f"I've analyzed {len(pack.artifacts)} signal(s) for this category:")
        elif "SUPPLIER_SCORING" in agent_name or "Supplier" in agent_name:
            response_parts.append("**Supplier Evaluation Complete**")
            response_parts.append("")
            if pack.artifacts:
                response_parts.append(f"I've scored and evaluated suppliers. Here are the results:")
        elif "RFX_DRAFT" in agent_name or "RFx" in agent_name or "Rfx" in agent_name:
            response_parts.append("**RFx Draft Complete**")
            response_parts.append("")
            if pack.artifacts:
                response_parts.append(f"I've prepared the RFx documentation:")
        elif "NEGOTIATION" in agent_name or "Negotiation" in agent_name:
            response_parts.append("**Negotiation Plan Ready**")
            response_parts.append("")
            if pack.artifacts:
                response_parts.append(f"I've created a negotiation strategy:")
        elif "CONTRACT" in agent_name or "Contract" in agent_name:
            response_parts.append("**Contract Analysis Complete**")
            response_parts.append("")
            if pack.artifacts:
                response_parts.append(f"I've reviewed the contract terms:")
        elif "IMPLEMENTATION" in agent_name or "Implementation" in agent_name:
            response_parts.append("**Implementation Plan Ready**")
            response_parts.append("")
            if pack.artifacts:
                response_parts.append(f"I've created an implementation roadmap:")
        else:
            # Generic fallback
            response_parts.append("**Analysis Complete**")
            response_parts.append("")
        
        # Add main artifacts
        if pack.artifacts:
            for artifact in pack.artifacts[:3]:
                response_parts.append(f"**{artifact.title}**")
                if artifact.content_text:
                    # Truncate long content but keep more context
                    content = artifact.content_text[:500] if len(artifact.content_text) > 500 else artifact.content_text
                    response_parts.append(content)
                elif artifact.content:
                    # Fallback to content dict if content_text is empty
                    content_str = str(artifact.content)[:500]
                    response_parts.append(content_str)
                response_parts.append("")
        else:
            # No artifacts - indicate this
            response_parts.append("Analysis completed successfully.")
            response_parts.append("")
        
        # Add next actions with agent-specific framing
        if pack.next_actions:
            if "SOURCING_SIGNAL" in agent_name:
                response_parts.append("**Recommended Actions:**")
            elif "SUPPLIER_SCORING" in agent_name:
                response_parts.append("**Next Steps in Supplier Selection:**")
            elif "RFX_DRAFT" in agent_name:
                response_parts.append("**Before Sending the RFx:**")
            elif "NEGOTIATION" in agent_name:
                response_parts.append("**Negotiation Preparation:**")
            elif "CONTRACT" in agent_name:
                response_parts.append("**Contract Review Actions:**")
            elif "IMPLEMENTATION" in agent_name:
                response_parts.append("**Implementation Steps:**")
            else:
                response_parts.append("**Recommended Next Steps:**")
            
            for action in pack.next_actions[:3]:
                response_parts.append(f"- {action.label}")
            response_parts.append("")
        
        # Add risks if any
        if pack.risks:
            response_parts.append("**Risks Identified:**")
            for risk in pack.risks[:2]:
                response_parts.append(f"- [{risk.severity.upper()}] {risk.description}")
            response_parts.append("")
        
        # Add notes
        if pack.notes:
            for note in pack.notes:
                response_parts.append(f"*{note}*")
        
        # Agent-specific closing message
        if pack.artifacts or pack.next_actions or pack.risks:
            response_parts.append("---")
            if "SOURCING_SIGNAL" in agent_name:
                response_parts.append("Review the signal analysis above. Would you like me to proceed with supplier evaluation?")
            elif "SUPPLIER_SCORING" in agent_name:
                response_parts.append("Review the supplier scores above. Ready to move forward with the shortlist?")
            elif "RFX_DRAFT" in agent_name:
                response_parts.append("Review the RFx draft above. Ready to send it to suppliers?")
            elif "NEGOTIATION" in agent_name:
                response_parts.append("Review the negotiation plan above. Ready to proceed with negotiations?")
            elif "CONTRACT" in agent_name:
                response_parts.append("Review the contract analysis above. Ready to finalize the agreement?")
            elif "IMPLEMENTATION" in agent_name:
                response_parts.append("Review the implementation plan above. Ready to begin rollout?")
            else:
                response_parts.append("Review the analysis above and let me know if you'd like to proceed or make changes.")
        else:
            response_parts.append("---")
            response_parts.append("Analysis complete. What would you like to do next?")
        
        return "\n".join(response_parts)
    
    def _format_agent_response(self, agent_result: Optional[Dict]) -> str:
        """Format agent output as conversational response."""
        if not agent_result:
            return "Analysis could not be completed. Please try again."
        
        output = agent_result.get("output", {})
        agent_name = agent_result.get("agent_name", "")
        
        if agent_name == "Strategy":
            strategy = output.get("recommended_strategy", "Monitor")
            confidence = output.get("confidence", 0)
            rationale = output.get("rationale", [])
            
            response = f"**Strategy Recommendation: {strategy}**\n\n"
            response += f"Confidence: {confidence:.0%}\n\n"
            
            if rationale:
                response += "**Rationale:**\n"
                for r in rationale:
                    response += f"- {r}\n"
            
            response += "\n---\nAwaiting your approval to proceed. Please review and approve or reject."
        
        elif agent_name == "SupplierEvaluation":
            suppliers = output.get("shortlisted_suppliers", [])
            response = f"**Supplier Evaluation Complete**\n\n"
            if suppliers:
                response += f"Shortlisted {len(suppliers)} suppliers:\n"
                for s in suppliers[:5]:
                    name = s.get('name', s.get('supplier_id', 'Unknown'))
                    score = s.get('score', 'N/A')
                    response += f"- {name}: {score}/10\n"
            response += "\n---\nAwaiting your approval."
        
        elif agent_name == "NegotiationSupport":
            objectives = output.get("negotiation_objectives", [])
            response = f"**Negotiation Plan Created**\n\n"
            if objectives:
                response += "**Objectives:**\n"
                for obj in objectives:
                    response += f"- {obj}\n"
            response += "\n---\nAwaiting your approval."
        
        else:
            response = json.dumps(output, indent=2)
        
        return response
    
    def _select_agent(
        self,
        message: str,
        allowed_agents: List[str],
        dtp_stage: str
    ) -> Optional[str]:
        """Select appropriate agent based on message."""
        message_lower = message.lower()
        
        if "strategy" in message_lower or "recommend" in message_lower:
            if "Strategy" in allowed_agents:
                return "Strategy"
        
        if "supplier" in message_lower or "evaluate" in message_lower:
            if "SupplierEvaluation" in allowed_agents:
                return "SupplierEvaluation"
        
        if "negotiat" in message_lower:
            if "NegotiationSupport" in allowed_agents:
                return "NegotiationSupport"
        
        return allowed_agents[0] if allowed_agents else None
    
    def _map_user_goal_to_intent(self, user_goal: str) -> str:
        """Map new UserGoal enum to old UserIntent format for ChatResponse."""
        mapping = {
            UserGoal.TRACK.value: UserIntent.STATUS.value,
            UserGoal.UNDERSTAND.value: UserIntent.EXPLAIN.value,
            UserGoal.CREATE.value: UserIntent.DECIDE.value,
            UserGoal.CHECK.value: UserIntent.DECIDE.value,
            UserGoal.DECIDE.value: UserIntent.DECIDE.value,
        }
        return mapping.get(user_goal, UserIntent.DECIDE.value)
    
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
            can_advance, _ = StateManager.can_advance_stage(state, True)
            if can_advance:
                state, _ = StateManager.advance_stage(state)
            state["status"] = CaseStatus.IN_PROGRESS.value
        else:
            state["status"] = CaseStatus.IN_PROGRESS.value
        
        state["waiting_for_human"] = False
        self.case_service.save_case_state(state)
        
        # Get updated state to return correct stage (in case it advanced)
        updated_state = self.case_service.get_case_state(case_id)
        final_stage = updated_state["dtp_stage"] if updated_state else state["dtp_stage"]
        
        return {
            "success": True,
            "decision": decision,
            "new_dtp_stage": final_stage,
            "message": f"Decision '{decision}' processed successfully"
        }


# Singleton
_chat_service = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

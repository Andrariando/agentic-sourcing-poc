"""
Intent classification and routing for the Supervisor.

TWO-LEVEL CLASSIFICATION:
- Primary: User Goal (TRACK, UNDERSTAND, CREATE, CHECK, DECIDE)
- Secondary: Work Type (ARTIFACT, DATA, APPROVAL, COMPLIANCE, VALUE)

LLM-FIRST CLASSIFICATION:
- LLM-based classification with structured output (primary path)
- Aggressive caching for performance (500 entries)
- Rule-based fallback (only for API errors or simple cases like greetings)
- Context-aware with conversation history

CONVERSATIONAL DESIGN:
- Detect greetings and simple responses
- STATUS for case updates
- EXPLAIN for understanding recommendations
- EXPLORE for alternatives
- DECIDE only for explicit action requests
"""
import re
import os
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from shared.constants import UserIntent, UserGoal, WorkType, AgentName
from shared.schemas import IntentResult, ActionPlan
import logging

logger = logging.getLogger(__name__)


class IntentClassificationSchema(BaseModel):
    """Structured output schema for LLM intent classification."""
    user_goal: str = Field(description="Primary user goal: TRACK, UNDERSTAND, CREATE, CHECK, or DECIDE")
    work_type: str = Field(description="Type of work needed: ARTIFACT, DATA, APPROVAL, COMPLIANCE, or VALUE")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    rationale: str = Field(description="Brief explanation of the classification decision")


class IntentRouter:
    """
    Classifies user intent and determines routing.
    
    Intent types:
    - STATUS: User wants status update (read-only, no agent)
    - EXPLAIN: User wants explanation of existing data (read-only, no agent)
    - EXPLORE: User wants to explore alternatives (may call agent, no state change)
    - DECIDE: User explicitly requests analysis or decision (calls agent)
    """
    
    # Greetings and acknowledgments (no agent call needed)
    GREETING_PATTERNS = [
        r'^hi\b', r'^hello\b', r'^hey\b', r'^good (morning|afternoon|evening)',
        r'^thanks\b', r'^thank you', r'^ok\b', r'^okay\b', r'^got it',
        r'^understood', r'^i see', r'^makes sense', r'^cool\b', r'^great\b',
        r'^perfect\b', r'^nice\b', r'^alright\b'
    ]
    
    # Status inquiry patterns
    STATUS_PATTERNS = [
        r'status', r'progress', r'update\b', r'where are we', r'current state',
        r"what's happening", r'how far', r'timeline', r'next step',
        r'what stage', r'which stage', r'current status', r'case status',
        r'tell me about (this|the) case', r'update me', r'brief me',
        r'summary', r'overview', r'catch me up'
    ]
    
    # Explain patterns (understanding existing data)
    EXPLAIN_PATTERNS = [
        r'what is', r'explain\b', r'describe', r'tell me about',
        r'how does', r'\bwhy\b', r'what does', r'meaning', r'definition',
        r'clarify', r'help me understand', r'can you explain', r"what's the",
        r'reason\b', r'rationale', r'basis', r'justify', r'grounds',
        r'confidence', r'evidence', r'how did you', r'what led to'
    ]
    
    # Explore patterns (hypotheticals, alternatives)
    EXPLORE_PATTERNS = [
        r'what if', r'alternative', r'options', r'could we', r'would it be possible',
        r'\bexplore\b', r'consider', r'compare', r'\bother\b', r'different\b',
        r'scenario', r'hypothetical', r'suppose', r'imagine',
        r'what would happen', r'pros and cons', r'trade-?off'
    ]
    
    # Decide patterns (explicit action requests) - ENHANCED
    DECIDE_PATTERNS = [
        # Action verbs (domain-specific)
        r'\bscan\b', r'\bscore\b', r'\bdraft\b', r'\bsupport\b', r'\bextract\b',
        r'\bgenerate\b', r'\bcreate\b', r'\bbuild\b', r'\bprepare\b', r'\bcompare\b',
        r'\bvalidate\b', r'\bcheck\b', r'\bdefine\b', r'\btrack\b',
        # General action verbs
        r'\brun\b', r'\banalyze\b', r'\bevaluate\b', r'\brecommend\b',
        r'\bexecute\b', r'\bstart\b', r'\bbegin\b', r'\blaunch\b',
        r'\binitiate\b', r'\bfinalize\b', r'\bselect\b', r'\bchoose\b',
        # Explicit requests
        r'give me a (strategy|recommendation|plan)',
        r'create a (strategy|recommendation|plan)',
        r'what (should|do) (we|i) do',
        r'suggest a (strategy|approach|plan)',
        r'(need|want) (a )?(strategy|recommendation|analysis)',
        # Composite action patterns
        r'scan (signals|for signals|all signals)',
        r'score (suppliers|supplier)',
        r'draft (rfx|rfp|rfq)',
        r'support (negotiation|negotiat)',
        r'extract (terms|key terms)',
        r'generate (plan|checklist|report)'
    ]
    
    # Approval patterns (handled separately in ChatService)
    APPROVAL_PATTERNS = [
        r'\bapprove\b', r'\bconfirm\b', r'\bproceed\b', r'\bgo ahead\b',
        r'\byes\b', r'\bok\b', r'\bokay\b', r'\baccept\b', r'\bagree\b',
        r"let's do it", r'sounds good', r'looks good', r'move forward'
    ]
    
    REJECTION_PATTERNS = [
        r'\breject\b', r'\bcancel\b', r'\bstop\b', r"\bdon't\b",
        r'\bdecline\b', r'\brefuse\b', r'\bwait\b', r'\bhold\b',
        r'not yet', r'not ready', r'no\b', r'revise', r'change'
    ]
    
    @classmethod
    def _user_goal_to_intent(cls, user_goal: str) -> UserIntent:
        """Map UserGoal to UserIntent for single-level classification."""
        goal_to_intent = {
            UserGoal.TRACK.value: UserIntent.STATUS,
            UserGoal.UNDERSTAND.value: UserIntent.EXPLAIN,
            UserGoal.CREATE.value: UserIntent.DECIDE,
            UserGoal.CHECK.value: UserIntent.DECIDE,
            UserGoal.DECIDE.value: UserIntent.DECIDE,
        }
        return goal_to_intent.get(user_goal, UserIntent.EXPLAIN)
    
    @classmethod
    def _classify_intent_rules_fallback(
        cls,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> UserIntent:
        """Fallback rule-based classification (only for errors or simple cases)."""
        message_lower = user_message.lower().strip()
        context = context or {}
        has_existing_output = context.get("has_existing_output", False)
        
        # Simple greeting check (no LLM needed)
        if any(re.search(p, message_lower) for p in cls.GREETING_PATTERNS):
            if len(message_lower.split()) <= 5:
                return UserIntent.STATUS
        
        # Simple status check
        if any(re.search(p, message_lower) for p in cls.STATUS_PATTERNS):
            return UserIntent.STATUS
        
        # Check for action requests (CREATE/DECIDE intent)
        # These should route to agent execution, not EXPLAIN
        action_keywords = [
            "recommend", "analyze", "evaluate", "score", "draft", "create",
            "generate", "scan", "compare", "prepare", "suggest", "propose",
            "assess", "check", "build", "define"
        ]
        # Check if it's a question
        is_question = (
            message_lower.startswith(("what", "which", "how", "when", "where", "why")) or
            "should i" in message_lower or "should we" in message_lower or
            "can you" in message_lower or "could you" in message_lower
        )
        # If it contains action keywords and is NOT a question, it's a DECIDE intent
        if not is_question and any(kw in message_lower for kw in action_keywords):
            return UserIntent.DECIDE
        
        # Default to EXPLAIN (safest - no agent call)
        return UserIntent.EXPLAIN
    
    @classmethod
    def classify_intent(
        cls, 
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> UserIntent:
        """
        Classify user intent using LLM-first approach with rule-based fallback.
        
        Flow:
        1. Quick greeting check (no LLM needed)
        2. LLM classification (primary path)
        3. Fallback rules (only on error)
        """
        message_lower = user_message.lower().strip()
        context = context or {}
        
        # 1. Quick greeting check (no LLM needed)
        if any(re.search(p, message_lower) for p in cls.GREETING_PATTERNS):
            if len(message_lower.split()) <= 5:
                return UserIntent.STATUS
        
        # 2. LLM classification (primary path)
        try:
            # Use LLM to get two-level classification
            intent_result = cls.classify_intent_llm(user_message, context)
            # Convert UserGoal to UserIntent
            return cls._user_goal_to_intent(intent_result.user_goal)
        except Exception as e:
            logger.warning(f"LLM classification failed in classify_intent: {e}, using fallback")
        
        # 3. Fallback rules (only on error)
        return cls._classify_intent_rules_fallback(user_message, context)
    
    @classmethod
    def _is_followup_question(
        cls,
        message: str,
        conversation_history: List[Dict[str, str]],
        latest_agent_name: Optional[str]
    ) -> bool:
        """
        Check if message is a follow-up question about previous conversation.
        
        Follow-up indicators:
        - Pronouns referring to previous output ("it", "that", "this", "the requirements", "the draft")
        - Questions about something mentioned in conversation history
        - Questions with domain terms that match latest agent output
        """
        if not conversation_history and not latest_agent_name:
            return False
        
        message_lower = message.lower()
        
        # Check for pronouns/definite articles referring to something
        followup_indicators = [
            r'\b(it|that|this|these|those)\s+(is|are|was|were|has|have|does|do)',
            r'the\s+(requirements?|draft|rfx|strategy|suppliers?|signals?)',
            r'what\s+(requirements?|sections?|parts?)',
            r'which\s+(requirements?|sections?|parts?)',
            r'how\s+(complete|defined|many)'
        ]
        
        if any(re.search(p, message_lower) for p in followup_indicators):
            return True
        
        # Check if question contains terms related to latest agent
        if latest_agent_name:
            agent_keywords = {
                "RFX_DRAFT": ["requirements", "sections", "draft", "rfx", "rfp", "rfq", "rfi"],
                "SOURCING_SIGNAL": ["signals", "signal"],
                "SUPPLIER_SCORING": ["suppliers", "scoring", "score", "shortlist"],
                "NEGOTIATION_SUPPORT": ["negotiation", "leverage", "targets"],
                "CONTRACT_SUPPORT": ["contract", "terms", "compliance"],
                "IMPLEMENTATION": ["implementation", "checklist", "savings"]
            }
            
            keywords = agent_keywords.get(latest_agent_name, [])
            if any(kw in message_lower for kw in keywords):
                return True
        
        return False
    
    @classmethod
    def is_approval_attempt(cls, message: str) -> bool:
        """Check if message looks like an approval attempt."""
        message_lower = message.lower().strip()
        is_approval = any(re.search(p, message_lower) for p in cls.APPROVAL_PATTERNS)
        is_rejection = any(re.search(p, message_lower) for p in cls.REJECTION_PATTERNS)
        return is_approval or is_rejection
    
    @classmethod
    def get_allowed_agents(
        cls,
        intent: UserIntent,
        dtp_stage: str
    ) -> List[str]:
        """
        Get list of agents that can be called for this intent/stage combination.
        
        GOVERNANCE:
        - STATUS/EXPLAIN: No agent call (use cached data)
        - EXPLORE: May call agents for exploration
        - DECIDE: Full agent access with human approval
        """
        # Base agent access by stage
        stage_agents = {
            "DTP-01": ["Strategy"],
            "DTP-02": ["Strategy", "MarketIntelligence"],
            "DTP-03": ["SupplierEvaluation", "MarketIntelligence"],
            "DTP-04": ["NegotiationSupport", "SupplierEvaluation"],
            "DTP-05": ["ContractSupport"],
            "DTP-06": []  # Execution - no agents
        }
        
        available = stage_agents.get(dtp_stage, [])
        
        # STATUS and EXPLAIN don't run agents (use existing data)
        if intent in [UserIntent.STATUS, UserIntent.EXPLAIN]:
            return []  # No agents called
        
        elif intent == UserIntent.EXPLORE:
            # Can call agents for exploration (no state change)
            return available
        
        elif intent == UserIntent.DECIDE:
            # Full access (requires human approval)
            return available
        
        return []
    
    @classmethod
    def requires_human_approval(
        cls,
        intent: UserIntent,
        agent_name: Optional[str] = None
    ) -> bool:
        """
        Determine if human approval is required.
        """
        # Only DECIDE intent triggers approval requirement
        if intent == UserIntent.DECIDE:
            return True
        
        # Strategy and Negotiation always need approval
        if agent_name in ["Strategy", "NegotiationSupport"]:
            return True
        
        return False
    
    @classmethod
    def validate_intent_for_stage(
        cls,
        dtp_stage: str,
        intent: UserIntent
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if intent is allowed for current stage.
        
        Returns:
            (is_valid, blocked_reason)
        """
        # STATUS and EXPLAIN always allowed
        if intent in [UserIntent.STATUS, UserIntent.EXPLAIN]:
            return True, None
        
        # EXPLORE always allowed (doesn't change state)
        if intent == UserIntent.EXPLORE:
            return True, None
        
        # DECIDE validation by stage
        if intent == UserIntent.DECIDE:
            # DTP-06 is execution only
            if dtp_stage == "DTP-06":
                return False, "Case is in execution phase. No further decisions available."
            return True, None
        
        return True, None
    
    @classmethod
    def should_allow_retrieval(
        cls,
        intent: UserIntent,
        dtp_stage: str,
        requested_doc_types: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str]]:
        """Check if retrieval is allowed for this intent/stage."""
        stage_relevant_docs = {
            "DTP-01": ["Policy", "Market Report", "Contract"],
            "DTP-02": ["Policy", "Market Report", "Contract", "RFx"],
            "DTP-03": ["Performance Report", "Contract", "RFx"],
            "DTP-04": ["Performance Report", "Contract"],
            "DTP-05": ["Contract", "Policy"],
            "DTP-06": ["Contract"]
        }
        
        allowed_types = stage_relevant_docs.get(dtp_stage, [])
        
        if requested_doc_types:
            blocked_types = [t for t in requested_doc_types if t not in allowed_types]
            if blocked_types:
                return False, f"Document types {blocked_types} not relevant for stage {dtp_stage}"
        
        return True, None
    
    @classmethod
    def format_gating_explanation(
        cls,
        intent: UserIntent,
        dtp_stage: str,
        blocked_reason: str
    ) -> str:
        """Generate user-friendly explanation for gated actions."""
        explanations = {
            UserIntent.DECIDE: (
                f"Your request involves a decision that's not available at the current "
                f"{dtp_stage} stage. {blocked_reason}\n\n"
                f"To proceed, you may need to complete earlier stages first."
            ),
            UserIntent.EXPLORE: (
                f"While you can explore this scenario, please note: {blocked_reason}\n\n"
                f"This exploration won't affect your case state."
            )
        }
        
        return explanations.get(intent, blocked_reason)
    
    # =========================================================================
    # TWO-LEVEL INTENT CLASSIFICATION
    # =========================================================================
    
    # User goal patterns
    GOAL_PATTERNS = {
        UserGoal.TRACK: [
            r'status', r'progress', r'update\b', r'where are we', r'current',
            r'monitor', r'scan', r'signal', r'check status'
        ],
        UserGoal.UNDERSTAND: [
            r'what is', r'explain\b', r'why\b', r'how does', r'tell me',
            r'understand', r'reason', r'describe', r'clarify'
        ],
        UserGoal.CREATE: [
            r'create', r'draft', r'generate', r'build', r'make', r'prepare',
            r'score', r'evaluate', r'plan', r'template'
        ],
        UserGoal.CHECK: [
            r'check\b', r'validate', r'verify', r'compliant', r'review',
            r'audit', r'confirm'
        ],
        UserGoal.DECIDE: [
            r'decide', r'approve', r'select', r'choose', r'finalize',
            r'award', r'proceed', r'go ahead'
        ],
    }
    
    # Work type patterns
    WORK_PATTERNS = {
        WorkType.ARTIFACT: [
            r'draft', r'document', r'template', r'report', r'plan',
            r'checklist', r'scorecard', r'summary'
        ],
        WorkType.DATA: [
            r'data', r'metric', r'performance', r'history', r'record'
        ],
        WorkType.APPROVAL: [
            r'approve', r'decide', r'authorize', r'sign off'
        ],
        WorkType.COMPLIANCE: [
            r'compliant', r'policy', r'rule', r'regulation', r'valid'
        ],
        WorkType.VALUE: [
            r'saving', r'value', r'cost', r'roi', r'benefit', r'price'
        ],
    }
    
    @classmethod
    def classify_intent_two_level(
        cls,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        Classify user intent into two levels with context awareness.
        - user_goal: Primary intent (TRACK, UNDERSTAND, CREATE, CHECK, DECIDE)
        - work_type: Secondary work type (ARTIFACT, DATA, APPROVAL, COMPLIANCE, VALUE)
        """
        message_lower = user_message.lower().strip()
        context = context or {}
        has_existing_output = context.get("has_existing_output", False)
        dtp_stage = context.get("dtp_stage", "")
        
        # Determine user goal with context awareness
        user_goal = UserGoal.UNDERSTAND  # Default
        goal_confidence = 0.5
        
        # Special case patterns FIRST (highest priority)
        # CHECK patterns (validation/compliance) - check before action verbs
        if any(kw in message_lower for kw in ['check eligibility', 'validate', 'verify compliance', 
                                               'check compliant', 'check supplier', 'validate term']):
            user_goal = UserGoal.CHECK
            goal_confidence = 0.95
        # Composite action patterns (high confidence)
        elif any(kw in message_lower for kw in ['recommend a strategy', 'recommend strategy', 'suggest a strategy', 'recommend']):
            # Strategy recommendation requests - always CREATE (even if output exists, user wants new analysis)
            user_goal = UserGoal.CREATE
            goal_confidence = 0.95
        elif any(kw in message_lower for kw in ['score supplier', 'evaluate supplier', 'rank supplier']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.95
        elif any(kw in message_lower for kw in ['draft rfx', 'draft rfp', 'draft rfq', 'create rfx']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.95
        elif any(kw in message_lower for kw in ['scan signals', 'scan for signals', 'scan all signals']):
            user_goal = UserGoal.CREATE if not has_existing_output else UserGoal.TRACK
            goal_confidence = 0.95
        elif any(kw in message_lower for kw in ['negotiat', 'leverage', 'target term']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.9
        elif any(kw in message_lower for kw in ['extract term', 'key term', 'contract term']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.9
        elif any(kw in message_lower for kw in ['implement', 'rollout', 'checklist', 'kpi']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.9
        
        # Domain questions that imply analysis (if no output exists)
        # e.g., "Why are costs increasing?" -> should trigger analysis, not explanation
        elif not has_existing_output and '?' in user_message and any(kw in message_lower for kw in ['cost', 'spend', 'budget', 'increasing', 'rising', 'performance', 'score', 'signal', 'risk', 'trend']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.9
        else:
            # Check action verbs (before question words)
            action_keywords = ['scan', 'score', 'draft', 'support', 'extract', 'generate', 
                              'create', 'build', 'prepare', 'compare', 'define', 
                              'track', 'evaluate', 'analyze']
            # Note: 'check' and 'validate' excluded here - handled by CHECK patterns above
            
            has_action_verb = any(kw in message_lower for kw in action_keywords)
            
            # If action verb and no existing output, high confidence CREATE
            if has_action_verb and not has_existing_output:
                user_goal = UserGoal.CREATE
                goal_confidence = 0.95
            else:
                # Pattern matching with priority
                for goal, patterns in cls.GOAL_PATTERNS.items():
                    for pattern in patterns:
                        if re.search(pattern, message_lower):
                            user_goal = goal
                            goal_confidence = 0.85
                            break
                    if goal_confidence > 0.5:
                        break
        
        # Context-aware adjustments
        if has_existing_output and '?' in user_message:
            # Question about existing output -> UNDERSTAND
            if user_goal == UserGoal.CREATE and goal_confidence < 0.9:
                user_goal = UserGoal.UNDERSTAND
                goal_confidence = 0.8
        
        # Determine work type
        work_type = WorkType.DATA  # Default
        
        for wtype, patterns in cls.WORK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    work_type = wtype
                    break
        
        return IntentResult(
            user_goal=user_goal.value,
            work_type=work_type.value,
            confidence=goal_confidence,
            rationale=f"Classified from message patterns (context-aware)"
        )
    
    @classmethod
    def get_action_plan(
        cls,
        intent: IntentResult,
        dtp_stage: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ActionPlan:
        """
        Generate action plan from two-level intent.
        
        Returns which agent and tasks to execute.
        """
        from backend.tasks.planners import AgentPlaybook
        
        playbook = AgentPlaybook()
        user_goal = UserGoal(intent.user_goal)
        work_type = WorkType(intent.work_type)
        
        # Get appropriate agent
        agent_name = playbook.get_agent_for_intent(user_goal, work_type, dtp_stage)
        
        if not agent_name:
            # Log warning when routing returns None
            logger.warning(
                f"Agent routing returned None for user_goal={user_goal.value}, "
                f"work_type={work_type.value}, dtp_stage={dtp_stage}. Using stage default."
            )
            # Default based on stage and work_type
            # For CREATE+ARTIFACT, prefer RFx Draft agents
            if user_goal == UserGoal.CREATE and work_type == WorkType.ARTIFACT:
                if dtp_stage in ["DTP-01", "DTP-02", "DTP-03"]:
                    agent_name = AgentName.RFX_DRAFT
                elif dtp_stage == "DTP-04":
                    agent_name = AgentName.NEGOTIATION_SUPPORT
                elif dtp_stage == "DTP-05":
                    agent_name = AgentName.CONTRACT_SUPPORT
                elif dtp_stage == "DTP-06":
                    agent_name = AgentName.IMPLEMENTATION
            # For CREATE+DATA, prefer data analysis agents
            elif user_goal == UserGoal.CREATE and work_type == WorkType.DATA:
                if dtp_stage == "DTP-01":
                    agent_name = AgentName.SOURCING_SIGNAL
                elif dtp_stage in ["DTP-02", "DTP-03"]:
                    agent_name = AgentName.SUPPLIER_SCORING
                elif dtp_stage == "DTP-04":
                    agent_name = AgentName.NEGOTIATION_SUPPORT
                elif dtp_stage == "DTP-05":
                    agent_name = AgentName.CONTRACT_SUPPORT
                elif dtp_stage == "DTP-06":
                    agent_name = AgentName.IMPLEMENTATION
            # Fallback to stage defaults
            if not agent_name:
                stage_defaults = {
                    "DTP-01": AgentName.SOURCING_SIGNAL,
                    "DTP-02": AgentName.SUPPLIER_SCORING,
                    "DTP-03": AgentName.RFX_DRAFT,
                    "DTP-04": AgentName.NEGOTIATION_SUPPORT,
                    "DTP-05": AgentName.CONTRACT_SUPPORT,
                    "DTP-06": AgentName.IMPLEMENTATION,
                }
                agent_name = stage_defaults.get(dtp_stage, AgentName.SOURCING_SIGNAL)
                logger.debug(f"Using stage default agent: {agent_name.value} for stage {dtp_stage}")
        
        # Get tasks
        tasks = playbook.get_tasks_for_agent(agent_name, user_goal, work_type, dtp_stage)
        
        # Determine approval requirement
        approval_required = (
            user_goal == UserGoal.DECIDE or
            work_type == WorkType.APPROVAL or
            dtp_stage in ["DTP-04", "DTP-05"]
        )
        
        # UI mode
        ui_mode_map = {
            AgentName.SOURCING_SIGNAL: "signals",
            AgentName.SUPPLIER_SCORING: "scoring",
            AgentName.RFX_DRAFT: "rfx",
            AgentName.NEGOTIATION_SUPPORT: "negotiation",
            AgentName.CONTRACT_SUPPORT: "contract",
            AgentName.IMPLEMENTATION: "implementation",
        }
        
        return ActionPlan(
            agent_name=agent_name.value,
            tasks=tasks,
            approval_required=approval_required,
            ui_mode=ui_mode_map.get(agent_name, "default")
        )
    
    # =========================================================================
    # LLM-FIRST CLASSIFICATION
    # =========================================================================
    
    # LLM classification cache (in-memory, simple hash-based)
    _llm_cache: Dict[str, IntentResult] = {}
    
    @classmethod
    def _get_cache_key(cls, message: str, context: Dict[str, Any]) -> str:
        """Generate cache key from message and context (enhanced for better cache hits)."""
        # Include more context for better cache key generation
        conversation_history = context.get("conversation_history", [])
        conv_hash = ""
        if conversation_history:
            # Hash last 3 messages for context-aware caching
            last_messages = [msg.get("content", "")[:50] for msg in conversation_history[-3:]]
            conv_hash = hashlib.md5("|".join(last_messages).encode()).hexdigest()[:8]
        
        cache_data = {
            "message": message.lower().strip(),
            "dtp_stage": context.get("dtp_stage", ""),
            "has_output": context.get("has_existing_output", False),
            "latest_agent": context.get("latest_agent_name", ""),
            "conv_hash": conv_hash
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    @classmethod
    def classify_intent_llm(
        cls,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        Use LLM to classify intent with structured output and Pydantic validation.
        
        Returns structured IntentResult with confidence and rationale.
        """
        context = context or {}
        dtp_stage = context.get("dtp_stage", "DTP-01")
        has_output = context.get("has_existing_output", False)
        category_id = context.get("category_id", "")
        latest_agent_name = context.get("latest_agent_name", "")
        conversation_history = context.get("conversation_history", [])
        case_id = context.get("case_id", "")
        
        # Format conversation history for prompt (last 5-10 messages)
        conv_context = ""
        if conversation_history:
            conv_context = "\nRecent conversation:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages for better context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Truncate long messages but keep more context
                if len(content) > 150:
                    content = content[:150] + "..."
                conv_context += f"- {role}: {content}\n"
        
        # Check cache first
        cache_key = cls._get_cache_key(user_message, context)
        if cache_key in cls._llm_cache:
            logger.debug(f"Cache hit for classification: {cache_key[:8]}...")
            return cls._llm_cache[cache_key]
        
        # Build LLM prompt with few-shot examples
        prompt = f"""Classify this user message in a procurement sourcing context.

Message: "{user_message}"

Context:
- DTP Stage: {dtp_stage}
- Has Existing Output: {has_output}
- Category: {category_id or "N/A"}
- Latest Agent: {latest_agent_name or "N/A"}{conv_context}

Examples:
1. "What RFI requirements should I define first to proceed with this case?" (has_output=True)
   → {{"user_goal": "UNDERSTAND", "work_type": "ARTIFACT", "confidence": 0.9, "rationale": "Question about existing RFI requirements - asking what's missing, not requesting new work"}}

2. "Draft RFx" (has_output=False)
   → {{"user_goal": "CREATE", "work_type": "ARTIFACT", "confidence": 0.95, "rationale": "Direct action request to create RFx document"}}

3. "How to complete it?" (has_output=True, latest_agent="RFX_DRAFT")
   → {{"user_goal": "UNDERSTAND", "work_type": "ARTIFACT", "confidence": 0.9, "rationale": "Follow-up question about completing existing draft - asking for guidance, not creating new"}}

4. "Scan signals" (has_output=False)
   → {{"user_goal": "CREATE", "work_type": "DATA", "confidence": 0.95, "rationale": "Action request to scan and analyze sourcing signals"}}

5. "Explain the scoring" (has_output=True, latest_agent="SUPPLIER_SCORING")
   → {{"user_goal": "UNDERSTAND", "work_type": "DATA", "confidence": 0.95, "rationale": "Question about existing scoring results - requesting explanation"}}

6. "What signals do we have?" (has_output=True)
   → {{"user_goal": "TRACK", "work_type": "DATA", "confidence": 0.9, "rationale": "Question asking for status/inventory of existing signals"}}

7. "Score suppliers based on quality, delivery, and cost" (has_output=False)
   → {{"user_goal": "CREATE", "work_type": "DATA", "confidence": 0.95, "rationale": "Action request to evaluate and score suppliers"}}

8. "Check supplier eligibility" (has_output=False)
   → {{"user_goal": "CHECK", "work_type": "COMPLIANCE", "confidence": 0.95, "rationale": "Validation request to check compliance/eligibility"}}

9. "Recommend a strategy" (has_output=False or True)
   → {{"user_goal": "CREATE", "work_type": "DATA", "confidence": 0.95, "rationale": "Command to analyze and generate strategy recommendation - action request, not a question"}}

10. "Why are costs increasing?" (has_output=False)
   → {{"user_goal": "CREATE", "work_type": "DATA", "confidence": 0.95, "rationale": "Question about domain metrics with no existing analysis - implies request for analysis"}}

11. "Recommend a strategy for this case" (has_output=False or True)
   → {{"user_goal": "CREATE", "work_type": "DATA", "confidence": 0.95, "rationale": "Command to analyze and generate strategy recommendation - action request, not a question"}}

Classification Guidelines:
- COMMANDS (not questions) with action verbs → CREATE (e.g., "Recommend a strategy", "Draft RFx", "Scan signals")
- QUESTIONS (starts with what/which/how/when/where/why or contains "should I") about requirements/data/sections when output exists → UNDERSTAND
- "How to X" questions → UNDERSTAND (asking for guidance, not creating)
- Action verbs in QUESTIONS with existing output → UNDERSTAND (asking about the action, not requesting it)
- Follow-up questions (check conversation history) → UNDERSTAND
- Key distinction: COMMANDS (imperative) = CREATE, QUESTIONS (interrogative) = UNDERSTAND/TRACK

User Goals:
- TRACK: Monitor/check status, scan data, get updates, inventory queries
- UNDERSTAND: Explain existing recommendations/data, clarify rationale, follow-up questions about what was generated
- CREATE: Generate artifacts (draft RFx, score suppliers, create plans) - only when no output or explicit new request
- CHECK: Validate/comply with policy, verify eligibility
- DECIDE: Make decision requiring approval, select option

Work Types:
- ARTIFACT: Generate work products (documents, reports, plans)
- DATA: Retrieve/analyze data, metrics, performance
- APPROVAL: Human decision required
- COMPLIANCE: Policy/rule check, validation
- VALUE: Savings/ROI analysis, cost analysis

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
    "user_goal": "TRACK" | "UNDERSTAND" | "CREATE" | "CHECK" | "DECIDE",
    "work_type": "ARTIFACT" | "DATA" | "APPROVAL" | "COMPLIANCE" | "VALUE",
    "confidence": 0.0-1.0,
    "rationale": "Brief explanation of classification"
}}"""

        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Fallback to rule-based if no API key
                logger.warning("No OpenAI API key found, using rule-based fallback")
                return cls.classify_intent_two_level(user_message, context)
            
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=200,
                api_key=api_key,
                model_kwargs={"response_format": {"type": "json_object"}}  # JSON mode
            )
            
            response = llm.invoke(prompt)
            content = response.content.strip()
            
            # Parse JSON (should be clean JSON in JSON mode)
            try:
                result_data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: try to extract JSON if wrapped
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                result_data = json.loads(json_str)
            
            # Validate with Pydantic schema
            try:
                validated = IntentClassificationSchema(**result_data)
                user_goal_str = validated.user_goal
                work_type_str = validated.work_type
                confidence = validated.confidence
                rationale = validated.rationale
            except Exception as schema_error:
                logger.warning(f"Schema validation failed, using direct parsing: {schema_error}")
                # Fallback to direct parsing
                user_goal_str = result_data.get("user_goal", "UNDERSTAND")
                work_type_str = result_data.get("work_type", "DATA")
                confidence = float(result_data.get("confidence", 0.8))
                rationale = result_data.get("rationale", "LLM classification")
            
            # Validate enum values
            try:
                user_goal = UserGoal(user_goal_str)
            except ValueError:
                logger.warning(f"Invalid user_goal: {user_goal_str}, defaulting to UNDERSTAND")
                user_goal = UserGoal.UNDERSTAND
            
            try:
                work_type = WorkType(work_type_str)
            except ValueError:
                logger.warning(f"Invalid work_type: {work_type_str}, defaulting to DATA")
                work_type = WorkType.DATA
            
            result = IntentResult(
                user_goal=user_goal.value,
                work_type=work_type.value,
                confidence=min(1.0, max(0.0, confidence)),
                rationale=f"LLM: {rationale}"
            )
            
            # Cache result
            cls._llm_cache[cache_key] = result
            # Limit cache size (keep last 500 entries with LRU-like eviction)
            if len(cls._llm_cache) > 500:
                # Remove oldest (simple: remove first item)
                oldest_key = next(iter(cls._llm_cache))
                del cls._llm_cache[oldest_key]
            
            logger.debug(f"LLM classification: {user_goal.value}/{work_type.value} (confidence: {confidence:.2f})")
            return result
            
        except Exception as e:
            # Fallback to rule-based on error
            logger.warning(f"LLM classification error: {e}, falling back to rules")
            return cls.classify_intent_two_level(user_message, context)
    
    @classmethod
    def classify_intent_hybrid(
        cls,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        LLM-first classification for two-level intent (UserGoal + WorkType).
        
        Flow:
        1. LLM classification (primary path)
        2. Fallback to rule-based (only on error)
        """
        context = context or {}
        
        # Primary path: Use LLM classification
        try:
            return cls.classify_intent_llm(user_message, context)
        except Exception as e:
            logger.warning(f"LLM classification failed in classify_intent_hybrid: {e}, using rule fallback")
            # Fallback to rule-based on error
            return cls.classify_intent_two_level(user_message, context)

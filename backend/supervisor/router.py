"""
Intent classification and routing for the Supervisor.

TWO-LEVEL CLASSIFICATION:
- Primary: User Goal (TRACK, UNDERSTAND, CREATE, CHECK, DECIDE)
- Secondary: Work Type (ARTIFACT, DATA, APPROVAL, COMPLIANCE, VALUE)

HYBRID CLASSIFICATION:
- Rule-based for clear cases (fast, deterministic)
- LLM-based for ambiguous cases (accurate, context-aware)
- Caching for performance

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
from pydantic import BaseModel

from shared.constants import UserIntent, UserGoal, WorkType, AgentName
from shared.schemas import IntentResult, ActionPlan


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
    def classify_intent(
        cls, 
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> UserIntent:
        """
        Classify user intent from message with optional context.
        
        Priority:
        1. STATUS - Quick status checks
        2. DECIDE - Explicit action requests
        3. EXPLORE - Hypotheticals and alternatives
        4. EXPLAIN - Understanding existing info (default)
        """
        message_lower = user_message.lower().strip()
        context = context or {}
        has_existing_output = context.get("has_existing_output", False)
        dtp_stage = context.get("dtp_stage", "")
        latest_agent_name = context.get("latest_agent_name")
        conversation_history = context.get("conversation_history", [])
        
        # NEW: Check if this is a follow-up question about previous conversation
        is_followup = cls._is_followup_question(user_message, conversation_history, latest_agent_name)
        
        # Check for greetings (map to STATUS for friendly response)
        if any(re.search(p, message_lower) for p in cls.GREETING_PATTERNS):
            # Short greetings default to status
            if len(message_lower.split()) <= 5:
                return UserIntent.STATUS
        
        # Check for STATUS intent
        if any(re.search(p, message_lower) for p in cls.STATUS_PATTERNS):
            return UserIntent.STATUS
        
        # NEW: If follow-up question and has output, likely EXPLAIN
        if is_followup and has_existing_output:
            return UserIntent.EXPLAIN
        
        # Check for explicit DECIDE patterns (ACTION VERBS FIRST - important!)
        # This catches "scan signals", "score suppliers", etc. before EXPLAIN patterns
        action_verb_detected = any(re.search(p, message_lower) for p in cls.DECIDE_PATTERNS)
        
        if action_verb_detected:
            # Context-aware: If no existing output and action verb, it's CREATE/DECIDE
            if not has_existing_output:
                return UserIntent.DECIDE
            # If has output but action verb, could be re-running or new request
            # Check if it's a question about the action
            if '?' in user_message and any(kw in message_lower for kw in ['what', 'how', 'why', 'which']):
                # "What signals did you scan?" -> EXPLAIN
                return UserIntent.EXPLAIN
            # Otherwise, action verb = DECIDE
            return UserIntent.DECIDE
        
        # Check for EXPLORE patterns
        if any(re.search(p, message_lower) for p in cls.EXPLORE_PATTERNS):
            return UserIntent.EXPLORE
        
        # Check for EXPLAIN patterns (enhanced with domain-specific terms)
        if any(re.search(p, message_lower) for p in cls.EXPLAIN_PATTERNS):
            return UserIntent.EXPLAIN
        
        # NEW: Domain-specific EXPLAIN patterns (requirements, sections, etc.)
        if any(kw in message_lower for kw in ['requirements', 'requirement', 'not defined', 'not fully defined', 
                                                'missing', 'undefined', 'incomplete', 'what sections', 
                                                'which sections', 'what requirements']):
            if has_existing_output:
                return UserIntent.EXPLAIN
        
        # Check if it's a question about existing recommendation
        if '?' in user_message:
            # Context-aware: If no output exists, question might be asking to create
            if not has_existing_output and any(kw in message_lower for kw in ['can you', 'could you', 'will you']):
                # "Can you scan signals?" -> DECIDE (action request)
                return UserIntent.DECIDE
            # Otherwise, questions default to EXPLAIN (especially with conversation history)
            if has_existing_output or conversation_history:
                return UserIntent.EXPLAIN
            return UserIntent.EXPLAIN
        
        # Short messages without clear intent -> STATUS
        if len(message_lower.split()) <= 3:
            return UserIntent.STATUS
        
        # Default: If action verb detected anywhere, prefer DECIDE over EXPLAIN
        # This prevents action requests from defaulting to EXPLAIN
        if any(kw in message_lower for kw in ['scan', 'score', 'draft', 'generate', 'create', 'build']):
            return UserIntent.DECIDE
        
        # Default to EXPLAIN (safest - no agent call needed)
        return UserIntent.EXPLAIN
    
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
            # Default based on stage
            stage_defaults = {
                "DTP-01": AgentName.SOURCING_SIGNAL,
                "DTP-02": AgentName.SUPPLIER_SCORING,
                "DTP-03": AgentName.RFX_DRAFT,
                "DTP-04": AgentName.NEGOTIATION_SUPPORT,
                "DTP-05": AgentName.CONTRACT_SUPPORT,
                "DTP-06": AgentName.IMPLEMENTATION,
            }
            agent_name = stage_defaults.get(dtp_stage, AgentName.SOURCING_SIGNAL)
        
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
    # HYBRID CLASSIFICATION: RULE + LLM
    # =========================================================================
    
    # LLM classification cache (in-memory, simple hash-based)
    _llm_cache: Dict[str, IntentResult] = {}
    
    @classmethod
    def _get_cache_key(cls, message: str, context: Dict[str, Any]) -> str:
        """Generate cache key from message and context."""
        cache_data = {
            "message": message.lower().strip(),
            "dtp_stage": context.get("dtp_stage", ""),
            "has_output": context.get("has_existing_output", False)
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
        Use LLM to classify intent for ambiguous cases.
        
        Returns structured IntentResult with confidence and rationale.
        """
        context = context or {}
        dtp_stage = context.get("dtp_stage", "DTP-01")
        has_output = context.get("has_existing_output", False)
        category_id = context.get("category_id", "")
        latest_agent_name = context.get("latest_agent_name", "")
        conversation_history = context.get("conversation_history", [])
        
        # Format conversation history for prompt
        conv_context = ""
        if conversation_history:
            conv_context = "\nRecent conversation:\n"
            for msg in conversation_history[-2:]:  # Last 2 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")[:100]  # Truncate for brevity
                conv_context += f"- {role}: {content}\n"
        
        # Check cache first
        cache_key = cls._get_cache_key(user_message, context)
        if cache_key in cls._llm_cache:
            return cls._llm_cache[cache_key]
        
        # Build LLM prompt
        prompt = f"""Classify this user message in a procurement sourcing context.

Message: "{user_message}"

Context:
- DTP Stage: {dtp_stage}
- Has Existing Output: {has_output}
- Category: {category_id or "N/A"}
- Latest Agent: {latest_agent_name or "N/A"}{conv_context}

Classification Guidelines:
- If user is asking about something already generated/mentioned → UNDERSTAND (EXPLAIN)
- If user is requesting new work/analysis → CREATE or DECIDE
- If user is checking status/progress → TRACK
- If user is exploring alternatives → EXPLORE
- If user mentions "requirements", "sections", "not defined" and has output → UNDERSTAND
- Consider conversation history: follow-up questions are usually UNDERSTAND

User Goals:
- TRACK: Monitor/check status, scan data, get updates
- UNDERSTAND: Explain existing recommendations/data, clarify rationale (use for follow-up questions)
- CREATE: Generate artifacts (draft RFx, score suppliers, create plans)
- CHECK: Validate/comply with policy, verify eligibility
- DECIDE: Make decision requiring approval, select option

Work Types:
- ARTIFACT: Generate work products (documents, reports, plans)
- DATA: Retrieve/analyze data, metrics, performance
- APPROVAL: Human decision required
- COMPLIANCE: Policy/rule check, validation
- VALUE: Savings/ROI analysis, cost analysis

Return ONLY valid JSON in this exact format:
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
                return cls.classify_intent_two_level(user_message, context)
            
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=200,
                api_key=api_key
            )
            
            response = llm.invoke(prompt)
            content = response.content.strip()
            
            # Extract JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            result_data = json.loads(json_str)
            
            # Validate and create IntentResult
            user_goal = UserGoal(result_data.get("user_goal", "UNDERSTAND"))
            work_type = WorkType(result_data.get("work_type", "DATA"))
            confidence = float(result_data.get("confidence", 0.8))
            rationale = result_data.get("rationale", "LLM classification")
            
            result = IntentResult(
                user_goal=user_goal.value,
                work_type=work_type.value,
                confidence=min(1.0, max(0.0, confidence)),
                rationale=f"LLM: {rationale}"
            )
            
            # Cache result
            cls._llm_cache[cache_key] = result
            # Limit cache size (keep last 100)
            if len(cls._llm_cache) > 100:
                # Remove oldest (simple: remove first item)
                oldest_key = next(iter(cls._llm_cache))
                del cls._llm_cache[oldest_key]
            
            return result
            
        except Exception as e:
            # Fallback to rule-based on error
            print(f"LLM classification error: {e}, falling back to rules")
            return cls.classify_intent_two_level(user_message, context)
    
    @classmethod
    def classify_intent_hybrid(
        cls,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        Hybrid classification: Rules for clear cases, LLM for ambiguous.
        
        Flow:
        1. Try rule-based classification
        2. If confidence < 0.85, use LLM
        3. Merge results with confidence weighting
        """
        context = context or {}
        
        # Step 1: Rule-based classification
        rule_result = cls.classify_intent_two_level(user_message, context)
        
        # Step 2: Check if we need LLM
        if rule_result.confidence >= 0.85:
            # High confidence rule result - use it
            return rule_result
        
        # Step 3: Use LLM for ambiguous cases
        llm_result = cls.classify_intent_llm(user_message, context)
        
        # Step 4: Merge results (prefer LLM if rule confidence is low)
        if rule_result.confidence < 0.7:
            # Very low rule confidence - trust LLM more
            return llm_result
        else:
            # Medium rule confidence - use weighted average
            # If LLM confidence is higher, use LLM
            if llm_result.confidence > rule_result.confidence:
                return llm_result
            else:
                # Keep rule result but note LLM was consulted
                rule_result.rationale += f" (LLM confirmed: {llm_result.user_goal})"
                return rule_result

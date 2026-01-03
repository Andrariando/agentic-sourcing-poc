"""
Intent classification and routing for the Supervisor.

TWO-LEVEL CLASSIFICATION:
- Primary: User Goal (TRACK, UNDERSTAND, CREATE, CHECK, DECIDE)
- Secondary: Work Type (ARTIFACT, DATA, APPROVAL, COMPLIANCE, VALUE)

CONVERSATIONAL DESIGN:
- Detect greetings and simple responses
- STATUS for case updates
- EXPLAIN for understanding recommendations
- EXPLORE for alternatives
- DECIDE only for explicit action requests
"""
import re
from typing import Optional, Dict, Any, List
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
    
    # Decide patterns (explicit action requests)
    DECIDE_PATTERNS = [
        # Action verbs
        r'\brun\b', r'\banalyze\b', r'\bevaluate\b', r'\brecommend\b',
        r'\bexecute\b', r'\bstart\b', r'\bbegin\b', r'\blaunch\b',
        r'\binitiate\b', r'\bfinalize\b', r'\bselect\b', r'\bchoose\b',
        # Explicit requests
        r'give me a (strategy|recommendation|plan)',
        r'create a (strategy|recommendation|plan)',
        r'what (should|do) (we|i) do',
        r'suggest a (strategy|approach|plan)',
        r'(need|want) (a )?(strategy|recommendation|analysis)'
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
    def classify_intent(cls, user_message: str) -> UserIntent:
        """
        Classify user intent from message.
        
        Priority:
        1. STATUS - Quick status checks
        2. DECIDE - Explicit action requests
        3. EXPLORE - Hypotheticals and alternatives
        4. EXPLAIN - Understanding existing info (default)
        """
        message_lower = user_message.lower().strip()
        
        # Check for greetings (map to STATUS for friendly response)
        if any(re.search(p, message_lower) for p in cls.GREETING_PATTERNS):
            # Short greetings default to status
            if len(message_lower.split()) <= 5:
                return UserIntent.STATUS
        
        # Check for STATUS intent
        if any(re.search(p, message_lower) for p in cls.STATUS_PATTERNS):
            return UserIntent.STATUS
        
        # Check for explicit DECIDE patterns
        if any(re.search(p, message_lower) for p in cls.DECIDE_PATTERNS):
            return UserIntent.DECIDE
        
        # Check for EXPLORE patterns
        if any(re.search(p, message_lower) for p in cls.EXPLORE_PATTERNS):
            return UserIntent.EXPLORE
        
        # Check for EXPLAIN patterns
        if any(re.search(p, message_lower) for p in cls.EXPLAIN_PATTERNS):
            return UserIntent.EXPLAIN
        
        # Check if it's a question about existing recommendation
        if '?' in user_message:
            # Questions default to EXPLAIN
            return UserIntent.EXPLAIN
        
        # Short messages without clear intent -> STATUS
        if len(message_lower.split()) <= 3:
            return UserIntent.STATUS
        
        # Default to EXPLAIN (safest - no agent call needed)
        return UserIntent.EXPLAIN
    
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
        Classify user intent into two levels:
        - user_goal: Primary intent (TRACK, UNDERSTAND, CREATE, CHECK, DECIDE)
        - work_type: Secondary work type (ARTIFACT, DATA, APPROVAL, COMPLIANCE, VALUE)
        """
        message_lower = user_message.lower().strip()
        context = context or {}
        
        # Determine user goal
        user_goal = UserGoal.UNDERSTAND  # Default
        goal_confidence = 0.5
        
        for goal, patterns in cls.GOAL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    user_goal = goal
                    goal_confidence = 0.85
                    break
            if goal_confidence > 0.5:
                break
        
        # Special case patterns
        if any(kw in message_lower for kw in ['score supplier', 'evaluate supplier', 'rank supplier']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.9
        elif any(kw in message_lower for kw in ['draft rfx', 'draft rfp', 'draft rfq', 'create rfx']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.9
        elif any(kw in message_lower for kw in ['negotiat', 'leverage', 'target term']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.85
        elif any(kw in message_lower for kw in ['extract term', 'key term', 'contract term']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.85
        elif any(kw in message_lower for kw in ['implement', 'rollout', 'checklist', 'kpi']):
            user_goal = UserGoal.CREATE
            goal_confidence = 0.85
        
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
            rationale=f"Classified from message patterns"
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

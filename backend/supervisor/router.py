"""
Intent classification and routing for the Supervisor.

CONVERSATIONAL DESIGN:
- Detect greetings and simple responses
- STATUS for case updates
- EXPLAIN for understanding recommendations
- EXPLORE for alternatives
- DECIDE only for explicit action requests
"""
import re
from typing import Optional, Dict, Any, List
from shared.constants import UserIntent


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

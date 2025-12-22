"""
Intent classification and routing for the Supervisor.
"""
from typing import Optional, Dict, Any, List
from shared.constants import UserIntent


class IntentRouter:
    """
    Classifies user intent and determines routing.
    
    Intent types:
    - EXPLAIN: User wants explanation/information (read-only)
    - EXPLORE: User wants to explore alternatives (no state change)
    - DECIDE: User wants to make a decision (requires approval)
    - STATUS: User wants status update (read-only)
    """
    
    # Keywords for intent classification
    EXPLAIN_KEYWORDS = [
        "what is", "explain", "describe", "tell me about", "how does",
        "why", "what does", "meaning", "definition", "clarify",
        "help me understand", "can you explain", "what's the"
    ]
    
    EXPLORE_KEYWORDS = [
        "what if", "alternative", "options", "could we", "would it be possible",
        "explore", "consider", "compare", "other", "different",
        "scenario", "hypothetical", "suppose", "imagine"
    ]
    
    DECIDE_KEYWORDS = [
        "approve", "reject", "proceed", "execute", "start", "begin",
        "launch", "initiate", "confirm", "finalize", "award",
        "select", "choose", "decide", "go ahead", "let's do"
    ]
    
    STATUS_KEYWORDS = [
        "status", "progress", "update", "where are we", "current state",
        "what's happening", "how far", "timeline", "next step"
    ]
    
    ACTION_KEYWORDS = [
        "run", "analyze", "evaluate", "recommend", "strategy",
        "supplier", "negotiation", "market scan", "rfx"
    ]
    
    @classmethod
    def classify_intent(cls, user_message: str) -> UserIntent:
        """
        Classify user intent from message.
        
        Priority:
        1. DECIDE (highest - has action implications)
        2. STATUS 
        3. EXPLORE
        4. EXPLAIN (default if unclear)
        """
        message_lower = user_message.lower()
        
        # Check for DECIDE intent first (highest priority)
        for keyword in cls.DECIDE_KEYWORDS:
            if keyword in message_lower:
                return UserIntent.DECIDE
        
        # Check for STATUS intent
        for keyword in cls.STATUS_KEYWORDS:
            if keyword in message_lower:
                return UserIntent.STATUS
        
        # Check for EXPLORE intent
        for keyword in cls.EXPLORE_KEYWORDS:
            if keyword in message_lower:
                return UserIntent.EXPLORE
        
        # Check for action-oriented but non-decision messages
        has_action = any(kw in message_lower for kw in cls.ACTION_KEYWORDS)
        has_question = "?" in user_message or any(
            message_lower.startswith(q) for q in ["what", "how", "why", "can", "should"]
        )
        
        if has_action and has_question:
            # Asking about an action = EXPLORE
            return UserIntent.EXPLORE
        elif has_action:
            # Requesting an action = DECIDE
            return UserIntent.DECIDE
        
        # Check for EXPLAIN intent
        for keyword in cls.EXPLAIN_KEYWORDS:
            if keyword in message_lower:
                return UserIntent.EXPLAIN
        
        # Default to EXPLAIN for safety (read-only)
        return UserIntent.EXPLAIN
    
    @classmethod
    def get_allowed_agents(
        cls,
        intent: UserIntent,
        dtp_stage: str
    ) -> List[str]:
        """
        Get list of agents that can be called for this intent/stage combination.
        
        GOVERNANCE RULE:
        - EXPLAIN/STATUS: Information agents only
        - EXPLORE: Analysis agents, but no state changes
        - DECIDE: Full agent access with human approval required
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
        
        if intent in [UserIntent.EXPLAIN, UserIntent.STATUS]:
            # Read-only - can call any available agent for information
            return available
        
        elif intent == UserIntent.EXPLORE:
            # Can call agents but results are exploratory
            return available
        
        elif intent == UserIntent.DECIDE:
            # Full access but will require human approval
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
        
        Rules:
        - DECIDE intent always requires approval
        - Any output that would change DTP stage requires approval
        - High-impact decisions require approval
        """
        if intent == UserIntent.DECIDE:
            return True
        
        # Strategy recommendations always require approval
        if agent_name == "Strategy":
            return True
        
        # Negotiation plans require approval
        if agent_name == "NegotiationSupport":
            return True
        
        return False
    
    @classmethod
    def should_allow_retrieval(
        cls,
        intent: UserIntent,
        dtp_stage: str,
        requested_doc_types: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check if retrieval is allowed for this intent/stage.
        
        Returns:
            (is_allowed, reason_if_blocked)
        """
        # All intents can retrieve for their stage
        # But certain document types may be stage-gated
        
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
        """Generate user-friendly explanation for why an action is gated."""
        explanations = {
            UserIntent.DECIDE: (
                f"Your request involves a decision that's not available at the current "
                f"{dtp_stage} stage. {blocked_reason}\n\n"
                f"To proceed, you may need to complete earlier stages first, or "
                f"this type of action may not be applicable to your current case."
            ),
            UserIntent.EXPLORE: (
                f"While you can explore this scenario, please note: {blocked_reason}\n\n"
                f"This exploration won't affect your case state."
            )
        }
        
        return explanations.get(intent, blocked_reason)


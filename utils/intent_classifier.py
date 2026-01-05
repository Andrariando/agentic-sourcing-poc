"""
Intent Classifier - Rule-based classification of user intent.

Classifies user input as COLLABORATIVE or EXECUTION.
- COLLABORATIVE: sense-making, discussion, clarification (default when ambiguous)
- EXECUTION: run agents, produce recommendations, advance DTP

Design Principles:
- No LLM usage (fully deterministic)
- Default to COLLABORATIVE when ambiguous
- Transparent and auditable
"""
from typing import Literal, Tuple, List
from dataclasses import dataclass


@dataclass
class IntentClassification:
    """Result of intent classification."""
    intent: Literal["COLLABORATIVE", "EXECUTION"]
    confidence: float  # 0.0 - 1.0
    matched_patterns: List[str]
    reasoning: str


# Execution intent patterns - explicit action requests
EXECUTION_PATTERNS = [
    # Direct action requests
    "proceed",
    "go ahead",
    "run the analysis",
    "run analysis",
    "make a recommendation",
    "recommend",
    "give me a recommendation",
    "execute",
    "start the process",
    "let's do it",
    "do it",
    "yes, proceed",
    "yes proceed",
    "approve",
    "i approve",
    "confirmed",
    "confirm",
    "move forward",
    "let's move forward",
    "next step",
    "advance",
    "submit",
    "finalize",
    "complete",
    "run rfx",
    "start rfx",
    "initiate rfx",
    "begin negotiation",
    "start negotiation",
    "create the plan",
    "generate the plan",
    "evaluate suppliers",
    "score suppliers",
    "rank suppliers",
    "make the decision",
    "decide",
    "select",
    "choose",
    "award",
    "sign off",
    "close the case",
    "implement",
    "roll out",
    # Affirmative responses to execution prompts
    "yes",
    "yes please",
    "go for it",
    "sounds good, proceed",
    "that works, proceed",
    "ok proceed",
    "okay proceed",
    "alright proceed",
    "sure proceed",
    "please proceed",
    "i'm ready",
    "ready to proceed",
    "let's execute",
]

# Collaborative intent patterns - discussion and exploration
COLLABORATIVE_PATTERNS = [
    # Questions and exploration
    "what are the options",
    "what options do we have",
    "what are my options",
    "help me think",
    "help me understand",
    "walk me through",
    "explain",
    "can you explain",
    "what does this mean",
    "what are the risks",
    "what are the tradeoffs",
    "trade-offs",
    "tradeoffs",
    "pros and cons",
    "advantages and disadvantages",
    "what should i consider",
    "what factors",
    "how should i think about",
    "what matters here",
    "what's important",
    "tell me more",
    "more details",
    "elaborate",
    "clarify",
    "i'm not sure",
    "i don't know",
    "uncertain",
    "confused",
    "need to think",
    "let me think",
    "give me a moment",
    "wait",
    "hold on",
    "pause",
    "stop",
    "not yet",
    "before we proceed",
    "before proceeding",
    "one question",
    "quick question",
    "can i ask",
    "what if",
    "how about",
    "alternatively",
    "another option",
    "other options",
    "different approach",
    "concerns",
    "worried about",
    "hesitant",
    "implications",
    "impact",
    "consequences",
    "downstream effects",
    "what happens if",
    "scenario",
    "compare",
    "comparison",
    "versus",
    "vs",
    "difference between",
    "which is better",
    "what's the difference",
    "why would we",
    "why should we",
    "why not",
    "is it possible",
    "could we",
    "can we",
    "should we",
    "might we",
    # Contextual exploration
    "background",
    "context",
    "history",
    "previous",
    "last time",
    "remind me",
    "what did we",
    "where were we",
    "status",
    "update me",
    "catch me up",
    "summary",
    "summarize",
    "overview",
]

# Ambiguous patterns that default to COLLABORATIVE
AMBIGUOUS_PATTERNS = [
    "what should we do",
    "what do you think",
    "what's your recommendation",
    "what would you suggest",
    "thoughts",
    "any thoughts",
    "ideas",
    "suggestions",
    "advice",
    "guidance",
    "input",
    "feedback",
    "opinion",
    "view",
    "perspective",
]


def classify_intent(user_input: str) -> IntentClassification:
    """
    Classify user intent as COLLABORATIVE or EXECUTION.
    
    Rules:
    1. Check for EXECUTION patterns first (explicit action requests)
    2. Check for COLLABORATIVE patterns (discussion, exploration)
    3. Check for AMBIGUOUS patterns (default to COLLABORATIVE)
    4. Default to COLLABORATIVE when no patterns match
    
    Returns IntentClassification with intent, confidence, and reasoning.
    """
    text = user_input.lower().strip()
    matched_execution = []
    matched_collaborative = []
    matched_ambiguous = []
    
    # Check execution patterns
    for pattern in EXECUTION_PATTERNS:
        if pattern in text:
            matched_execution.append(pattern)
    
    # Check collaborative patterns
    for pattern in COLLABORATIVE_PATTERNS:
        if pattern in text:
            matched_collaborative.append(pattern)
    
    # Check ambiguous patterns
    for pattern in AMBIGUOUS_PATTERNS:
        if pattern in text:
            matched_ambiguous.append(pattern)
    
    # Decision logic
    # Rule 1: If ONLY execution patterns matched (no collaborative), it's EXECUTION
    if matched_execution and not matched_collaborative and not matched_ambiguous:
        return IntentClassification(
            intent="EXECUTION",
            confidence=0.9,
            matched_patterns=matched_execution,
            reasoning=f"Matched execution patterns: {matched_execution}"
        )
    
    # Rule 2: If collaborative patterns matched, it's COLLABORATIVE
    if matched_collaborative:
        return IntentClassification(
            intent="COLLABORATIVE",
            confidence=0.85,
            matched_patterns=matched_collaborative,
            reasoning=f"Matched collaborative patterns: {matched_collaborative}"
        )
    
    # Rule 3: If ambiguous patterns matched, default to COLLABORATIVE
    if matched_ambiguous:
        return IntentClassification(
            intent="COLLABORATIVE",
            confidence=0.7,
            matched_patterns=matched_ambiguous,
            reasoning=f"Matched ambiguous patterns (defaulting to collaborative): {matched_ambiguous}"
        )
    
    # Rule 4: If execution and collaborative both matched, prefer COLLABORATIVE
    # (user may be asking about execution, not requesting it)
    if matched_execution and (matched_collaborative or matched_ambiguous):
        return IntentClassification(
            intent="COLLABORATIVE",
            confidence=0.6,
            matched_patterns=matched_collaborative + matched_ambiguous,
            reasoning=f"Mixed patterns detected - defaulting to collaborative for safety"
        )
    
    # Rule 5: Short affirmative responses in context of prior execution prompt
    # These would need context, but for safety default to COLLABORATIVE
    if len(text.split()) <= 3 and text in ["ok", "okay", "sure", "yes", "yep", "yeah", "alright"]:
        # Short affirmatives are ambiguous - might be agreement or acknowledgment
        # Default to COLLABORATIVE unless explicitly paired with "proceed"
        return IntentClassification(
            intent="COLLABORATIVE",
            confidence=0.5,
            matched_patterns=[],
            reasoning="Short affirmative response - ambiguous, defaulting to collaborative"
        )
    
    # Rule 6: Default to COLLABORATIVE when no patterns match
    return IntentClassification(
        intent="COLLABORATIVE",
        confidence=0.5,
        matched_patterns=[],
        reasoning="No clear patterns matched - defaulting to collaborative"
    )


def is_mid_stage_interruption(user_input: str, current_state: str = "executing") -> bool:
    """
    Detect if user is interrupting mid-execution with uncertainty.
    
    Returns True if user seems to be pausing or questioning mid-process.
    """
    interruption_patterns = [
        "wait",
        "hold on",
        "stop",
        "pause",
        "actually",
        "on second thought",
        "i changed my mind",
        "let me reconsider",
        "not so fast",
        "before we continue",
        "one moment",
        "hang on",
        "let's step back",
        "step back",
        "reconsider",
        "rethink",
    ]
    
    text = user_input.lower().strip()
    for pattern in interruption_patterns:
        if pattern in text:
            return True
    return False


def get_execution_confirmation_needed(user_input: str) -> bool:
    """
    Check if execution intent is clear enough or needs confirmation.
    
    Returns True if we should ask for explicit confirmation before executing.
    """
    classification = classify_intent(user_input)
    
    # If confidence is high for EXECUTION, no confirmation needed
    if classification.intent == "EXECUTION" and classification.confidence >= 0.85:
        return False
    
    # If it's EXECUTION but lower confidence, ask for confirmation
    if classification.intent == "EXECUTION" and classification.confidence < 0.85:
        return True
    
    # COLLABORATIVE intent never needs execution confirmation
    return False






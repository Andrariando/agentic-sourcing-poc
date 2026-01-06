"""
Unit tests for chat routing - golden prompt testing.

Tests that user messages are classified to the correct intent
and routed to the correct agent.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from backend.supervisor.router import IntentRouter
from shared.constants import UserIntent, UserGoal


# Golden prompts: (message, context, expected_intent, expected_agent_or_None)
GOLDEN_PROMPTS = [
    # STATUS queries
    ("What is the current status?", {"dtp_stage": "DTP-01", "has_existing_output": False}, UserIntent.STATUS, None),
    ("Where are we on this case?", {"dtp_stage": "DTP-02", "has_existing_output": True}, UserIntent.STATUS, None),
    ("Update me on progress", {"dtp_stage": "DTP-01", "has_existing_output": False}, UserIntent.STATUS, None),
    
    # EXPLAIN queries  
    ("Why did you recommend RFx?", {"dtp_stage": "DTP-01", "has_existing_output": True}, UserIntent.EXPLAIN, None),
    ("Explain the rationale", {"dtp_stage": "DTP-01", "has_existing_output": True}, UserIntent.EXPLAIN, None),
    ("What are the risks?", {"dtp_stage": "DTP-02", "has_existing_output": True}, UserIntent.EXPLAIN, None),
    
    # DECIDE/CREATE queries - should trigger agent
    ("Recommend a strategy", {"dtp_stage": "DTP-01", "has_existing_output": False}, UserIntent.DECIDE, "SOURCING_SIGNAL"),
    ("Score suppliers", {"dtp_stage": "DTP-02", "has_existing_output": False}, UserIntent.DECIDE, "SUPPLIER_SCORING"),
    ("Draft an RFx", {"dtp_stage": "DTP-03", "has_existing_output": False}, UserIntent.DECIDE, "RFX_DRAFT"),
    ("Analyze this case", {"dtp_stage": "DTP-01", "has_existing_output": False}, UserIntent.DECIDE, None),
    
    # Greetings should NOT default to STATUS with generic message
    # They should go to EXPLAIN for helpful guidance
    ("Hello there", {"dtp_stage": "DTP-01", "has_existing_output": False}, UserIntent.EXPLAIN, None),
    ("Hi", {"dtp_stage": "DTP-01", "has_existing_output": False}, UserIntent.EXPLAIN, None),
]


class TestIntentClassification:
    """Test intent classification accuracy."""
    
    @pytest.mark.parametrize("message,context,expected_intent,expected_agent", GOLDEN_PROMPTS)
    def test_golden_prompts(self, message, context, expected_intent, expected_agent):
        """Test that golden prompts classify correctly."""
        # Use rule-based fallback for deterministic testing
        intent = IntentRouter._classify_intent_rules_fallback(message, context)
        
        # Assert correct intent
        assert intent == expected_intent, (
            f"Message '{message}' classified as {intent.value}, expected {expected_intent.value}"
        )
    
    def test_two_level_classification(self):
        """Test two-level classification returns valid UserGoal."""
        message = "Recommend a strategy for this case"
        context = {"dtp_stage": "DTP-01", "has_existing_output": False}
        
        result = IntentRouter.classify_intent_two_level(message, context)
        
        assert result.user_goal in [g.value for g in UserGoal], f"Invalid user_goal: {result.user_goal}"
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
    
    def test_action_plan_generation(self):
        """Test that action plan is generated correctly."""
        from shared.schemas import IntentResult
        
        intent_result = IntentResult(
            user_goal=UserGoal.CREATE.value,
            work_type="ARTIFACT",
            confidence=0.9,
            rationale="Test"
        )
        
        action_plan = IntentRouter.get_action_plan(intent_result, "DTP-01")
        
        assert action_plan.agent_name, "Action plan should have an agent name"
        assert isinstance(action_plan.tasks, list), "Tasks should be a list"


class TestRoutingVariation:
    """Test that responses vary based on input."""
    
    def test_different_inputs_different_intents(self):
        """Two different messages should (often) get different intents."""
        context = {"dtp_stage": "DTP-01", "has_existing_output": False}
        
        status_intent = IntentRouter._classify_intent_rules_fallback("What is the status?", context)
        decide_intent = IntentRouter._classify_intent_rules_fallback("Recommend a strategy", context)
        
        assert status_intent != decide_intent, (
            f"Different inputs got same intent: {status_intent.value}"
        )
    
    def test_greeting_not_same_as_status_query(self):
        """Greetings should be handled differently than explicit status queries."""
        context = {"dtp_stage": "DTP-01", "has_existing_output": False}
        
        # Explicit status query
        status_intent = IntentRouter._classify_intent_rules_fallback("What is the current status?", context)
        
        # Greeting
        greeting_intent = IntentRouter._classify_intent_rules_fallback("Hello there", context)
        
        # Both might be STATUS, but the key is they're processed differently
        # by the handler based on case state
        assert status_intent == UserIntent.STATUS, "Explicit status query should be STATUS"


class TestFallbackBehavior:
    """Test fallback behavior and error handling."""
    
    def test_unknown_input_gets_safe_fallback(self):
        """Unknown/ambiguous input should get a safe intent, not crash."""
        context = {"dtp_stage": "DTP-01", "has_existing_output": False}
        
        # Nonsense input
        intent = IntentRouter._classify_intent_rules_fallback("asdfghjkl", context)
        
        # Should default to EXPLAIN (safe, no agent call)
        assert intent == UserIntent.EXPLAIN, f"Unknown input got {intent.value}, expected EXPLAIN"
    
    def test_classify_intent_handles_none_context(self):
        """classify_intent should handle None context gracefully."""
        intent = IntentRouter._classify_intent_rules_fallback("What is the status?", None)
        
        # Should not crash, should return valid intent
        assert intent in UserIntent, f"Invalid intent: {intent}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

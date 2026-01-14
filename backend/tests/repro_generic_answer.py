import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from agents.strategy_agent import StrategyAgent
from utils.schemas import CaseSummary

def test_strategy_agent_generic_answer():
    """
    Test if StrategyAgent ignores 'explore alternatives' and returns deterministic output.
    """
    agent = StrategyAgent(tier=1)
    
    # Mock data
    case_summary = CaseSummary(
        case_id="test_case_1",
        category_id="IT Software",
        contract_id="C-123",
        supplier_id="S-456",
        dtp_stage="DTP-01",
        trigger_source="User",
        status="In Progress"
    )
    
    # Run 1: Initial Recommendation
    print("\n--- Run 1: Initial ---")
    rec1, _, _, _, _ = agent.recommend_strategy(
        case_summary,
        user_intent="What should I do?",
        use_cache=False
    )
    print(f"Rec 1 Strategy: {rec1.recommended_strategy}")
    print(f"Rec 1 Rationale: {rec1.rationale[:1]}")
    
    # Run 2: Explore Alternatives
    print("\n--- Run 2: Explore Alternatives ---")
    rec2, _, _, _, _ = agent.recommend_strategy(
        case_summary,
        user_intent="Can you explore alternatives?",
        use_cache=False,
        conversation_history=[
            {"role": "assistant", "content": f"Recommended Strategy: {rec1.recommended_strategy}"}
        ]
    )
    print(f"Rec 2 Strategy: {rec2.recommended_strategy}")
    print(f"Rec 2 Rationale: {rec2.rationale[:1]}")
    
    # Assertion: If bug exists, Rec 2 will be identical to Rec 1 (ignoring the request)
    if rec2.recommended_strategy == rec1.recommended_strategy and rec2.rationale == rec1.rationale:
        print("\n[FAIL] Bug Reproduced: Agent returned identical generic answer despite request for alternatives.")
    else:
        print("\n[PASS] Agent provided alternative/modified response.")

if __name__ == "__main__":
    test_strategy_agent_generic_answer()

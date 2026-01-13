
import unittest
from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.supervisor import SupervisorAgent
from utils.schemas import StrategyRecommendation, SupplierShortlist

class TestRoutingGuardrails(unittest.TestCase):
    def setUp(self):
        self.supervisor = SupervisorAgent()

    def test_status_routing(self):
        """Goal A.4: Status questions should route to CaseClarifier"""
        next_agent, reason, _ = self.supervisor.determine_next_agent_with_confidence(
            dtp_stage="DTP-01",
            latest_output=None,
            policy_context=None,
            user_intent="What is the status of this case?"
        )
        self.assertEqual(next_agent, "CaseClarifier", "Status query failed to route to CaseClarifier")

    def test_strategy_routing(self):
        """Goal A.4: Strategy/Recommendation questions should route to Strategy"""
        next_agent, reason, _ = self.supervisor.determine_next_agent_with_confidence(
            dtp_stage="DTP-01",
            latest_output=None,
            policy_context=None,
            user_intent="Recommend a strategy for this category"
        )
        self.assertEqual(next_agent, "Strategy", "Strategy query failed to route to Strategy agent")

    def test_risk_routing(self):
        """Goal A.4: Risk questions should route to SignalInterpretation (or relevant risk agent)"""
        next_agent, reason, _ = self.supervisor.determine_next_agent_with_confidence(
            dtp_stage="DTP-02",
            latest_output=None,
            policy_context=None,
            user_intent="Are there any risks or compliance flags?"
        )
        self.assertEqual(next_agent, "SignalInterpretation", "Risk query failed to route to SignalInterpretation")

    def test_compare_routing(self):
        """Goal A.4: Comparison questions should route to SupplierEvaluation"""
        next_agent, reason, _ = self.supervisor.determine_next_agent_with_confidence(
            dtp_stage="DTP-03",
            latest_output=None,
            policy_context=None,
            user_intent="Compare the shortlisted suppliers"
        )
        self.assertEqual(next_agent, "SupplierEvaluation", "Compare query failed to route to SupplierEvaluation")

    def test_sequential_routing_no_intent(self):
        """Verify standard DTP sequential routing still works when no specific intent"""
        # DTP-01 -> Strategy
        next_agent, _, _ = self.supervisor.determine_next_agent_with_confidence(
            dtp_stage="DTP-01",
            latest_output=None,
            policy_context=None,
            user_intent=""
        )
        self.assertEqual(next_agent, "Strategy", "Default DTP-01 routing broken")

        # DTP-02 -> SupplierEvaluation
        next_agent, _, _ = self.supervisor.determine_next_agent_with_confidence(
            dtp_stage="DTP-02",
            latest_output=None,
            policy_context=None,
            user_intent=""
        )
        self.assertEqual(next_agent, "SupplierEvaluation", "Default DTP-02 routing broken")

    def test_output_driven_routing(self):
        """Verify routing based on agent output types"""
        # StrategyRecommendation (RFx) -> SupplierEvaluation
        strat_output = StrategyRecommendation(
            case_id="123",
            category_id="IT",
            recommended_strategy="RFx",
            rationale=["Test"],
            confidence=0.9,
            risks=[],
            required_capabilities=[]
        )
        next_agent, _, _ = self.supervisor.determine_next_agent_with_confidence(
            dtp_stage="DTP-01",
            latest_output=strat_output,
            policy_context=None,
            user_intent=""
        )
        self.assertEqual(next_agent, "SupplierEvaluation", "Strategy output didn't trigger SupplierEvaluation")

if __name__ == '__main__':
    unittest.main()

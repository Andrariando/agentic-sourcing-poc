
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.schemas import CaseSummary
from agents.supervisor import SupervisorAgent

# Mock dependencies that might be hard to load
# Use unittest.mock to handle internal logic, but trust installed packages for imports
# sys.modules['langchain_openai'] = MagicMock() -> Removed to prevent conflicts

# Import the function to test
# We need to mock get_supervisor in workflow.py to avoid loading the real one if it depends on complex things
# But SupervisorAgent seems fine to load.
from graphs.workflow import process_human_decision

class TestStageTransitions(unittest.TestCase):
    
    def setUp(self):
        # Create a basic case summary
        self.case_summary = CaseSummary(
            case_id="CASE-001",
            name="IT Renewal",
            category_id="IT-SERVICES",
            dtp_stage="DTP-01",
            trigger_source="User",
            status="In Progress",
            created_date=datetime.now().isoformat(),
            updated_date=datetime.now().isoformat(),
            summary_text="Test case",
            key_findings=[],
            recommended_action=None
        )
        
        # Base state
        self.base_state = {
            "case_summary": self.case_summary,
            "dtp_stage": "DTP-01",
            "dtp_policy_context": {},
            "human_decision": {},
            "waiting_for_human": True,
            "latest_agent_output": None
        }

    @patch('graphs.workflow.get_supervisor')
    def test_dtp01_to_dtp02_nested_format(self, mock_get_supervisor):
        """Test DTP-01 -> DTP-02 using nested chat_service format"""
        print("\n--- Testing DTP-01 -> DTP-02 (Nested Format) ---")
        
        # Setup mock supervisor to allow transition
        mock_supervisor_instance = MagicMock()
        mock_supervisor_instance.advance_dtp_stage.return_value = ("DTP-02", None)
        mock_get_supervisor.return_value = mock_supervisor_instance
        
        # Simulate chat_service.process_decision output structure
        human_decision = {
            "DTP-01": {
                "sourcing_required": {"answer": "Yes", "value": "Yes"},
                "sourcing_route": {"answer": "Strategic", "value": "Strategic"}
            }
        }
        
        state = self.base_state.copy()
        state["human_decision"] = human_decision
        state["last_human_action"] = "approve_decision" # Flag set by process_decision
        
        # Run
        new_state = process_human_decision(state)
        
        # Verify
        self.assertEqual(new_state["dtp_stage"], "DTP-02")
        self.assertFalse(new_state["waiting_for_human"])
        print("✅ DTP-01 -> DTP-02 transition successful")

    @patch('graphs.workflow.get_supervisor')
    def test_dtp02_to_dtp03_synonym_approval(self, mock_get_supervisor):
        """Test DTP-02 -> DTP-03 using synonym 'Approve' logic inheritance"""
        print("\n--- Testing DTP-02 -> DTP-03 (Synonym / Inferred) ---")
        
        mock_supervisor_instance = MagicMock()
        mock_supervisor_instance.advance_dtp_stage.return_value = ("DTP-03", None)
        mock_get_supervisor.return_value = mock_supervisor_instance
        
        # In this case, maybe strict last_human_action wasn't set, but we have valid answers
        # This tests the fallback logic: "Fallback: If current stage's questions are answered, treat as Approve"
        human_decision = {
            "DTP-02": {
                "supplier_list_confirmed": {"answer": "Approve", "value": "Yes"}
            }
        }
        
        state = self.base_state.copy()
        state["dtp_stage"] = "DTP-02"
        state["human_decision"] = human_decision
        state["last_human_action"] = "" # Simulate missing flag to test fallback
        
        # Run
        new_state = process_human_decision(state)
        
        # Verify
        self.assertEqual(new_state["dtp_stage"], "DTP-03")
        print("✅ DTP-02 -> DTP-03 transition inferred from answers successful")

    @patch('graphs.workflow.get_supervisor')
    def test_rejection_flow(self, mock_get_supervisor):
        """Test Rejection (Stay in stage)"""
        print("\n--- Testing Rejection Flow ---")
        
        state = self.base_state.copy()
        state["last_human_action"] = "reject_decision"
        state["human_decision"] = {"DTP-01": {}} # Structure exists but action is reject
        
        # Run
        new_state = process_human_decision(state)
        
        # Verify
        self.assertEqual(new_state["dtp_stage"], "DTP-01") # Should NOT advance
        self.assertFalse(new_state["waiting_for_human"]) # Should unblock to allow loop back
        self.assertIn("User rejected", new_state["user_intent"])
        print("✅ Rejection handled correctly (Workflow resumed with feedback)")
    
    @patch('graphs.workflow.get_supervisor')
    def test_transition_error_handling(self, mock_get_supervisor):
        """Test what happens if Supervisor blocks transition"""
        print("\n--- Testing Transition Error (Blocked) ---")
        
        mock_supervisor_instance = MagicMock()
        mock_supervisor_instance.advance_dtp_stage.return_value = ("DTP-01", "Missing required field")
        mock_get_supervisor.return_value = mock_supervisor_instance
        
        state = self.base_state.copy()
        state["last_human_action"] = "approve_decision"
        state["human_decision"] = {"DTP-01": {"foo": "bar"}}
        
        # Run
        new_state = process_human_decision(state)
        
        # Verify
        self.assertTrue(new_state["waiting_for_human"]) # Should stay waiting
        self.assertIn("error_state", new_state)
        print("✅ Transition blocked correctly on error")

if __name__ == '__main__':
    unittest.main()

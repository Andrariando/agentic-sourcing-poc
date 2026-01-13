
import sys
import os
import unittest
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
load_dotenv()

from agents.negotiation_agent import NegotiationSupportAgent
from utils.schemas import CaseSummary

class TestNegotiationOverride(unittest.TestCase):
    
    def test_intent_injection(self):
        # Initialize Agent
        print("\n--- Testing NegotiationAgent Intent Override ---")
        agent = NegotiationSupportAgent()
        
        # Setup Case
        case = CaseSummary(
            case_id="TEST-NEG-001",
            category_id="IT-Software",
            status="In Progress",
            supplier_id="SUP-001",
            dtp_stage="DTP-04",
            trigger_source="User",
            summary_text="Unit test for negotiation intent",
            created_date="2024-01-01T00:00:00"
        )
        
        # Mock Cache to disable it
        def mock_check_cache(*args, **kwargs):
            return type('obj', (object,), {'cache_hit': False, 'cache_key': 'test'}), None
        agent.check_cache = mock_check_cache
        
        # Execute with Specific Intent
        intent = "Prioritize extending payment terms to Net 60 days."
        print(f"User Intent: {intent}")
        
        # We expect the LLM to pick this up in 'negotiation_objectives' or 'target_terms'
        plan, _, _, _, _ = agent.create_negotiation_plan(
            case_summary=case,
            supplier_id="SUP-001",
            use_cache=False,
            user_intent=intent
        )
        
        print(f"Generated Objectives: {plan.negotiation_objectives}")
        print(f"Target Terms: {plan.target_terms}")
        
        # Verification
        # Check if 'Net 60' or '60 days' appears in the output
        term_found = False
        terms_str = json.dumps(plan.target_terms).lower()
        objs_str = json.dumps(plan.negotiation_objectives).lower()
        
        if "60" in terms_str or "60" in objs_str:
            term_found = True
            
        if term_found:
            print("[PASS] Agent successfully incorporated user intent for Net 60 terms.")
        else:
            print("[FAIL] Agent ignored user intent.")
            
        self.assertTrue(term_found, "Negotiation Plan did not reflect user intent (Net 60)")

if __name__ == "__main__":
    unittest.main()

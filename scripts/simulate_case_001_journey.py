
import sys
import os
import time
import json
from datetime import datetime

# Force utf-8 output to avoid Windows unicode errors
try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set dummy API key to pass validations
os.environ["OPENAI_API_KEY"] = "dummy"

from backend.services.chat_service import ChatService
from backend.services.case_service import get_case_service
from utils.schemas import CaseSummary

# Mock ChatOpenAI to avoid API keys requirements and real LLM calls
# We just want to test the flow logic (Supervisor, State, Transitions)
from unittest.mock import MagicMock
import langchain_openai

# Create a mock that returns appropriate responses based on input
class MockChatOpenAI:
    def __init__(self, *args, **kwargs):
        pass
    
    def _mock_msg(self, content):
        mock_msg = MagicMock()
        mock_msg.content = content
        mock_msg.model_dump.return_value = {"content": content}
        return mock_msg

    def invoke(self, messages, *args, **kwargs):
        # Extract content from last message
        last_msg_content = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
        last_msg_lower = last_msg_content.lower()

        # ---------------------------------------------------------
        # 1. INTENT CLASSIFICATION MOCK (LLMResponder)
        # ---------------------------------------------------------
        # Detect LLMResponder prompt via unique phrases
        if "you are analyzing a user message" in last_msg_lower or "classification rules" in last_msg_lower:
            # Extract user message
            user_said = ""
            if 'USER MESSAGE: "' in last_msg_content: # Case sensitive search in original content
                 try:
                    user_said = last_msg_content.split('USER MESSAGE: "')[1].split('"')[0].lower()
                 except:
                    user_said = last_msg_lower
            elif 'message: "' in last_msg_lower:
                 try:
                    user_said = last_msg_lower.split('message: "')[1].split('"')[0]
                 except:
                    user_said = last_msg_lower
            
            # Logic for intent (LLMResponder Schema)
            # Schema: { needs_agent, agent_hint, is_approval, is_rejection, is_progression, ... }
            
            if any(x in user_said for x in ["move", "next", "proceed", "advance"]):
                 return self._mock_msg(json.dumps({
                    "needs_agent": False,
                    "agent_hint": "",
                    "is_approval": False,
                    "is_rejection": False,
                    "is_progression": True,
                    "needs_data": False,
                    "missing_info": "",
                    "can_answer_directly": False,
                    "intent_summary": "User wants to advance stage"
                 }))
            elif any(x in user_said for x in ["yes", "approve", "confirm"]):
                 return self._mock_msg(json.dumps({
                    "needs_agent": False,
                    "agent_hint": "",
                    "is_approval": True,
                    "is_rejection": False,
                    "is_progression": False,
                    "needs_data": False,
                    "missing_info": "",
                    "can_answer_directly": False,
                    "intent_summary": "User approving"
                 }))
            elif any(x in user_said for x in ["analyze", "find", "draft", "negotiate", "award"]):
                 return self._mock_msg(json.dumps({
                    "needs_agent": True,
                    "agent_hint": "Strategy", # Generic, usually disregarded if workflow runs
                    "is_approval": False,
                    "is_rejection": False,
                    "is_progression": False,
                    "needs_data": False,
                    "missing_info": "",
                    "can_answer_directly": False,
                    "intent_summary": "Action request"
                 }))
            
            # Default fallback (Question)
            return self._mock_msg(json.dumps({
                "needs_agent": False,
                "agent_hint": "",
                "is_approval": False,
                "is_rejection": False,
                "is_progression": False,
                "needs_data": False,
                "missing_info": "",
                "can_answer_directly": True,
                "intent_summary": "General question"
            }))

        # ---------------------------------------------------------
        # 2. AGENT GENERATION MOCK
        # ---------------------------------------------------------
        content = "I am a mock response."
        
        # Strategy Agent Mock
        if "analyze" in last_msg_lower or "part of the strategy" in last_msg_lower:
             content = json.dumps({
                 "recommended_strategy": "RFx",
                 "justification": "Mock strategy analysis suggests RFx due to high costs.",
                 "confidence": 0.9,
                 "risks": []
             })
        
        # Supplier Agent Mock
        elif "supplier" in last_msg_lower:
             content = json.dumps({
                 "shortlisted_suppliers": ["Accenture", "Infosys"],
                 "justification": "Found 2 capable suppliers.",
                 "confidence": 0.9,
                 "top_choice_supplier_id": "SUP-001"
             })
             
        # RFx Agent Mock
        elif "rfx" in last_msg_lower or "draft" in last_msg_lower:
             content = json.dumps({
                 "rfx_sections": ["Scope", "SLA", "Pricing"],
                 "readiness_score": 0.95
             })
             
        # Negotiation Agent Mock
        elif "negotiate" in last_msg_lower:
             content = json.dumps({
                 "negotiation_levers": ["Volume discount", "Payment terms"],
                 "target_savings_pct": 10.0,
                 "supplier_id": "SUP-001"
             })
             
        # Contract Agent Mock (Implementation Plan req)
        elif "contract" in last_msg_lower or "award" in last_msg_lower:
             content = json.dumps({
                 "key_terms": {"term": "3 years", "auto_renew": False},
                 "supplier_id": "SUP-001"
             })
             
        # Implementation Mock
        elif "implementation" in last_msg_lower:
             content = json.dumps({
                 "rollout_steps": ["Kickoff", "Transition", "Go-Live"],
                 "supplier_id": "SUP-001"
             })
             
        return self._mock_msg(content)

# Patch the real class
langchain_openai.ChatOpenAI = MockChatOpenAI

def print_step(step_num, title):
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {title}")
    print(f"{'='*60}")

def print_status(case_summary):
    print(f"STATUS: {case_summary.dtp_stage} | {case_summary.status}")

def run_simulation():
    print(">>> STARTING CASE-001 SIMULATION (MOCKED LLM)")
    
    chat_service = ChatService()
    case_service = get_case_service()
    
    # 0. Create Case
    print("\n[0] Creating Case...")
    case_id = case_service.create_case(
        category_id="IT-SERVICES",
        name="Simulated Case 001",
        trigger_source="User"
    )
    print(f"Created Case ID: {case_id}")
    
    # helper to process message
    def msg(text):
        print(f"\n[USER]: {text}")
        response = chat_service.process_message(case_id, text)
        print(f"[COPILOT]: {response.assistant_message}")
        if response.waiting_for_human:
            print("   (Paused: Waiting for Human input)")
        return response

    # STEP 1: Strategy Analysis
    print_step(1, "Strategy Analysis")
    msg("Analyze this case for the renewal.")
    
    # STEP 2: Move to DTP-02 (Proactive)
    print_step(2, "Advance to DTP-02")
    msg("Okay, let's move to the next stage.")
    
    # System should ask: Is sourcing required?
    # STEP 3: Answer Strategy Checkpoint
    print_step(3, "Answer Checkpoint (Sourcing Required)")
    msg("Yes") # Should trigger specific Q
    
    # System should ask: Sourcing route?
    print_step(4, "Answer Checkpoint (Route)")
    msg("Strategic")
    
    # System asks: Do you want to confirm and proceed?
    print_step(5, "Confirm Transition to DTP-02")
    msg("Yes")
    
    # Verify we are at DTP-02
    state = case_service.get_case(case_id)
    print_status(state.summary)
    if state.dtp_stage != "DTP-02":
        print("[X] FAILED to reach DTP-02")
        return

    # STEP 4: Supplier ID
    print_step(6, "Find Suppliers (DTP-02)")
    msg("Find me some alternative suppliers.")
    
    # STEP 5: Move to DTP-03
    print_step(7, "Advance to DTP-03")
    msg("Looks good, proceed.")
    
    # System should ask: Confirm list?
    # STEP 6: Confirm
    print_step(8, "Confirm Supplier List")
    msg("Approve") # Testing synonym
    
    # System asks: Do you want to confirm and proceed?
    print_step(9, "Confirm Transition to DTP-03")
    msg("Yes")
    
    # Verify DTP-03
    state = case_service.get_case(case_id)
    print_status(state.summary)
    if state.dtp_stage != "DTP-03":
        print("[X] FAILED to reach DTP-03")
        return

    # STEP 7: RFx
    print_step(10, "Draft RFx (DTP-03)")
    msg("Draft the RFP.")
    
    # STEP 8: Move to DTP-04
    print_step(11, "Advance to DTP-04")
    msg("Evaluation is done. Move next.")
    
    # System ask: Evaluation complete?
    print_step(12, "Confirm Readiness")
    msg("Yes")
    
    # System asks: Confirm transition?
    print_step(13, "Confirm Transition to DTP-04")
    msg("Yes")
    
    # Verify DTP-04
    state = case_service.get_case(case_id)
    print_status(state.summary)
    if state.dtp_stage != "DTP-04":
        print("[X] FAILED to reach DTP-04")
        return

    # STEP 9: Negotiation
    print_step(14, "Run Negotiation (DTP-04)")
    msg("Help me negotiate terms.")
    
    # STEP 10: Award & Advance to DTP-05
    print_step(15, "Award and Advance to DTP-05")
    msg("Negotiations complete. I want to award and contract.")
    
    # System asks supplier ID?
    print_step(16, "Provide Supplier ID")
    msg("SUP-001") # Using mock supplier ID
    
    # System asks: Savings validated?
    print_step(17, "Confirm Savings")
    msg("Yes")

    # System asks: Legal approval?
    print_step(18, "Confirm Legal")
    msg("Yes")
    
    # System asks: Confirm transition?
    print_step(19, "Confirm Transition to DTP-05")
    msg("Yes")
    
    state = case_service.get_case(case_id)
    print_status(state.summary)
    if state.dtp_stage != "DTP-05":
         print(f"[X] Failed to reach DTP-05 (Status: {state.dtp_stage})")
         return

    # STEP 11: Contracting (DTP-05)
    print_step(20, "Contracting (DTP-05)")
    msg("Extract contract terms.")

    # Advance DTP-06
    print_step(21, "Advance to DTP-06")
    msg("Contract signed. Move to implementation.")
    
    # System asks: Confirm signed?
    print_step(22, "Confirm Signed")
    msg("Yes")
    # System asks: Confirm transition?
    print_step(23, "Confirm Transition to DTP-06")
    msg("Yes")

    state = case_service.get_case(case_id)
    print_status(state.summary)
    if state.dtp_stage != "DTP-06":
         print(f"[X] Failed to reach DTP-06 (Status: {state.dtp_stage})")
         return
    
    print("\n>>> SIMULATION COMPLETE: Case-001 Journey Verified (DTP-01 -> DTP-06)")
    print("[SUCCESS] Proactive Assistant Flow is fully functional.")

if __name__ == "__main__":
    run_simulation()

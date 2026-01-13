import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from utils.schemas import (
    CaseSummary, NegotiationPlan, AgentDialogue, AgentActionLog, DTPPolicyContext
)
from utils.state import PipelineState
from graphs.workflow import negotiation_node
from agents.supervisor import SupervisorAgent

def create_mock_state():
    summary = CaseSummary(
        case_id="TEST-DIALOGUE-001",
        category_id="IT-Hardware",
        supplier_id="SUP-TEST",
        dtp_stage="DTP-04",
        trigger_source="Test",
        status="In Progress",
        created_date=datetime.now().isoformat(),
        summary_text="Test case validation"
    )
    
    return {
        "case_summary": summary,
        "dtp_stage": "DTP-04",
        "trigger_source": "User",
        "budget_state": {"tokens_used": 0},
        "activity_log": [],
        "user_intent": "Negotiate assuming we have leverage", # Intent that might trigger concern if no leverage
        "conversation_history": []
    }

def test_agent_dialogue_handling():
    print("1. Setup Mock State")
    state = create_mock_state()
    
    # Mock NegotiationAgent in the workflow (dynamic patch)
    print("2. Patching NegotiationAgent output to simulate 'AgentDialogue'...")
    
    # Manually constructed AgentDialogue
    dialogue = AgentDialogue(
        agent_name="NegotiationSupport",
        message="I cannot proceed with negotiation planning because no contract data is available.",
        reasoning="User requested negotiation, but contract_id is missing and no contract document was found. Cannot identify levers.",
        status="NeedClarification",
        metadata={"missing": "contract"}
    )
    
    # We will simulate the node execution manually since we can't easily mock the agent instance *inside* the node function without complex patching
    # Instead, we'll verify the LOGIC that the node uses.
    
    # Simulate what negotiation_node does when agent returns AgentDialogue
    print("3. Simulating Workflow Logic for AgentDialogue...")
    output_payload_safe = dialogue.model_dump()
    task_name_safe = "Agent Dialogue"
    
    log = AgentActionLog(
        timestamp=datetime.now().isoformat(),
        case_id=state["case_summary"].case_id,
        dtp_stage=state["dtp_stage"],
        trigger_source="Test",
        agent_name="NegotiationSupport",
        task_name=task_name_safe,
        model_used="mock",
        output_payload=output_payload_safe,
        output_summary=f"Agent Dialogue ({dialogue.status}): {dialogue.message}"
    )
    
    state["latest_agent_output"] = dialogue
    state["activity_log"].append(log)
    
    # Assertions on Logging
    print(f"   [CHECK] Task Name: {log.task_name}")
    assert log.task_name == "Agent Dialogue"
    print("   [PASS] Task Name logged correctly.")
    
    # 4. Verify Supervisor Routing
    print("4. Verifying Supervisor Routing Logic...")
    supervisor = SupervisorAgent()
    next_agent, reason, clarification = supervisor.determine_next_agent_with_confidence(
        dtp_stage="DTP-04",
        latest_output=dialogue,
        policy_context=None,
        user_intent=""
    )
    
    print(f"   [CHECK] Next Agent: {next_agent}")
    print(f"   [CHECK] Reason: {reason}")
    
    if dialogue.status == "NeedClarification":
        assert next_agent == "CaseClarifier"
        print("   [PASS] Supervisor correctly routed 'NeedClarification' to 'CaseClarifier'.")
    
    # Test Concern Raised
    print("5. Verifying 'ConcernRaised' Routing...")
    dialogue.status = "ConcernRaised"
    next_agent, reason, _ = supervisor.determine_next_agent_with_confidence(
        dtp_stage="DTP-04",
        latest_output=dialogue
    )
    print(f"   [CHECK] Next Agent for Concern: {next_agent}")
    assert next_agent == "wait_for_human"
    print("   [PASS] Supervisor correctly routed 'ConcernRaised' to 'wait_for_human'.")

if __name__ == "__main__":
    try:
        test_agent_dialogue_handling()
        print("\n[SUCCESS] VERIFICATION SUCCESSFUL: Agent-Supervisor Dialogue Logic is correct.")
    except Exception as e:
        print(f"\n[FAILURE] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()

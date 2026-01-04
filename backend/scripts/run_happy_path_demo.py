#!/usr/bin/env python3
"""
Happy Path Demo Script - Full DTP-01 to DTP-06 Workflow

This script:
1. Seeds initial data if needed
2. Creates or uses CASE-DEMO-001
3. Runs through all 6 DTP stages with chat messages
4. Saves chat history and final case state
5. Makes the case available in the UI

Usage:
    python backend/scripts/run_happy_path_demo.py
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.services.case_service import get_case_service
from backend.services.chat_service import get_chat_service
from backend.persistence.database import init_db
from backend.scripts.seed_synthetic_data import (
    seed_suppliers, seed_spend, seed_sla_events, seed_documents
)
from sqlmodel import Session
from backend.persistence.database import get_engine


# Demo case ID
DEMO_CASE_ID = "CASE-DEMO-001"

# Happy Path Messages for each stage
HAPPY_PATH_MESSAGES = [
    # DTP-01: Strategy - Scan signals first
    {
        "stage": "DTP-01",
        "message": "Scan signals",
        "approve": True,
        "description": "Scan for sourcing signals"
    },
    # DTP-01: Strategy - Get recommendation (after signals)
    {
        "stage": "DTP-01",
        "message": "Recommend a strategy for this case",
        "approve": True,
        "description": "Request strategy recommendation"
    },
    # DTP-02: Planning - Score suppliers
    {
        "stage": "DTP-02",
        "message": "Score suppliers",
        "approve": True,
        "description": "Evaluate and score suppliers"
    },
    # DTP-03: Sourcing - Draft RFx
    {
        "stage": "DTP-03",
        "message": "Draft RFx",
        "approve": True,
        "description": "Create RFx document"
    },
    # DTP-04: Negotiation
    {
        "stage": "DTP-04",
        "message": "Support negotiation",
        "approve": True,
        "description": "Prepare negotiation plan"
    },
    # DTP-05: Contracting
    {
        "stage": "DTP-05",
        "message": "Extract key terms",
        "approve": True,
        "description": "Extract and validate contract terms"
    },
    # DTP-06: Implementation
    {
        "stage": "DTP-06",
        "message": "Generate implementation plan",
        "approve": True,
        "description": "Create implementation plan"
    },
]


def setup_demo_case() -> str:
    """Create or get the demo case."""
    from sqlmodel import Session, select
    from backend.persistence.models import CaseState
    from backend.persistence.database import get_engine
    
    session = Session(get_engine())
    
    try:
        # Check if case exists
        existing = session.exec(
            select(CaseState).where(CaseState.case_id == DEMO_CASE_ID)
        ).first()
        
        if existing:
            # Check if already completed
            if existing.dtp_stage == "DTP-06":
                print(f"  ✓ Found existing {DEMO_CASE_ID} already at DTP-06 (completed)")
                print(f"  → To re-run, delete the case first or use a different case ID")
                session.close()
                return DEMO_CASE_ID
            
            # Reset to DTP-01 for fresh demo
            print(f"  ✓ Found existing {DEMO_CASE_ID} at {existing.dtp_stage}, resetting to DTP-01...")
            existing.dtp_stage = "DTP-01"
            existing.status = "In Progress"
            existing.latest_agent_output = None
            existing.latest_agent_name = None
            existing.activity_log = None
            existing.human_decision = None
            existing.updated_at = datetime.now().isoformat()
            session.add(existing)
            session.commit()
            return DEMO_CASE_ID
        
        # Create new case directly in database with our ID
        now = datetime.now().isoformat()
        case = CaseState(
            case_id=DEMO_CASE_ID,
            category_id="IT_SERVICES",
            contract_id="CTR-001",
            supplier_id="SUP-001",
            trigger_source="Demo",
            dtp_stage="DTP-01",
            status="In Progress",
            name="Happy Path Demo - IT Services Renewal",
            summary_text="Complete happy path demonstration case running through all DTP stages from Strategy to Implementation.",
            key_findings=json.dumps([
                "Contract expires in 35 days",
                "Supplier performance trending stable",
                "Spend within 5% of budget"
            ]),
            created_at=now,
            updated_at=now
        )
        session.add(case)
        session.commit()
        print(f"  ✓ Created {DEMO_CASE_ID}")
        return DEMO_CASE_ID
    finally:
        session.close()


def run_happy_path(case_id: str) -> Dict[str, Any]:
    """Run through the full happy path workflow."""
    chat_service = get_chat_service()
    case_service = get_case_service()
    
    chat_history = []
    stage_history = []
    max_iterations = 50  # Safety limit
    iteration = 0
    
    print("\n" + "="*60)
    print("Running Happy Path Demo")
    print("="*60 + "\n")
    
    # Process each message in sequence, advancing stages
    for msg_idx, msg_config in enumerate(HAPPY_PATH_MESSAGES):
        iteration += 1
        if iteration > max_iterations:
            print(f"  ⚠ Reached maximum iterations, stopping...")
            break
        
        # Get current case state
        state = case_service.get_case_state(case_id)
        if not state:
            print(f"  ✗ Case {case_id} not found!")
            break
        
        current_stage = state["dtp_stage"]
        expected_stage = msg_config["stage"]
        
        # If we're already past this stage, skip
        if current_stage > expected_stage:
            print(f"  → Skipping {expected_stage} message (already at {current_stage})")
            continue
        
        # Wait until we reach the expected stage
        attempts = 0
        while current_stage != expected_stage and attempts < 5:
            attempts += 1
            state = case_service.get_case_state(case_id)
            if not state:
                break
            current_stage = state["dtp_stage"]
            
            # If we're ahead, break
            if current_stage > expected_stage:
                break
            
            # If waiting for approval, approve to advance
            if state.get("waiting_for_human"):
                print(f"  → Currently at {current_stage}, approving to advance to {expected_stage}...")
                decision_result = chat_service.process_decision(case_id, "Approve")
                if decision_result["success"]:
                    # Wait a moment for state to update
                    import time
                    time.sleep(0.5)
                    state = case_service.get_case_state(case_id)
                    if state:
                        current_stage = state["dtp_stage"]
                        print(f"  ✓ Advanced to {current_stage}")
                else:
                    print(f"  ✗ Failed to approve: {decision_result.get('message')}")
                    # Continue anyway, might not need approval
                    break
            else:
                # No approval needed - might need to run agent first
                break
        
        # Check if we should process this message
        if current_stage != expected_stage:
            # Try to send message anyway - might trigger agent
            pass
        
        # Send message
        print(f"\n[{current_stage}] {msg_config['description']}")
        print(f"  User: {msg_config['message']}")
        
        # Add to chat history
        chat_history.append({
            "role": "user",
            "content": msg_config["message"],
            "timestamp": datetime.now().isoformat(),
            "stage": current_stage
        })
        
        # Process message
        try:
            response = chat_service.process_message(
                case_id=case_id,
                user_message=msg_config["message"]
            )
            
            # Add assistant response to history
            chat_history.append({
                "role": "assistant",
                "content": response.assistant_message,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "intent": response.intent_classified,
                    "agent": response.agents_called[0] if response.agents_called else None,
                    "docs_retrieved": response.retrieval_context.get("documents_retrieved", 0) if response.retrieval_context else 0
                },
                "stage": current_stage
            })
            
            print(f"  AI: {response.assistant_message[:150]}...")
            
            # Wait a moment for state to update
            import time
            time.sleep(1.0)
            
            # Check current state again
            state = case_service.get_case_state(case_id)
            if state and state.get("waiting_for_human") and msg_config.get("approve"):
                print(f"  → Approving decision to advance...")
                
                # Approve decision
                decision_result = chat_service.process_decision(
                    case_id=case_id,
                    decision="Approve"
                )
                
                if decision_result["success"]:
                    # Wait for state update
                    time.sleep(0.5)
                    state = case_service.get_case_state(case_id)
                    if state:
                        new_stage = state["dtp_stage"]
                        stage_history.append({
                            "from_stage": current_stage,
                            "to_stage": new_stage,
                            "timestamp": datetime.now().isoformat(),
                            "action": "Approved",
                            "message": msg_config["message"]
                        })
                        
                        # Add approval to chat history
                        chat_history.append({
                            "role": "user",
                            "content": "Approve",
                            "timestamp": datetime.now().isoformat(),
                            "stage": current_stage
                        })
                        
                        chat_history.append({
                            "role": "assistant",
                            "content": f"Decision approved. Advanced to {new_stage}.",
                            "timestamp": datetime.now().isoformat(),
                            "stage": new_stage
                        })
                        
                        print(f"  ✓ Approved - Advanced to {new_stage}")
            
        except Exception as e:
            print(f"  ✗ Error processing message: {e}")
            import traceback
            traceback.print_exc()
            # Continue with next iteration
            continue
        
        # Small delay to ensure state is saved
        import time
        time.sleep(0.5)
    
    # Final check - ensure we're at DTP-06
    print("\n  → Verifying final state...")
    final_state = case_service.get_case_state(case_id)
    if final_state and final_state["dtp_stage"] != "DTP-06":
        print(f"  ⚠ Case is at {final_state['dtp_stage']}, not DTP-06. Attempting to complete...")
        # Try to complete remaining stages
        current = final_state["dtp_stage"]
        stage_order = ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"]
        try:
            current_idx = stage_order.index(current)
            # Send messages for remaining stages
            for remaining_idx in range(current_idx + 1, len(stage_order)):
                remaining_stage = stage_order[remaining_idx]
                # Find message for this stage
                for msg_cfg in HAPPY_PATH_MESSAGES:
                    if msg_cfg["stage"] == remaining_stage:
                        print(f"  → Completing {remaining_stage}...")
                        try:
                            resp = chat_service.process_message(case_id, msg_cfg["message"])
                            time.sleep(1)
                            state = case_service.get_case_state(case_id)
                            if state and state.get("waiting_for_human"):
                                chat_service.process_decision(case_id, "Approve")
                                time.sleep(0.5)
                        except:
                            pass
                        break
        except:
            pass
    
    # Get final state
    final_case = case_service.get_case(case_id)
    
    return {
        "case_id": case_id,
        "final_stage": final_case.dtp_stage if final_case else "Unknown",
        "final_status": final_case.status if final_case else "Unknown",
        "chat_history": chat_history,
        "stage_transitions": stage_history,
        "completed_at": datetime.now().isoformat()
    }


def save_demo_data(demo_result: Dict[str, Any]):
    """Save demo data including chat history to case."""
    case_service = get_case_service()
    case_id = demo_result["case_id"]
    
    # Get current case state
    state = case_service.get_case_state(case_id)
    if not state:
        print(f"  ✗ Case {case_id} not found for saving!")
        return
    
    # Save chat history to activity log or a custom field
    # We'll add it to activity log for now
    activity_log = state.get("activity_log", [])
    
    # Add chat history entries to activity log
    for chat_entry in demo_result["chat_history"]:
        activity_log.append({
            "timestamp": chat_entry["timestamp"],
            "action": f"Chat: {chat_entry['role']}",
            "agent_name": "User" if chat_entry["role"] == "user" else "Copilot",
            "details": {
                "message": chat_entry["content"],
                "stage": chat_entry.get("stage"),
                "metadata": chat_entry.get("metadata")
            }
        })
    
    # Update case state
    state["activity_log"] = activity_log
    
    # Save
    case_service.save_case_state(state)
    
    # Also save to a JSON file for reference
    demo_file = project_root / "data" / "happy_path_demo.json"
    demo_file.parent.mkdir(exist_ok=True)
    demo_file.write_text(json.dumps(demo_result, indent=2))
    
    print(f"\n  ✓ Saved demo data to {demo_file}")
    print(f"  ✓ Chat history saved to case activity log")


def main():
    """Main execution."""
    print("\n" + "="*60)
    print("HAPPY PATH DEMO - Full DTP-01 to DTP-06 Workflow")
    print("="*60 + "\n")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    
    # Seed data if needed
    print("\nSeeding required data...")
    engine = get_engine()
    with Session(engine) as session:
        try:
            # Check if data exists
            from sqlmodel import select
            from backend.persistence.models import SupplierPerformance
            
            existing = session.exec(select(SupplierPerformance)).first()
            if not existing:
                print("  Seeding suppliers, spend, and SLA data...")
                seed_suppliers(session)
                seed_spend(session)
                seed_sla_events(session)
            else:
                print("  ✓ Data already seeded")
        except Exception as e:
            print(f"  ⚠ Error seeding: {e}")
    
    # Seed documents
    try:
        from backend.rag.vector_store import get_vector_store
        vector_store = get_vector_store()
        # Try to seed documents (will skip if already exist)
        seed_documents(vector_store)
        print("  ✓ Documents available")
    except Exception as e:
        print(f"  ⚠ Document seeding: {e}")
    
    # Setup demo case
    print("\nSetting up demo case...")
    case_id = setup_demo_case()
    print(f"  ✓ Using case: {case_id}")
    
    # Run happy path
    print("\n" + "="*60)
    print("EXECUTING HAPPY PATH")
    print("="*60)
    
    demo_result = run_happy_path(case_id)
    
    # Save results
    print("\n" + "="*60)
    print("SAVING DEMO DATA")
    print("="*60)
    
    save_demo_data(demo_result)
    
    # Final verification
    final_case = case_service.get_case(demo_result['case_id'])
    if final_case:
        print("\n" + "="*60)
        print("FINAL VERIFICATION")
        print("="*60)
        print(f"  Current Stage: {final_case.dtp_stage}")
        print(f"  Status: {final_case.status}")
        print(f"  Activity Log Entries: {len(final_case.activity_log) if final_case.activity_log else 0}")
        
        if final_case.dtp_stage != "DTP-06":
            print(f"\n  ⚠ WARNING: Case is at {final_case.dtp_stage}, not DTP-06!")
            print(f"  → The demo may not have completed all stages.")
            print(f"  → Try running the script again or check the logs above.")
        else:
            print(f"\n  ✓ SUCCESS: Case completed all stages (DTP-06)")
    
    # Summary
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print(f"\nCase ID: {demo_result['case_id']}")
    print(f"Final Stage: {demo_result['final_stage']}")
    print(f"Final Status: {demo_result['final_status']}")
    print(f"Chat Messages: {len([m for m in demo_result['chat_history'] if m['role'] == 'user'])}")
    print(f"Stage Transitions: {len(demo_result['stage_transitions'])}")
    
    if demo_result['final_stage'] == "DTP-06":
        print("\n✅ Demo case is complete and ready to view!")
        print("\nTo view in UI:")
        print(f"  1. Start backend: python -m uvicorn backend.main:app --reload")
        print(f"  2. Start frontend: streamlit run frontend/app.py")
        print(f"  3. Open case: {demo_result['case_id']}")
        print(f"  4. Chat history will be loaded automatically from activity log")
    else:
        print("\n⚠ Demo case did not complete all stages.")
        print("  Check the logs above for errors.")
        print("  You may need to re-run the script.")
    
    print(f"\nDemo data saved to: data/happy_path_demo.json")
    print("")


if __name__ == "__main__":
    main()


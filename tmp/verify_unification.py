
import sys
import os
from unittest.mock import MagicMock

# Add current directory to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

print("--- VERIFYING AGENT UNIFICATION ---")

# 1. Test backend.agents imports
print("\n1. Testing backend.agents unified imports...")
try:
    from backend.agents import (
        SupervisorAgent, SourcingSignalAgent, SupplierScoringAgent, 
        RfxDraftAgent, NegotiationSupportAgent, ContractSupportAgent, ImplementationAgent
    )
    from agents.supervisor import SupervisorAgent as RootSupervisor
    
    print(f"SUCCESS: backend.agents imports working.")
    print(f"VERIFICATION: SupervisorAgent is RootSupervisor? {SupervisorAgent is RootSupervisor}")
except Exception as e:
    print(f"FAILED: backend.agents imports: {e}")

# 2. Test ChatService initialization
print("\n2. Testing ChatService initialization...")
try:
    # Mock services needed by ChatService
    import backend.services.chat_service as cs
    cs.get_case_service = MagicMock()
    
    chat_service = cs.ChatService()
    print("SUCCESS: ChatService initialized.")
except Exception as e:
    print(f"FAILED: ChatService initialization: {e}")
    import traceback
    traceback.print_exc()

# 3. Test LangGraph compilation
print("\n3. Testing LangGraph compilation...")
try:
    from graphs.workflow import get_workflow_graph
    app = get_workflow_graph()
    print("SUCCESS: LangGraph compiled successfully.")
except Exception as e:
    print(f"FAILED: LangGraph compilation: {e}")
    import traceback
    traceback.print_exc()

print("\n--- UNIFICATION VERIFICATION COMPLETE ---")

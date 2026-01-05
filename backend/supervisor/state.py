"""
Supervisor state management.
The Supervisor is the SINGLE SOURCE OF TRUTH for case state.
"""
from typing import TypedDict, Optional, List, Dict, Any, Union
from datetime import datetime
import json

from shared.constants import UserIntent, CaseStatus, DTP_STAGES


class SupervisorState(TypedDict):
    """
    Central state object managed by Supervisor.
    
    No agent may directly modify this state.
    All state changes go through the Supervisor.
    """
    # Case identification
    case_id: str
    dtp_stage: str  # DTP-01 to DTP-06
    
    # Case context
    category_id: str
    contract_id: Optional[str]
    supplier_id: Optional[str]
    trigger_source: str  # "User" or "Signal"
    status: str  # CaseStatus
    
    # Current interaction
    user_intent: str  # Raw user message
    intent_classification: str  # EXPLAIN, EXPLORE, DECIDE, STATUS
    
    # Agent outputs (read-only for agents)
    latest_agent_output: Optional[Dict[str, Any]]
    latest_agent_name: Optional[str]
    
    # Activity tracking
    activity_log: List[Dict[str, Any]]
    
    # Human decision (only set when waiting)
    human_decision: Optional[Dict[str, Any]]
    waiting_for_human: bool
    
    # Retrieval context (what was retrieved this turn)
    retrieval_context: Optional[Dict[str, Any]]
    documents_retrieved: List[str]  # Document IDs
    
    # Governance
    allowed_actions: List[str]  # What actions are permitted
    blocked_reason: Optional[str]  # Why an action was blocked
    
    # Error handling
    error_state: Optional[Dict[str, Any]]


class StateManager:
    """
    Manages Supervisor state with governance enforcement.
    """
    
    # DTP stage transitions (what stages can follow what)
    ALLOWED_TRANSITIONS = {
        "DTP-01": ["DTP-02"],
        "DTP-02": ["DTP-03", "DTP-04"],
        "DTP-03": ["DTP-04"],
        "DTP-04": ["DTP-05"],
        "DTP-05": ["DTP-06"],
        "DTP-06": ["DTP-06"],  # Terminal
    }
    
    # Which intents are allowed at which stages
    STAGE_INTENT_PERMISSIONS = {
        "DTP-01": [UserIntent.EXPLAIN, UserIntent.EXPLORE, UserIntent.DECIDE, UserIntent.STATUS],
        "DTP-02": [UserIntent.EXPLAIN, UserIntent.EXPLORE, UserIntent.DECIDE, UserIntent.STATUS],
        "DTP-03": [UserIntent.EXPLAIN, UserIntent.EXPLORE, UserIntent.DECIDE, UserIntent.STATUS],
        "DTP-04": [UserIntent.EXPLAIN, UserIntent.EXPLORE, UserIntent.DECIDE, UserIntent.STATUS],
        "DTP-05": [UserIntent.EXPLAIN, UserIntent.EXPLORE, UserIntent.DECIDE, UserIntent.STATUS],
        "DTP-06": [UserIntent.EXPLAIN, UserIntent.STATUS],  # Execution - limited actions
    }
    
    @classmethod
    def create_initial_state(
        cls,
        case_id: str,
        category_id: str,
        trigger_source: str = "User",
        contract_id: Optional[str] = None,
        supplier_id: Optional[str] = None
    ) -> SupervisorState:
        """Create initial state for a new case."""
        return SupervisorState(
            case_id=case_id,
            dtp_stage="DTP-01",
            category_id=category_id,
            contract_id=contract_id,
            supplier_id=supplier_id,
            trigger_source=trigger_source,
            status=CaseStatus.IN_PROGRESS.value,
            user_intent="",
            intent_classification=UserIntent.UNKNOWN.value,
            latest_agent_output=None,
            latest_agent_name=None,
            activity_log=[],
            human_decision=None,
            waiting_for_human=False,
            retrieval_context=None,
            documents_retrieved=[],
            allowed_actions=cls.ALLOWED_TRANSITIONS.get("DTP-01", []),
            blocked_reason=None,
            error_state=None
        )
    
    @classmethod
    def validate_transition(
        cls,
        current_stage: str,
        target_stage: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if a DTP stage transition is allowed.
        
        Returns:
            (is_valid, error_message)
        """
        if current_stage not in cls.ALLOWED_TRANSITIONS:
            return False, f"Unknown current stage: {current_stage}"
        
        if target_stage not in DTP_STAGES:
            return False, f"Unknown target stage: {target_stage}"
        
        allowed = cls.ALLOWED_TRANSITIONS[current_stage]
        if target_stage not in allowed:
            return False, f"Cannot transition from {current_stage} to {target_stage}. Allowed: {allowed}"
        
        return True, None
    
    @classmethod
    def validate_intent_for_stage(
        cls,
        dtp_stage: str,
        intent: UserIntent
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if an intent is allowed at the current stage.
        
        Returns:
            (is_valid, error_message)
        """
        allowed = cls.STAGE_INTENT_PERMISSIONS.get(dtp_stage, [])
        
        if intent not in allowed:
            return False, f"Intent {intent.value} is not allowed at stage {dtp_stage}"
        
        return True, None
    
    @classmethod
    def can_advance_stage(
        cls,
        state: SupervisorState,
        has_human_approval: bool
    ) -> tuple[bool, Optional[str]]:
        """
        Check if stage can be advanced.
        
        Rules:
        1. Must have human approval
        2. Must be a valid transition
        3. Must not be in error state
        """
        if not has_human_approval:
            return False, "Human approval required to advance DTP stage"
        
        if state.get("error_state"):
            return False, "Cannot advance stage while in error state"
        
        current = state["dtp_stage"]
        next_stages = cls.ALLOWED_TRANSITIONS.get(current, [])
        
        if not next_stages:
            return False, f"No valid transitions from {current}"
        
        return True, None
    
    @classmethod
    def advance_stage(
        cls,
        state: SupervisorState,
        target_stage: Optional[str] = None
    ) -> tuple[SupervisorState, Optional[str]]:
        """
        Advance to next DTP stage.
        
        Args:
            state: Current state
            target_stage: Target stage (uses first allowed if not specified)
            
        Returns:
            (new_state, error_message)
        """
        current = state["dtp_stage"]
        allowed = cls.ALLOWED_TRANSITIONS.get(current, [])
        
        if not allowed:
            return state, f"No valid transitions from {current}"
        
        if target_stage:
            if target_stage not in allowed:
                return state, f"Cannot transition to {target_stage} from {current}"
            new_stage = target_stage
        else:
            new_stage = allowed[0]
        
        # Create new state with updated stage
        new_state = dict(state)
        new_state["dtp_stage"] = new_stage
        new_state["allowed_actions"] = cls.ALLOWED_TRANSITIONS.get(new_stage, [])
        new_state["human_decision"] = None
        new_state["waiting_for_human"] = False
        
        # Add to activity log
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "stage_advance",
            "from_stage": current,
            "to_stage": new_stage,
            "agent_name": "Supervisor"
        }
        new_state["activity_log"] = state.get("activity_log", []) + [log_entry]
        
        return SupervisorState(**new_state), None







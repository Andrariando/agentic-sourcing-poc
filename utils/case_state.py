"""
Canonical Case State - Single authoritative case record.

PHASE 2 - OBJECTIVE D: Clarify and Unify Case State Ownership

This module provides a single canonical CaseState model that:
- Represents the authoritative case record
- Is used consistently across Supervisor, Workflow, Memory, Response generation
- Eliminates ambiguity about which state object is "the truth"

DESIGN PRINCIPLES:
- CaseState is the canonical record
- PipelineState is an execution snapshot (transient)
- UI views derive from CaseState
- Only Supervisor can mutate CaseState
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

from utils.schemas import (
    CaseSummary, HumanDecision, AgentActionLog,
    StrategyRecommendation, SupplierShortlist, NegotiationPlan,
    SignalAssessment, ClarificationRequest, OutOfScopeNotice,
    RFxDraft, ContractExtraction, ImplementationPlan
)
from utils.case_memory import CaseMemory, create_case_memory


# Type alias for all possible agent outputs
AgentOutput = Union[
    StrategyRecommendation,
    SupplierShortlist,
    NegotiationPlan,
    SignalAssessment,
    ClarificationRequest,
    OutOfScopeNotice,
    RFxDraft,
    ContractExtraction,
    ImplementationPlan,
    None
]


class CaseState(BaseModel):
    """
    Canonical case state - the single source of truth for a case.
    
    This model is:
    - Authoritative: Other state objects are views or snapshots
    - Persistent: Survives across workflow invocations
    - Complete: Contains all case data needed for decisions
    - Owned by Supervisor: Only Supervisor mutations are allowed
    """
    
    # === Identity ===
    case_id: str
    name: str
    
    # === Classification ===
    category_id: str
    contract_id: Optional[str] = None
    supplier_id: Optional[str] = None
    trigger_source: str  # "User" | "Signal" | "System"
    trigger_type: Optional[str] = None  # "Renewal" | "Savings" | "Risk" | "Monitoring"
    
    # === Lifecycle ===
    dtp_stage: str  # "DTP-01" through "DTP-06"
    status: str  # "In Progress" | "Waiting for Human Decision" | "Completed" | "Rejected"
    created_date: str
    updated_date: str
    created_timestamp: str
    updated_timestamp: str
    
    # === Content ===
    summary: CaseSummary
    user_intent: Optional[str] = None
    
    # === Agent Outputs (History) ===
    latest_agent_output: AgentOutput = None
    latest_agent_name: Optional[str] = None
    output_history: List[Dict[str, Any]] = Field(default_factory=list)  # List of {agent, output_type, timestamp}
    
    # === Human Decisions ===
    human_decision: Optional[HumanDecision] = None
    waiting_for_human: bool = False
    
    # === Memory (Phase 2) ===
    memory: CaseMemory = None  # Will be initialized if None
    
    # === Audit ===
    activity_log: List[AgentActionLog] = Field(default_factory=list)
    
    # === Contradictions (Phase 2) ===
    active_contradictions: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        # Initialize memory if not provided
        if self.memory is None:
            self.memory = create_case_memory(self.case_id)
    
    def record_agent_output(
        self,
        agent_name: str,
        output: AgentOutput
    ) -> None:
        """
        Record a new agent output (called by Supervisor only).
        
        Updates:
        - latest_agent_output
        - latest_agent_name
        - output_history
        - memory
        """
        self.latest_agent_output = output
        self.latest_agent_name = agent_name
        self.updated_timestamp = datetime.now().isoformat()
        self.updated_date = datetime.now().strftime("%Y-%m-%d")
        
        # Add to history
        if output is not None:
            self.output_history.append({
                "agent": agent_name,
                "output_type": type(output).__name__,
                "timestamp": self.updated_timestamp
            })
            
            # Update memory
            if self.memory:
                output_type = type(output).__name__
                summary = self._summarize_output(output)
                details = self._extract_output_details(output)
                self.memory.record_agent_output(agent_name, output_type, summary, details)
    
    def record_human_decision(
        self,
        decision: str,
        reason: Optional[str] = None,
        context: Optional[str] = None
    ) -> None:
        """Record a human decision (called by Supervisor only)."""
        self.human_decision = HumanDecision(
            decision=decision,
            reason=reason,
            edited_fields={},
            timestamp=datetime.now().isoformat(),
            user_id=None
        )
        self.waiting_for_human = False
        self.updated_timestamp = datetime.now().isoformat()
        
        # Update memory
        if self.memory:
            self.memory.record_human_decision(decision, reason, context)
    
    def record_user_intent(self, intent: str) -> None:
        """Record user intent."""
        self.user_intent = intent
        if self.memory:
            self.memory.record_user_intent(intent)
    
    def add_contradiction(self, description: str) -> None:
        """Add a detected contradiction."""
        if description not in self.active_contradictions:
            self.active_contradictions.append(description)
            if self.memory:
                self.memory.record_contradiction(description, [], {})
    
    def resolve_contradiction(self, description: str) -> None:
        """Resolve a contradiction (typically after human decision)."""
        if description in self.active_contradictions:
            self.active_contradictions.remove(description)
            if self.memory:
                self.memory.resolve_contradiction(description)
    
    def get_memory_context(self) -> str:
        """Get memory context for agent prompts."""
        if self.memory:
            return self.memory.get_prompt_context()
        return ""
    
    def advance_stage(self, new_stage: str) -> None:
        """Advance to a new DTP stage (Supervisor only)."""
        self.dtp_stage = new_stage
        self.summary.dtp_stage = new_stage
        self.updated_timestamp = datetime.now().isoformat()
        self.updated_date = datetime.now().strftime("%Y-%m-%d")
    
    def set_waiting_for_human(self, reason: str = "") -> None:
        """Set case to wait for human decision."""
        self.waiting_for_human = True
        self.status = "Waiting for Human Decision"
    
    def _summarize_output(self, output: AgentOutput) -> str:
        """Generate a summary string for an output."""
        if output is None:
            return "No output"
        
        output_type = type(output).__name__
        
        if output_type == "StrategyRecommendation":
            return f"Recommends {getattr(output, 'recommended_strategy', 'unknown')}"
        elif output_type == "SupplierShortlist":
            count = len(getattr(output, "shortlisted_suppliers", []))
            return f"Shortlisted {count} suppliers"
        elif output_type == "NegotiationPlan":
            return f"Negotiation plan for {getattr(output, 'supplier_id', 'unknown')}"
        elif output_type == "RFxDraft":
            count = len(getattr(output, "rfx_sections", {}))
            return f"RFx draft with {count} sections"
        elif output_type == "ContractExtraction":
            count = len(getattr(output, "extracted_terms", {}))
            return f"Extracted {count} terms"
        elif output_type == "ImplementationPlan":
            count = len(getattr(output, "rollout_steps", []))
            return f"Implementation plan with {count} steps"
        elif output_type == "ClarificationRequest":
            return f"Clarification: {getattr(output, 'reason', 'info needed')}"
        else:
            return f"Produced {output_type}"
    
    def _extract_output_details(self, output: AgentOutput) -> Dict[str, Any]:
        """Extract key details from an output for memory."""
        if output is None:
            return {}
        
        details = {}
        
        if hasattr(output, "recommended_strategy"):
            details["recommended_strategy"] = output.recommended_strategy
        if hasattr(output, "confidence"):
            details["confidence"] = output.confidence
        if hasattr(output, "top_choice_supplier_id"):
            details["top_choice_supplier_id"] = output.top_choice_supplier_id
        if hasattr(output, "supplier_id"):
            details["supplier_id"] = output.supplier_id
        
        return details
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "case_id": self.case_id,
            "name": self.name,
            "category_id": self.category_id,
            "contract_id": self.contract_id,
            "supplier_id": self.supplier_id,
            "dtp_stage": self.dtp_stage,
            "status": self.status,
            "trigger_source": self.trigger_source,
            "user_intent": self.user_intent,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
            "created_timestamp": self.created_timestamp,
            "updated_timestamp": self.updated_timestamp,
            "waiting_for_human": self.waiting_for_human,
            "latest_agent_name": self.latest_agent_name,
            "active_contradictions": self.active_contradictions,
        }


def create_case_state(
    case_id: str,
    name: str,
    category_id: str,
    trigger_source: str,
    contract_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
) -> CaseState:
    """Factory function to create a new CaseState."""
    now = datetime.now()
    now_date = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    
    summary = CaseSummary(
        case_id=case_id,
        category_id=category_id,
        contract_id=contract_id,
        supplier_id=supplier_id,
        dtp_stage="DTP-01",
        trigger_source=trigger_source,
        status="In Progress",
        created_date=now_date,
        summary_text=f"New case for category {category_id}",
        key_findings=[],
        recommended_action=None
    )
    
    return CaseState(
        case_id=case_id,
        name=name,
        category_id=category_id,
        contract_id=contract_id,
        supplier_id=supplier_id,
        trigger_source=trigger_source,
        dtp_stage="DTP-01",
        status="In Progress",
        created_date=now_date,
        updated_date=now_date,
        created_timestamp=now_iso,
        updated_timestamp=now_iso,
        summary=summary,
        memory=create_case_memory(case_id)
    )

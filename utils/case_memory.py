"""
Case Memory Layer - Structured, bounded memory for case continuity.

PHASE 2 - OBJECTIVE A: Make Memory Real (Not Cosmetic)

This module provides a rolling, structured CaseMemory object that:
- Summarizes key decisions made during the case
- Records human approvals/rejections with reasons
- Tracks important user intents across turns
- Is bounded in size (summary, not raw chat)
- Is injected into every agent prompt for context

DESIGN PRINCIPLES:
- Memory is updated after every workflow execution
- Memory is NOT raw chat transcripts
- Memory is bounded (max entries, summarized)
- Memory lives with the case, not in UI session state
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MemoryEntry(BaseModel):
    """Single memory entry representing a significant case event."""
    timestamp: str
    entry_type: str  # "decision", "approval", "rejection", "user_intent", "agent_output", "contradiction"
    agent_name: Optional[str] = None
    summary: str  # Concise summary (max ~100 chars)
    details: Dict[str, Any] = Field(default_factory=dict)


class CaseMemory(BaseModel):
    """
    Structured, bounded memory for a sourcing case.
    
    This is the canonical memory object that:
    - Persists across workflow invocations
    - Is injected into agent prompts
    - Provides case continuity without raw chat history
    """
    case_id: str
    
    # Rolling memory entries (bounded to MAX_ENTRIES)
    entries: List[MemoryEntry] = Field(default_factory=list)
    
    # Summarized state (always current)
    current_strategy: Optional[str] = None  # Latest recommended strategy
    current_supplier_choice: Optional[str] = None  # Latest supplier recommendation
    human_decisions: List[str] = Field(default_factory=list)  # "Approved X", "Rejected Y"
    key_user_intents: List[str] = Field(default_factory=list)  # Important user requests
    active_contradictions: List[str] = Field(default_factory=list)  # Unresolved conflicts
    
    # Collaboration Mode tracking (PHASE 3)
    collaboration_insights: List[str] = Field(default_factory=list)  # Key insights from discussions
    user_preferences: Dict[str, Any] = Field(default_factory=dict)  # Captured user preferences
    flagged_risks: List[str] = Field(default_factory=list)  # Risks identified during collaboration
    key_decisions: List[str] = Field(default_factory=list)  # Decisions made during collaboration
    last_collaboration_topic: Optional[str] = None  # Last topic discussed
    intent_shifts: List[str] = Field(default_factory=list)  # Track COLLABORATIVE -> EXECUTION shifts
    recommended_strategy: Optional[str] = None  # Alias for current_strategy (for collaboration engine)
    
    # Counters
    total_agent_calls: int = 0
    total_human_decisions: int = 0
    total_collaboration_turns: int = 0  # Count of collaborative exchanges
    
    # Bounds
    MAX_ENTRIES: int = 20  # Keep last 20 entries
    MAX_USER_INTENTS: int = 5  # Keep last 5 user intents
    MAX_HUMAN_DECISIONS: int = 10  # Keep last 10 decisions
    MAX_COLLABORATION_INSIGHTS: int = 10  # Keep last 10 insights
    MAX_KEY_DECISIONS: int = 10  # Keep last 10 decisions
    
    def add_entry(self, entry: MemoryEntry) -> None:
        """Add a memory entry, enforcing bounds."""
        self.entries.append(entry)
        if len(self.entries) > self.MAX_ENTRIES:
            self.entries = self.entries[-self.MAX_ENTRIES:]
    
    def record_agent_output(
        self,
        agent_name: str,
        output_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an agent's output as a memory entry."""
        self.total_agent_calls += 1
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="agent_output",
            agent_name=agent_name,
            summary=f"{agent_name}: {summary[:80]}",
            details=details or {}
        )
        self.add_entry(entry)
        
        # Update summarized state based on output type
        if output_type == "StrategyRecommendation":
            self.current_strategy = details.get("recommended_strategy") if details else None
        elif output_type == "SupplierShortlist":
            self.current_supplier_choice = details.get("top_choice_supplier_id") if details else None
    
    def record_human_decision(
        self,
        decision: str,  # "Approve" or "Reject"
        reason: Optional[str] = None,
        context: Optional[str] = None
    ) -> None:
        """Record a human decision."""
        self.total_human_decisions += 1
        summary = f"Human {decision}"
        if context:
            summary += f" ({context})"
        
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="approval" if decision == "Approve" else "rejection",
            agent_name="Human",
            summary=summary[:100],
            details={"decision": decision, "reason": reason}
        )
        self.add_entry(entry)
        
        # Update summarized decisions
        decision_text = f"{decision}: {context or 'unspecified'}"
        if reason:
            decision_text += f" - {reason[:50]}"
        self.human_decisions.append(decision_text)
        if len(self.human_decisions) > self.MAX_HUMAN_DECISIONS:
            self.human_decisions = self.human_decisions[-self.MAX_HUMAN_DECISIONS:]
    
    def record_user_intent(self, intent: str) -> None:
        """Record a significant user intent."""
        # Only record meaningful intents (not status queries)
        if len(intent.strip()) > 5:
            entry = MemoryEntry(
                timestamp=datetime.now().isoformat(),
                entry_type="user_intent",
                agent_name=None,
                summary=f"User: {intent[:80]}",
                details={"full_intent": intent}
            )
            self.add_entry(entry)
            
            # Keep last N intents in summary
            self.key_user_intents.append(intent[:100])
            if len(self.key_user_intents) > self.MAX_USER_INTENTS:
                self.key_user_intents = self.key_user_intents[-self.MAX_USER_INTENTS:]
    
    def record_contradiction(
        self,
        description: str,
        agents_involved: List[str],
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a detected contradiction between agent outputs."""
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="contradiction",
            agent_name=", ".join(agents_involved),
            summary=f"CONFLICT: {description[:80]}",
            details=details or {}
        )
        self.add_entry(entry)
        self.active_contradictions.append(description)
    
    def resolve_contradiction(self, description: str) -> None:
        """Mark a contradiction as resolved (by human decision)."""
        if description in self.active_contradictions:
            self.active_contradictions.remove(description)
    
    def record_collaboration_turn(
        self,
        user_input: str,
        topic: Optional[str] = None,
        insight: Optional[str] = None,
        preference: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a collaborative discussion turn (PHASE 3).
        
        This tracks collaborative interactions separately from execution.
        """
        self.total_collaboration_turns += 1
        
        # Record the collaborative turn
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="collaboration",
            agent_name="Collaboration",
            summary=f"Discussion: {user_input[:60]}",
            details={
                "topic": topic,
                "insight": insight,
                "preference": preference
            }
        )
        self.add_entry(entry)
        
        # Update topic
        if topic:
            self.last_collaboration_topic = topic
        
        # Record insight if captured
        if insight:
            self.collaboration_insights.append(insight)
            if len(self.collaboration_insights) > self.MAX_COLLABORATION_INSIGHTS:
                self.collaboration_insights = self.collaboration_insights[-self.MAX_COLLABORATION_INSIGHTS:]
        
        # Record preference if captured
        if preference:
            self.user_preferences.update(preference)
    
    def record_intent_shift(self, from_intent: str, to_intent: str, trigger: str) -> None:
        """
        Record when user shifts from COLLABORATIVE to EXECUTION mode.
        
        This provides audit trail of when execution was explicitly requested.
        """
        shift = f"{from_intent} → {to_intent}: {trigger[:50]}"
        self.intent_shifts.append(shift)
        
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="intent_shift",
            agent_name=None,
            summary=f"Intent shift: {shift}",
            details={"from": from_intent, "to": to_intent, "trigger": trigger}
        )
        self.add_entry(entry)
    
    def record_key_decision(self, decision: str, context: Optional[str] = None) -> None:
        """Record a key decision made during collaboration."""
        decision_text = decision if not context else f"{decision} ({context})"
        self.key_decisions.append(decision_text)
        if len(self.key_decisions) > self.MAX_KEY_DECISIONS:
            self.key_decisions = self.key_decisions[-self.MAX_KEY_DECISIONS:]
    
    def record_flagged_risk(self, risk: str) -> None:
        """Record a risk flagged during collaboration."""
        if risk not in self.flagged_risks:
            self.flagged_risks.append(risk)
    
    def get_collaboration_context(self) -> str:
        """
        Get collaboration-specific context for the Collaboration Engine.
        
        This is used by the Collaboration Engine to generate contextual responses.
        """
        lines = []
        
        if self.key_decisions:
            lines.append(f"**Decisions made:** {'; '.join(self.key_decisions[-3:])}")
        
        if self.user_preferences:
            prefs = [f"{k}: {v}" for k, v in list(self.user_preferences.items())[:3]]
            lines.append(f"**User preferences:** {'; '.join(prefs)}")
        
        if self.flagged_risks:
            lines.append(f"**Flagged risks:** {'; '.join(self.flagged_risks[-3:])}")
        
        if self.collaboration_insights:
            lines.append(f"**Insights:** {'; '.join(self.collaboration_insights[-2:])}")
        
        return "\n".join(lines) if lines else ""
    
    def get_prompt_context(self) -> str:
        """
        Generate a bounded context string for injection into agent prompts.
        
        This is the key method that provides memory to agents without
        passing raw chat history.
        """
        lines = []
        lines.append("=== CASE MEMORY (for context only, not for decision-making) ===")
        
        # Current state summary
        if self.current_strategy:
            lines.append(f"• Current recommended strategy: {self.current_strategy}")
        if self.current_supplier_choice:
            lines.append(f"• Current top supplier: {self.current_supplier_choice}")
        
        # Human decisions
        if self.human_decisions:
            lines.append(f"• Human decisions so far: {'; '.join(self.human_decisions[-3:])}")
        
        # Key user intents
        if self.key_user_intents:
            lines.append(f"• Recent user requests: {'; '.join(self.key_user_intents[-2:])}")
        
        # Active contradictions (important!)
        if self.active_contradictions:
            lines.append(f"⚠️ UNRESOLVED CONFLICTS: {'; '.join(self.active_contradictions)}")
        
        # Recent activity summary
        recent_entries = self.entries[-5:] if self.entries else []
        if recent_entries:
            lines.append("• Recent activity:")
            for entry in recent_entries:
                lines.append(f"  - {entry.summary}")
        
        lines.append("=== END CASE MEMORY ===")
        return "\n".join(lines)
    
    def get_summary_for_ui(self) -> Dict[str, Any]:
        """Get a summary dict for UI display."""
        return {
            "total_agent_calls": self.total_agent_calls,
            "total_human_decisions": self.total_human_decisions,
            "current_strategy": self.current_strategy,
            "current_supplier_choice": self.current_supplier_choice,
            "active_contradictions": len(self.active_contradictions),
            "memory_entries_count": len(self.entries)
        }


def create_case_memory(case_id: str) -> CaseMemory:
    """Factory function to create a new CaseMemory instance."""
    return CaseMemory(case_id=case_id)


def update_memory_from_workflow_result(
    memory: CaseMemory,
    agent_name: str,
    output: Any,
    user_intent: Optional[str] = None
) -> CaseMemory:
    """
    Update case memory after a workflow execution.
    
    This is called after every workflow run to ensure memory stays current.
    """
    # Record user intent if provided
    if user_intent:
        memory.record_user_intent(user_intent)
    
    # Record agent output
    if output is not None:
        output_type = type(output).__name__
        
        # Extract summary based on output type
        if hasattr(output, "recommended_strategy"):
            summary = f"Recommends {output.recommended_strategy}"
            details = {
                "recommended_strategy": output.recommended_strategy,
                "confidence": getattr(output, "confidence", None),
                "rationale": getattr(output, "rationale", [])[:2]  # First 2 rationale points
            }
        elif hasattr(output, "shortlisted_suppliers"):
            count = len(output.shortlisted_suppliers)
            summary = f"Shortlisted {count} suppliers"
            details = {
                "supplier_count": count,
                "top_choice_supplier_id": getattr(output, "top_choice_supplier_id", None)
            }
        elif hasattr(output, "negotiation_objectives"):
            count = len(output.negotiation_objectives)
            summary = f"Created negotiation plan with {count} objectives"
            details = {"objectives_count": count}
        elif hasattr(output, "rfx_sections"):
            count = len(output.rfx_sections)
            summary = f"Drafted RFx with {count} sections"
            details = {"sections_count": count}
        elif hasattr(output, "extracted_terms"):
            count = len(output.extracted_terms)
            summary = f"Extracted {count} contract terms"
            details = {"terms_count": count}
        elif hasattr(output, "rollout_steps"):
            count = len(output.rollout_steps)
            summary = f"Created implementation plan with {count} steps"
            details = {"steps_count": count}
        elif hasattr(output, "questions"):
            count = len(output.questions)
            summary = f"Requested clarification ({count} questions)"
            details = {"question_count": count}
        else:
            summary = f"Produced {output_type}"
            details = {}
        
        memory.record_agent_output(agent_name, output_type, summary, details)
    
    return memory




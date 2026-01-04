"""
Response Adapter Layer - Separates decision logic from chat narration.

PHASE 2 - OBJECTIVE B: Separate Decision Logic from Chat Narration

This module provides a clean abstraction that:
- Takes structured agent outputs + case state
- Produces natural-language chatbot responses
- Lives outside app.py
- Allows new agents/output types without rewriting UI logic

DESIGN PRINCIPLES:
- Chatbot speaks in first-person collaborative tone
- Invites human input at decision points
- Never claims autonomous authority
- Consistent style across all agent outputs
"""
from typing import Any, Optional, Dict, List
from utils.case_memory import CaseMemory


class ResponseAdapter:
    """
    Adapts structured agent outputs into natural language chat responses.
    
    This is the single point where agent outputs become human-readable text.
    All new agent types should add a handler here.
    """
    
    def __init__(self):
        # Response templates by agent output type
        self._handlers = {
            "StrategyRecommendation": self._handle_strategy,
            "SupplierShortlist": self._handle_supplier_shortlist,
            "NegotiationPlan": self._handle_negotiation_plan,
            "RFxDraft": self._handle_rfx_draft,
            "ContractExtraction": self._handle_contract_extraction,
            "ImplementationPlan": self._handle_implementation_plan,
            "ClarificationRequest": self._handle_clarification,
            "SignalAssessment": self._handle_signal_assessment,
            "OutOfScopeNotice": self._handle_out_of_scope,
        }
    
    def generate_response(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory] = None,
        user_intent: Optional[str] = None,
        waiting_for_human: bool = False,
        contradictions: Optional[List[str]] = None,
        constraint_reflection: Optional[str] = None,
        constraint_violations: Optional[List[str]] = None
    ) -> str:
        """
        Generate a natural language response from structured output.
        
        PHASE 3: Now includes mandatory constraint reflection when constraints exist.
        
        Args:
            output: The agent output (Pydantic model)
            case_state: Current case state dict
            memory: Optional CaseMemory for context
            user_intent: What the user asked
            waiting_for_human: Whether HIL is required
            contradictions: Any detected contradictions to surface
            constraint_reflection: MANDATORY reflection on user constraints (must appear before recommendation)
            constraint_violations: List of constraint violations to warn about
        
        Returns:
            Natural language response string
        """
        if output is None:
            return self._generate_no_output_response(case_state, user_intent)
        
        output_type = type(output).__name__
        handler = self._handlers.get(output_type)
        
        if handler:
            response = handler(output, case_state, memory)
        else:
            response = self._generate_fallback_response(output, output_type)
        
        # PHASE 3: MANDATORY - Prepend constraint reflection (before the recommendation)
        # This is non-negotiable: when constraints exist, they must be acknowledged
        if constraint_reflection:
            response = constraint_reflection + "\n\n---\n\n" + response
        
        # PHASE 3: Add constraint violation warnings if any
        if constraint_violations:
            response = self._add_constraint_violation_warning(response, constraint_violations)
        
        # Add contradiction warning if any
        if contradictions:
            response = self._add_contradiction_warning(response, contradictions)
        
        # Add HIL prompt if waiting for human
        if waiting_for_human:
            response = self._add_hil_prompt(response, output_type)
        
        return response
    
    def _add_constraint_violation_warning(self, response: str, violations: List[str]) -> str:
        """
        Add constraint violation warning to response.
        
        PHASE 3: This is a BLOCKING warning - constraints must be addressed.
        """
        warning = "\n\n---\n⚠️ **Constraint Compliance Issue:**\n"
        warning += "The following user preferences were not explicitly addressed:\n"
        for v in violations[:5]:
            warning += f"• {v}\n"
        warning += "\n_Please note: Your stated preferences should shape this recommendation. If the output doesn't reflect them, please let me know and I'll adjust._"
        return response + warning
    
    def _handle_strategy(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle StrategyRecommendation output."""
        parts = []
        
        # Opening
        parts.append(f"I've completed my analysis for this case and have a recommendation ready.")
        
        # Core recommendation
        strategy = getattr(output, "recommended_strategy", "Unknown")
        confidence = getattr(output, "confidence", 0)
        confidence_pct = int(confidence * 100) if confidence else 0
        
        parts.append(f"\n\n**Recommended Strategy: {strategy}** (confidence: {confidence_pct}%)")
        
        # Rationale
        rationale = getattr(output, "rationale", [])
        if rationale:
            parts.append("\n\n**Why this recommendation:**")
            for reason in rationale[:3]:
                parts.append(f"\n• {reason}")
        
        # Risk assessment
        risk = getattr(output, "risk_assessment", "")
        if risk:
            parts.append(f"\n\n**Risk considerations:** {risk}")
        
        # Memory context (if available)
        if memory and memory.human_decisions:
            parts.append(f"\n\n_This builds on your previous decisions: {memory.human_decisions[-1]}_")
        
        # Closing - invite collaboration
        parts.append("\n\nI believe this approach aligns with the case objectives, but I'd value your perspective. ")
        parts.append("Would you like me to explain the alternatives, or shall we proceed with this strategy?")
        
        return "".join(parts)
    
    def _handle_supplier_shortlist(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle SupplierShortlist output."""
        parts = []
        
        suppliers = getattr(output, "shortlisted_suppliers", [])
        count = len(suppliers)
        top_choice = getattr(output, "top_choice_supplier_id", None)
        
        parts.append(f"I've evaluated the supplier landscape and identified **{count} qualified suppliers** for this category.")
        
        if top_choice:
            parts.append(f"\n\n**Top recommendation:** {top_choice}")
        
        # Brief comparison
        comparison = getattr(output, "comparison_summary", "")
        if comparison:
            parts.append(f"\n\n**Comparison:** {comparison[:200]}")
        
        # Show top 3 suppliers
        if suppliers[:3]:
            parts.append("\n\n**Shortlisted suppliers:**")
            for s in suppliers[:3]:
                name = s.get("name", s.get("supplier_id", "Unknown"))
                score = s.get("score", "N/A")
                parts.append(f"\n• {name} (score: {score})")
        
        # Invitation to proceed
        parts.append("\n\nThe scores reflect performance data and category requirements. ")
        parts.append("You have the final say on supplier selection. Would you like a detailed comparison, or shall we move to negotiation planning?")
        
        return "".join(parts)
    
    def _handle_negotiation_plan(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle NegotiationPlan output."""
        parts = []
        
        objectives = getattr(output, "negotiation_objectives", [])
        leverage = getattr(output, "leverage_points", [])
        supplier_id = getattr(output, "supplier_id", "the selected supplier")
        
        parts.append(f"I've prepared a negotiation plan for **{supplier_id}** with **{len(objectives)} key objectives**.")
        
        if objectives[:3]:
            parts.append("\n\n**Objectives:**")
            for obj in objectives[:3]:
                parts.append(f"\n• {obj}")
        
        if leverage[:2]:
            parts.append("\n\n**Leverage points I've identified:**")
            for lev in leverage[:2]:
                parts.append(f"\n• {lev}")
        
        # Governance reminder
        parts.append("\n\n**Important:** This plan is advisory. I don't have authority to conduct negotiations or make commitments. ")
        parts.append("Your approval is required before engaging with the supplier. Shall I refine any aspect of this plan?")
        
        return "".join(parts)
    
    def _handle_rfx_draft(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle RFxDraft output."""
        parts = []
        
        sections = getattr(output, "rfx_sections", {})
        completeness = getattr(output, "completeness_check", {})
        
        parts.append(f"I've drafted the RFx document with **{len(sections)} sections** based on category templates.")
        
        if sections:
            parts.append("\n\n**Sections included:**")
            for section in list(sections.keys())[:5]:
                parts.append(f"\n• {section}")
        
        # Completeness check
        all_complete = completeness.get("all_sections_filled", False)
        if all_complete:
            parts.append("\n\n✓ All required sections have been filled.")
        else:
            parts.append("\n\n⚠️ Some sections may need additional review.")
        
        parts.append("\n\nThis draft follows standard templates but **commercial terms require your review and legal approval**. ")
        parts.append("Would you like me to adjust any section before finalizing?")
        
        return "".join(parts)
    
    def _handle_contract_extraction(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle ContractExtraction output."""
        parts = []
        
        terms = getattr(output, "extracted_terms", {})
        validation = getattr(output, "validation_results", {})
        inconsistencies = getattr(output, "inconsistencies", [])
        
        parts.append(f"I've extracted **{len(terms)} contract terms** from the agreement.")
        
        if terms:
            parts.append("\n\n**Key terms identified:**")
            for term_name in list(terms.keys())[:4]:
                parts.append(f"\n• {term_name}")
        
        # Flag issues
        if inconsistencies:
            parts.append(f"\n\n⚠️ **Issues requiring your attention:** {len(inconsistencies)} inconsistencies detected")
            for issue in inconsistencies[:2]:
                parts.append(f"\n• {issue}")
        
        parts.append("\n\nThese extractions are for reference—**legal review is required** before execution. ")
        parts.append("Should I proceed to implementation planning, or do you need clarification on any terms?")
        
        return "".join(parts)
    
    def _handle_implementation_plan(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle ImplementationPlan output."""
        parts = []
        
        steps = getattr(output, "rollout_steps", [])
        savings = getattr(output, "projected_savings", None)
        
        parts.append(f"I've created an implementation plan with **{len(steps)} rollout steps**.")
        
        if savings:
            parts.append(f"\n\n**Projected savings:** ${savings:,.2f}")
        
        if steps[:4]:
            parts.append("\n\n**Rollout sequence:**")
            for step in steps[:4]:
                step_name = step.get("step", "Step")
                timeline = step.get("timeline", "TBD")
                parts.append(f"\n• {step_name} ({timeline})")
        
        explanation = getattr(output, "explanation", "")
        if explanation:
            parts.append(f"\n\n**Impact summary:** {explanation[:150]}")
        
        parts.append("\n\nThese steps are based on standard playbooks. Your sign-off is required before proceeding with implementation.")
        
        return "".join(parts)
    
    def _handle_clarification(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle ClarificationRequest output."""
        parts = []
        
        reason = getattr(output, "reason", "Additional information needed")
        questions = getattr(output, "questions", [])
        options = getattr(output, "suggested_options", [])
        
        parts.append(f"I need some additional information to proceed effectively.\n\n**Why I'm asking:** {reason}")
        
        if questions:
            parts.append("\n\n**Questions:**")
            for i, q in enumerate(questions, 1):
                parts.append(f"\n{i}. {q}")
        
        if options:
            parts.append("\n\n**Suggested options:**")
            for opt in options:
                parts.append(f"\n• {opt}")
        
        parts.append("\n\nPlease share your thoughts, and I'll incorporate them into the analysis.")
        
        return "".join(parts)
    
    def _handle_signal_assessment(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle SignalAssessment output."""
        parts = []
        
        assessment = getattr(output, "assessment", "")
        recommended_action = getattr(output, "recommended_action", "")
        urgency = getattr(output, "urgency_score", 5)
        
        parts.append(f"I've assessed the signal. Here's what I found:\n\n**Assessment:** {assessment}")
        parts.append(f"\n\n**Suggested action:** {recommended_action}")
        parts.append(f"\n**Urgency level:** {urgency}/10")
        
        rationale = getattr(output, "rationale", [])
        if rationale:
            parts.append("\n\n**Key factors:**")
            for r in rationale[:3]:
                parts.append(f"\n• {r}")
        
        parts.append("\n\nThis assessment is based on available data. Would you like to create a case to address this signal?")
        
        return "".join(parts)
    
    def _handle_out_of_scope(
        self,
        output: Any,
        case_state: Dict[str, Any],
        memory: Optional[CaseMemory]
    ) -> str:
        """Handle OutOfScopeNotice output."""
        parts = []
        
        requested = getattr(output, "requested_action", "the requested action")
        reason = getattr(output, "reason", "falls outside current capabilities")
        alternatives = getattr(output, "alternative_actions", [])
        
        parts.append(f"I can't complete **{requested}** at this time.\n\n**Reason:** {reason}")
        
        if alternatives:
            parts.append("\n\n**What I can do instead:**")
            for alt in alternatives:
                parts.append(f"\n• {alt}")
        
        next_steps = getattr(output, "suggested_next_steps", [])
        if next_steps:
            parts.append("\n\n**Suggested next steps:**")
            for step in next_steps:
                parts.append(f"\n• {step}")
        
        return "".join(parts)
    
    def _generate_no_output_response(
        self,
        case_state: Dict[str, Any],
        user_intent: Optional[str]
    ) -> str:
        """Generate response when no agent output is available."""
        dtp_stage = case_state.get("dtp_stage", "DTP-01")
        status = case_state.get("status", "In Progress")
        
        if status == "Waiting for Human Decision":
            return "I'm waiting for your decision on the previous recommendation. Please let me know if you'd like to approve, reject, or need more information."
        
        return f"I'm ready to help with this case (currently at {dtp_stage}). What would you like me to focus on?"
    
    def _generate_fallback_response(self, output: Any, output_type: str) -> str:
        """Fallback for unknown output types."""
        return f"I've completed the analysis and produced a {output_type}. Please review the details in the case view."
    
    def _add_contradiction_warning(self, response: str, contradictions: List[str]) -> str:
        """Add contradiction warning to response."""
        warning = "\n\n---\n⚠️ **Heads up:** I've detected some conflicting information that needs your attention:\n"
        for c in contradictions[:3]:
            warning += f"• {c}\n"
        warning += "\nPlease review and let me know how to proceed."
        return response + warning
    
    def _add_hil_prompt(self, response: str, output_type: str) -> str:
        """Add human-in-the-loop prompt."""
        prompt = "\n\n---\n👤 **Your decision needed:** "
        
        if output_type == "StrategyRecommendation":
            prompt += "Please confirm whether to proceed with this strategy (approve/reject), or let me know if you'd like changes."
        elif output_type == "SupplierShortlist":
            prompt += "Please confirm the supplier selection before we proceed to negotiation."
        elif output_type == "NegotiationPlan":
            prompt += "Please approve the negotiation plan before I finalize it."
        else:
            prompt += "Please review and let me know if you approve or need changes."
        
        return response + prompt
    
    # Helper for status queries
    def generate_status_response(self, case_state: Dict[str, Any], memory: Optional[CaseMemory] = None) -> str:
        """Generate a status summary response."""
        parts = []
        
        case_id = case_state.get("case_id", "this case")
        dtp_stage = case_state.get("dtp_stage", "DTP-01")
        status = case_state.get("status", "In Progress")
        
        parts.append(f"Here's where we stand with **{case_id}**:")
        parts.append(f"\n\n**Current stage:** {dtp_stage}")
        parts.append(f"\n**Status:** {status}")
        
        if memory:
            if memory.current_strategy:
                parts.append(f"\n**Strategy direction:** {memory.current_strategy}")
            if memory.current_supplier_choice:
                parts.append(f"\n**Lead supplier:** {memory.current_supplier_choice}")
            if memory.human_decisions:
                parts.append(f"\n**Recent decisions:** {memory.human_decisions[-1]}")
            if memory.active_contradictions:
                parts.append(f"\n⚠️ **Unresolved conflicts:** {len(memory.active_contradictions)}")
        
        parts.append("\n\nWhat would you like to focus on next?")
        
        return "".join(parts)


# Singleton instance for easy access
_response_adapter = None

def get_response_adapter() -> ResponseAdapter:
    """Get the singleton ResponseAdapter instance."""
    global _response_adapter
    if _response_adapter is None:
        _response_adapter = ResponseAdapter()
    return _response_adapter





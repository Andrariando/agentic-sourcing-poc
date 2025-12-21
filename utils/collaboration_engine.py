"""
Collaboration Response Engine.

Generates collaborative, human-like responses that:
- Use CaseMemory + current DTP stage
- Frame options without recommendation
- Ask clarifying questions appropriate to the DTP stage
- Signal readiness to execute only if user wants

Design Principles:
- Bypasses Supervisor and LangGraph entirely
- First-person, collaborative tone
- Curious, not directive
- Consultant-operator hybrid (MIT-style)
- Never says "collaboration mode" explicitly
"""
from typing import Dict, Any, Optional, List
import random
from utils.collaboration_templates import (
    get_collaboration_template,
    get_stage_questions,
    get_stage_tradeoffs,
    get_option_framing,
    get_transition_prompt,
)
from utils.case_memory import CaseMemory
from utils.dtp_stages import get_dtp_stage_display


class CollaborationEngine:
    """
    Generates collaborative responses based on case context and DTP stage.
    
    This engine does NOT:
    - Advance DTP stage
    - Invoke LangGraph
    - Call decision agents
    - Request approvals
    
    This engine DOES:
    - Reference prior CaseMemory
    - Mention possible options (without recommending)
    - Ask 1-2 high-quality, DTP-specific questions
    - Surface tensions, risks, or tradeoffs
    """
    
    def __init__(self):
        # Collaborative opening phrases (never directive)
        self.openings = [
            "Let's think through this together.",
            "Good question — there's a bit to unpack here.",
            "That's worth exploring before we move forward.",
            "Let me share what I'm seeing, and then I'd love your input.",
            "Before we commit to a direction, let's consider a few things.",
            "There are a couple of angles to consider here.",
            "I want to make sure we're aligned before proceeding.",
        ]
        
        # Transition phrases (for offering execution)
        self.execution_offers = [
            "When you're ready, I can run the analysis and provide a structured recommendation.",
            "If you'd like, I can now proceed with the formal evaluation.",
            "Just let me know when you want me to move this forward.",
            "Once you're comfortable, say the word and I'll proceed.",
        ]
    
    def generate_response(
        self,
        user_input: str,
        case_id: str,
        dtp_stage: str,
        case_memory: Optional[CaseMemory] = None,
        case_context: Optional[Dict[str, Any]] = None,
        latest_agent_output: Any = None,
    ) -> str:
        """
        Generate a collaborative response for the given context.
        
        Args:
            user_input: The user's message
            case_id: Current case ID
            dtp_stage: Current DTP stage (e.g., "DTP-01")
            case_memory: Optional CaseMemory object for context
            case_context: Optional additional case context
            latest_agent_output: Optional latest agent output for reference
        
        Returns:
            A collaborative, human-like response string
        """
        template = get_collaboration_template(dtp_stage)
        stage_display = get_dtp_stage_display(dtp_stage)
        
        # Build response parts
        parts = []
        
        # 1. Opening - acknowledge and engage
        parts.append(self._generate_opening(user_input, dtp_stage, case_memory))
        
        # 2. Context reference - what we know
        if case_memory or case_context or latest_agent_output:
            context_ref = self._reference_context(
                case_memory, case_context, latest_agent_output, dtp_stage
            )
            if context_ref:
                parts.append(context_ref)
        
        # 3. Option framing - what paths exist (without recommending)
        parts.append(self._frame_options(dtp_stage, user_input))
        
        # 4. Clarifying questions - DTP-specific
        parts.append(self._ask_questions(dtp_stage, user_input, case_memory))
        
        # 5. Transition offer - signal readiness to execute
        parts.append(self._offer_transition(dtp_stage))
        
        return "\n\n".join(parts)
    
    def _generate_opening(
        self,
        user_input: str,
        dtp_stage: str,
        case_memory: Optional[CaseMemory]
    ) -> str:
        """Generate a collaborative opening."""
        stage_display = get_dtp_stage_display(dtp_stage)
        opening = random.choice(self.openings)
        
        # Acknowledge specific user concerns if detected
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ["risk", "concern", "worry", "uncertain"]):
            return f"I hear your concern — it's important to think through the risks here. {opening}"
        elif any(word in user_lower for word in ["option", "alternative", "choice"]):
            return f"You're right to explore the options. {opening}"
        elif any(word in user_lower for word in ["think", "help", "understand"]):
            return opening
        elif any(word in user_lower for word in ["what", "how", "why"]):
            return f"That's a good question to ask at the **{stage_display}** stage. {opening}"
        else:
            return f"We're at the **{stage_display}** stage ({dtp_stage}). {opening}"
    
    def _reference_context(
        self,
        case_memory: Optional[CaseMemory],
        case_context: Optional[Dict[str, Any]],
        latest_agent_output: Any,
        dtp_stage: str
    ) -> Optional[str]:
        """Reference what we already know from CaseMemory and context."""
        insights = []
        
        # Pull from CaseMemory if available
        if case_memory:
            # Check for prior strategy decisions
            if case_memory.recommended_strategy:
                insights.append(
                    f"We've been leaning toward a **{case_memory.recommended_strategy}** approach"
                )
            
            # Check for key decisions
            if case_memory.key_decisions:
                recent = case_memory.key_decisions[-1] if case_memory.key_decisions else None
                if recent:
                    insights.append(f"Previously, we decided: _{recent}_")
            
            # Check for flagged risks
            if case_memory.flagged_risks:
                risks = case_memory.flagged_risks[:2]
                if risks:
                    insights.append(f"Key risks on the radar: {', '.join(risks)}")
            
            # Check for active contradictions
            if case_memory.active_contradictions:
                insights.append(
                    f"⚠️ There's some conflicting information we should address: "
                    f"{case_memory.active_contradictions[0]}"
                )
        
        # Pull from latest agent output if available
        if latest_agent_output:
            output_type = type(latest_agent_output).__name__
            if output_type == "StrategyRecommendation":
                if hasattr(latest_agent_output, "recommended_strategy"):
                    insights.append(
                        f"The latest analysis suggests **{latest_agent_output.recommended_strategy}** "
                        f"(confidence: {latest_agent_output.confidence:.0%})"
                    )
            elif output_type == "SupplierShortlist":
                count = len(getattr(latest_agent_output, "shortlisted_suppliers", []))
                if count > 0:
                    insights.append(f"We have **{count} suppliers** in the running")
        
        if insights:
            return "**What we know so far:**\n" + "\n".join(f"- {i}" for i in insights)
        return None
    
    def _frame_options(self, dtp_stage: str, user_input: str) -> str:
        """Frame the available options without recommending."""
        base_framing = get_option_framing(dtp_stage)
        
        # Add some nuance based on user input
        user_lower = user_input.lower()
        
        if "tradeoff" in user_lower or "trade-off" in user_lower:
            return (
                f"{base_framing}\n\n"
                "Each path has tradeoffs — there's no perfect answer, "
                "just the right fit for your priorities."
            )
        elif "risk" in user_lower:
            return (
                f"{base_framing}\n\n"
                "Some paths carry more risk than others. "
                "I can help you think through which risks are acceptable."
            )
        else:
            return base_framing
    
    def _ask_questions(
        self,
        dtp_stage: str,
        user_input: str,
        case_memory: Optional[CaseMemory]
    ) -> str:
        """Ask 1-2 high-quality, DTP-specific questions."""
        # Get stage-appropriate questions
        questions = get_stage_questions(dtp_stage, count=3)
        tradeoffs = get_stage_tradeoffs(dtp_stage, count=2)
        
        # Select questions that haven't been answered yet
        # (In a full implementation, we'd check CaseMemory for answered questions)
        selected_questions = random.sample(questions, min(2, len(questions)))
        
        # Possibly include a tradeoff prompt
        user_lower = user_input.lower()
        if any(word in user_lower for word in ["compare", "versus", "vs", "between", "difference"]):
            tradeoff = random.choice(tradeoffs) if tradeoffs else None
            if tradeoff:
                return (
                    f"**A few things I'd like to understand:**\n"
                    f"- {selected_questions[0]}\n\n"
                    f"Also worth considering: _{tradeoff}_"
                )
        
        # Standard question format
        return (
            "**Before we proceed, I'd like to understand:**\n" +
            "\n".join(f"- {q}" for q in selected_questions)
        )
    
    def _offer_transition(self, dtp_stage: str) -> str:
        """Offer transition to execution mode."""
        transition = get_transition_prompt(dtp_stage)
        return f"---\n💡 {transition}"
    
    def generate_interruption_response(
        self,
        user_input: str,
        dtp_stage: str,
        case_memory: Optional[CaseMemory] = None,
    ) -> str:
        """
        Generate response for mid-stage interruption.
        User has paused execution to reconsider.
        """
        stage_display = get_dtp_stage_display(dtp_stage)
        
        response = (
            f"No problem — let's pause and make sure we're on the right track.\n\n"
            f"We're at the **{stage_display}** stage. "
            f"What's on your mind? I can help you think through any concerns before we continue."
        )
        
        # Add context if available
        if case_memory and case_memory.key_decisions:
            response += (
                f"\n\nFor reference, here's what we've established so far:\n"
                f"- {case_memory.key_decisions[-1]}"
            )
        
        response += (
            "\n\n_Take your time — when you're ready to proceed, just let me know._"
        )
        
        return response
    
    def generate_clarification_response(
        self,
        topic: str,
        dtp_stage: str,
        case_memory: Optional[CaseMemory] = None,
    ) -> str:
        """
        Generate response for user seeking clarification on a specific topic.
        """
        template = get_collaboration_template(dtp_stage)
        
        # Find relevant focus areas
        relevant_focus = [f for f in template.focus_areas if topic.lower() in f.lower()]
        if not relevant_focus:
            relevant_focus = template.focus_areas[:2]
        
        response = (
            f"Good question. At this stage, **{topic}** relates to:\n\n" +
            "\n".join(f"- {f}" for f in relevant_focus) +
            "\n\nWould you like me to elaborate on any of these?"
        )
        
        return response


# Singleton instance
_collaboration_engine: Optional[CollaborationEngine] = None


def get_collaboration_engine() -> CollaborationEngine:
    """Get or create the collaboration engine singleton."""
    global _collaboration_engine
    if _collaboration_engine is None:
        _collaboration_engine = CollaborationEngine()
    return _collaboration_engine

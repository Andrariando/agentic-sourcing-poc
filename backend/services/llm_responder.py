"""
LLM Responder Service - Generates natural responses using LLM.

This service is the core of the GPT-like experience. It:
1. Analyzes user intent using LLM (not regex/rules)
2. Generates natural responses (not templates)
3. Decides when to call agents vs answer directly
4. Asks for more data when needed
5. Maintains conversation context
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class LLMResponder:
    """
    Generates natural, ChatGPT-like responses using LLM.
    
    This replaces the template-based ResponseAdapter with dynamic LLM generation.
    """
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7):
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        self.analysis_llm = ChatOpenAI(model=model, temperature=0)  # Deterministic for analysis
    
    def analyze_intent(
        self,
        user_message: str,
        case_context: Dict[str, Any],
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to understand what the user wants.
        
        Returns:
            {
                "needs_agent": bool,  # Should we run a specialist agent?
                "agent_hint": str,    # Which agent might be needed
                "is_approval": bool,  # Is user approving something?
                "is_rejection": bool, # Is user rejecting something?
                "needs_data": bool,   # Do we need more info from user?
                "missing_info": str,  # What info is missing
                "can_answer_directly": bool,  # Can LLM answer without agent?
                "intent_summary": str  # Brief summary of user intent
            }
        """
        history_text = self._format_history(conversation_history) if conversation_history else "No prior conversation."
        
        prompt = f"""You are analyzing a user message in a procurement copilot system.

CASE CONTEXT:
- Case ID: {case_context.get('case_id', 'Unknown')}
- Name: {case_context.get('case_name', '')}
- Summary: {case_context.get('summary', '')[:500]}...
- Key Findings: {str(case_context.get('key_findings', []))[:500]}...
- DTP Stage: {case_context.get('dtp_stage', 'DTP-01')}
- Category: {case_context.get('category_id', 'Unknown')}
- Status: {case_context.get('status', 'Unknown')}
- Has Agent Output: {bool(case_context.get('latest_agent_output'))}
- Waiting for Human: {case_context.get('waiting_for_human', False)}

CONVERSATION HISTORY:
{history_text}

USER MESSAGE: "{user_message}"

CLASSIFICATION RULES:
1. QUESTION (can_answer_directly=true, needs_agent=false): User is ASKING about something. Examples:
   - "What are the signals?" -> QUESTION (explain existing data)
   - "What contract expiry do we have?" -> QUESTION (explain existing data)
   - "Why did you recommend this?" -> QUESTION (explain previous output)
   - "What are the risks?" -> QUESTION (explain/discuss)

2. ACTION REQUEST (needs_agent=true, can_answer_directly=false): User wants NEW WORK done, including SEARCHING or STRATEGY. Examples:
   - "Recommend a strategy" -> ACTION (run Strategy Agent)
   - "Score the suppliers" -> ACTION (run Supplier Evaluation)
   - "Draft an RFP" -> ACTION (run RFx Agent)
   - "Analyze the case" -> ACTION (run analysis)
   - "What are my options?" -> ACTION (run Strategy Agent)
   - "Find me cheap alternatives" -> ACTION (run Strategy/Sourcing Agent)
   - "I want suppliers other than Microsoft" -> ACTION (run Strategy/Sourcing Agent)

3. APPROVAL (is_approval=true): User is confirming/agreeing. Examples:
   - "Approve", "Yes", "Proceed", "Looks good", "Let's do it"

4. REJECTION (is_rejection=true): User is declining. Examples:
   - "Reject", "No", "I don't agree", "Change it"

5. PROGRESSION (is_progression=true): User wants to advance stage but is asking "How?". Examples:
   - "How do I proceed?", "Move to next stage", "What's next?", "Advance to DTP-02"
   (Set is_progression=true, needs_agent=false, can_answer_directly=false)

Respond with JSON only:
{{
    "needs_agent": true/false,  // TRUE ONLY if user requests NEW WORK (not questions)
    "agent_hint": "string",     // If needs_agent, which one?
    "is_approval": true/false,  // Is user approving?
    "is_rejection": true/false, // Is user rejecting?
    "is_progression": true/false, // Is user asking to move to next stage?
    "needs_data": true/false,   // Do we need more info from user?
    "missing_info": "string",   // If needs_data, what's missing?
    "can_answer_directly": true/false,  // TRUE if this is a QUESTION we can answer
    "intent_summary": "string"  // One sentence summary
}}

IMPORTANT: If the user is ASKING a question (what, why, how, which, etc.), set can_answer_directly=true and needs_agent=false.

Respond with valid JSON only, no explanation."""

        try:
            # Revert to standard invoke to avoid potential config issues
            # We enforce JSON in prompt which is usually sufficient for gpt-4o-mini
            response = self.analysis_llm.invoke([HumanMessage(content=prompt)])
            
            # Clean up response content in case of markdown fences
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
                
            result = json.loads(content.strip())
            logger.info(f"[LLMResponder] Intent analysis: {result}")
            return result
        except Exception as e:
            logger.error(f"[LLMResponder] Intent analysis failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback: DO NOT default to agent if it's likely a question
            # Check for question marks or question words
            if "?" in user_message or any(w in user_message.lower() for w in ["what", "how", "why", "when"]):
                return {
                    "needs_agent": False,
                    "agent_hint": "",
                    "is_approval": False,
                    "is_rejection": False,
                    "is_progression": False,
                    "needs_data": False,
                    "missing_info": "",
                    "can_answer_directly": True,
                    "intent_summary": "Fallback: Question detected"
                }
            return {
                "needs_agent": True,
                "agent_hint": "Strategy",
                "is_approval": False,
                "is_rejection": False,
                "is_progression": False,
                "needs_data": False,
                "missing_info": "",
                "can_answer_directly": False,
                "intent_summary": "Fallback: Default to agent"
            }
    
    def generate_response(
        self,
        user_message: str,
        case_context: Dict[str, Any],
        agent_output: Any = None,
        conversation_history: List[Dict[str, str]] = None,
        action_taken: str = None
    ) -> str:
        """
        Generate a natural, ChatGPT-like response.
        ...
        """
        history_text = self._format_history(conversation_history) if conversation_history else ""
        output_text = self._format_agent_output(agent_output) if agent_output else "No agent analysis available yet."
        
        system_prompt = """You are a friendly, professional procurement copilot assistant. 
You help users with sourcing decisions, supplier evaluation, negotiations, and contracts.

PERSONALITY:
- Be conversational and natural, like ChatGPT
- Be concise but informative
- Never use templated or robotic language
- If something went wrong, acknowledge it honestly
- Proactively offer helpful next steps
- If you don't have enough information, ask for it naturally (don't draft an email)
- NEVER generate a "Subject:" line or email template unless explicitly asked to draft an email.
- Answer questions directly.

RULES:
- Use the agent output to inform your response, but express it naturally.
- DO NOT just repeat or summarize the agent output if the user requested something specific that isn't in the output. 
- If the user asks a specific question (e.g., "What are savings?") and the data isn't in the Agent Output, say "I don't have specific savings data in the current analysis." then offer to find it.
- If the user approved something, acknowledge it warmly and explain next steps.
- If you need more data, ask specific questions.
- Always be helpful and action-oriented."""

        user_prompt = f"""CASE CONTEXT:
- Case ID: {case_context.get('case_id', 'Unknown')}
- Name: {case_context.get('case_name', 'Unknown')}
- Summary: {case_context.get('summary', '')}
- Key Findings: {str(case_context.get('key_findings', []))}
- DTP Stage: {case_context.get('dtp_stage', 'DTP-01')}
- Category: {case_context.get('category_id', 'Unknown')}
- Status: {case_context.get('status', 'Unknown')}

{f"CONVERSATION HISTORY:{chr(10)}{history_text}" if history_text else ""}

{f"ACTION TAKEN: {action_taken}" if action_taken else ""}

AGENT OUTPUT/ANALYSIS:
{output_text}

USER MESSAGE: "{user_message}"

Generate a natural, helpful response:"""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            return response.content
        except Exception as e:
            logger.error(f"[LLMResponder] Response generation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"I apologize, but I encountered an issue processing your request. Could you please try rephrasing or let me know more about what you'd like to do?"
    
    def generate_approval_response(
        self,
        result: Dict[str, Any],
        case_context: Dict[str, Any]
    ) -> str:
        """Generate a natural response for approval actions."""
        success = result.get("success", False)
        new_stage = result.get("new_dtp_stage", case_context.get("dtp_stage"))
        
        if success:
            return self.generate_response(
                user_message="I approve",
                case_context={**case_context, "dtp_stage": new_stage},
                action_taken=f"User approved. Case advanced from {case_context.get('dtp_stage')} to {new_stage}."
            )
        else:
            error = result.get("message", "Unknown error")
            return self.generate_response(
                user_message="I approve",
                case_context=case_context,
                action_taken=f"Approval failed: {error}"
            )
    
    def generate_rejection_response(
        self,
        case_context: Dict[str, Any],
        reason: str = None
    ) -> str:
        """Generate a natural response for rejection/revision requests."""
        return self.generate_response(
            user_message="I reject this",
            case_context=case_context,
            action_taken=f"User rejected with feedback: {reason or 'No specific feedback provided'}"
        )
    
    def generate_data_request(
        self,
        missing_info: str,
        case_context: Dict[str, Any]
    ) -> str:
        """Generate a natural request for missing data."""
        prompt = f"""The user asked for help but we need more information.

Missing: {missing_info}
Case Context: {case_context.get('category_id', 'General')} procurement

Generate a friendly, specific request for the missing information. Be conversational."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            logger.error(f"[LLMResponder] Data request failed: {e}")
            return f"I'd love to help! Could you please provide more details about {missing_info}?"
    
    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Format conversation history for prompt."""
        if not history:
            return ""
        
        formatted = []
        for msg in history[-5:]:  # Last 5 messages for context
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")[:500]  # Truncate long messages
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)
    
    def _format_agent_output(self, output: Any) -> str:
        """Format agent output for prompt."""
        if output is None:
            return "No analysis available."
        
        if isinstance(output, dict):
            # Extract key fields for common output types
            formatted = []
            
            if "recommended_strategy" in output:
                formatted.append(f"Recommended Strategy: {output['recommended_strategy']}")
                if "confidence" in output:
                    formatted.append(f"Confidence: {int(output['confidence'] * 100)}%")
                if "rationale" in output:
                    rationale = output["rationale"]
                    if isinstance(rationale, list):
                        formatted.append("Rationale: " + ", ".join(rationale[:3]))
                    else:
                        formatted.append(f"Rationale: {rationale}")
                if "risk_assessment" in output:
                    formatted.append(f"Risk: {output['risk_assessment']}")
            
            elif "shortlisted_suppliers" in output:
                suppliers = output["shortlisted_suppliers"]
                formatted.append(f"Found {len(suppliers)} suppliers")
                if output.get("top_choice_supplier_id"):
                    formatted.append(f"Top choice: {output['top_choice_supplier_id']}")
            
            elif "rfx_type" in output:
                formatted.append(f"RFx Type: {output['rfx_type']}")
                if "completeness" in output:
                    formatted.append(f"Completeness: {output['completeness']}%")
            
            else:
                # Generic formatting
                for key, value in list(output.items())[:5]:
                    if value and not key.startswith("_"):
                        formatted.append(f"{key}: {str(value)[:100]}")
            
            return "\n".join(formatted) if formatted else str(output)[:500]
        
        elif hasattr(output, "model_dump"):
            # Pydantic model
            return self._format_agent_output(output.model_dump())
        
        else:
            return str(output)[:500]


# Singleton instance
_llm_responder = None

def get_llm_responder() -> LLMResponder:
    """Get or create LLM responder instance."""
    global _llm_responder
    if _llm_responder is None:
        _llm_responder = LLMResponder()
    return _llm_responder

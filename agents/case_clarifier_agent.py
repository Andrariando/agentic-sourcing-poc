"""
Case Clarifier Agent - Generates targeted questions for human collaboration.

This agent is LLM-powered and is invoked by the Supervisor when:
- Confidence score < threshold
- Required inputs are missing
- Policy ambiguity exists
- Multiple valid paths exist

The Supervisor remains deterministic and delegates question generation to this agent.
"""
from typing import Dict, Any, Optional, List
from utils.schemas import (
    ClarificationRequest, CaseSummary, StrategyRecommendation,
    SupplierShortlist, NegotiationPlan, SignalAssessment
)
from agents.base_agent import BaseAgent
import json


class CaseClarifierAgent(BaseAgent):
    """
    Case Clarifier Agent - generates targeted questions for humans.
    Only responsibility: question generation and clarification.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("CaseClarifier", tier)
        self.confidence_threshold_low = 0.6
        self.confidence_threshold_medium = 0.8
    
    def request_clarification(
        self,
        case_summary: CaseSummary,
        latest_output: Any,
        context: Dict[str, Any],
        use_cache: bool = True
    ) -> tuple[ClarificationRequest, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Generate clarification request based on context.
        
        Args:
            case_summary: Current case summary
            latest_output: Latest agent output (if any)
            context: Additional context (confidence, missing fields, policy ambiguity, etc.)
        
        Returns:
            (clarification_request, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "clarification_request",
                case_summary,
                additional_inputs=context
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # Build prompt based on context
        reason = context.get("reason", "Information needed for decision")
        confidence = context.get("confidence", None)
        missing_fields = context.get("missing_fields", [])
        policy_ambiguity = context.get("policy_ambiguity", None)
        multiple_paths = context.get("multiple_paths", [])
        
        prompt = self._build_clarification_prompt(
            case_summary, latest_output, reason, confidence,
            missing_fields, policy_ambiguity, multiple_paths
        )
        
        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "latest_output_type": type(latest_output).__name__ if latest_output else None,
            "context": context
        }
        
        try:
            clarification, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, ClarificationRequest, retry_on_invalid=True
            )
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    "clarification_request",
                    case_summary,
                    additional_inputs=context
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (clarification, llm_input_payload, output_dict))
            
            return clarification, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(
                ClarificationRequest, case_summary.case_id, case_summary.category_id, reason
            ), llm_input_payload, {}, 0, 0
    
    def _build_clarification_prompt(
        self,
        case_summary: CaseSummary,
        latest_output: Any,
        reason: str,
        confidence: Optional[float],
        missing_fields: List[str],
        policy_ambiguity: Optional[str],
        multiple_paths: List[str]
    ) -> str:
        """Build prompt for clarification request generation."""
        
        output_description = "None"
        if latest_output:
            if isinstance(latest_output, StrategyRecommendation):
                output_description = f"Strategy recommendation: {latest_output.recommended_strategy} (confidence: {latest_output.confidence:.2f})"
            elif isinstance(latest_output, SupplierShortlist):
                output_description = f"Supplier shortlist with {len(latest_output.shortlisted_suppliers)} suppliers"
            elif isinstance(latest_output, NegotiationPlan):
                output_description = f"Negotiation plan for supplier {latest_output.supplier_id}"
            elif isinstance(latest_output, SignalAssessment):
                output_description = f"Signal assessment: {latest_output.recommended_action} (confidence: {latest_output.confidence:.2f})"
        
        prompt = f"""You are a Case Clarifier Agent for dynamic sourcing pipelines.

Your ONLY responsibility is to generate targeted, actionable questions for humans to help resolve ambiguity or gather missing information.

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Latest Agent Output:
{output_description}

Clarification Context:
- Reason: {reason}
- Confidence: {confidence if confidence is not None else 'Not specified'}
- Missing Fields: {', '.join(missing_fields) if missing_fields else 'None'}
- Policy Ambiguity: {policy_ambiguity if policy_ambiguity else 'None'}
- Multiple Valid Paths: {', '.join(multiple_paths) if multiple_paths else 'None'}

Your task: Generate a structured clarification request that:
1. Clearly explains WHY clarification is needed
2. Asks SPECIFIC, actionable questions (not vague or open-ended)
3. Provides suggested options when appropriate (to guide the human)
4. Lists what information is missing or ambiguous

IMPORTANT CONSTRAINTS:
- Questions must be specific and answerable
- Do not ask questions that require extensive research
- Focus on decision-making information, not general knowledge
- Suggested options should be concrete choices, not abstract concepts

Respond with a JSON object matching this EXACT schema:
{{
  "reason": "Need clarification on budget constraints before proceeding with supplier evaluation",
  "questions": ["What is the maximum budget for this category?", "Are there preferred suppliers we should prioritize?", "What is the timeline for making a decision?"],
  "suggested_options": ["Proceed with current budget estimates", "Wait for finance approval", "Explore cost reduction options first"],
  "missing_information": ["Budget allocation", "Stakeholder preferences"],
  "context_summary": "This case involves a contract renewal decision with multiple viable options requiring stakeholder input"
}}

IMPORTANT: All list fields must contain simple strings, not objects. If there are no suggested options, use an empty array [] not null.

Provide ONLY valid JSON, no markdown formatting."""
        
        return prompt
    
    def create_fallback_output(
        self,
        schema: type,
        case_id: str,
        category_id: str,
        reason: str = "Information needed"
    ) -> ClarificationRequest:
        """Fallback output when LLM fails"""
        return ClarificationRequest(
            reason=reason,
            questions=["Please provide additional context for this case"],
            suggested_options=None,
            missing_information=[],
            context_summary=f"Case {case_id} for category {category_id} requires clarification"
        )






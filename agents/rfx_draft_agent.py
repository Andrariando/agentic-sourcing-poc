"""
RFx Draft Agent (DTP-03) - Table 3 alignment.

Per Table 3:
- Assembles RFx draft using templates, past examples, and structured generation
- Analytical Logic: Template assembly; retrieval of past RFx materials;
  controlled narrative generation; rule-based completeness checks
"""
from typing import Dict, Any, Optional
from utils.schemas import RFxDraft, CaseSummary
from utils.data_loader import get_category, get_requirements, get_suppliers_by_category
from utils.knowledge_layer import get_vector_context
from agents.base_agent import BaseAgent
import json


class RFxDraftAgent(BaseAgent):
    """
    RFx Draft Agent for DTP-03 (Table 3 aligned).
    
    Template-driven generation only.
    LLM fills structure, adapts language, explains intent.
    Rule-based completeness checks before returning output.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("RFxDraft", tier)
    
    def create_rfx_draft(
        self,
        case_summary: CaseSummary,
        use_cache: bool = True
    ) -> tuple[RFxDraft, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Create RFx draft using template-driven generation (Table 3).
        Returns (rfx_draft, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "rfx_draft",
                case_summary
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # STEP 1: Retrieve RFx template from Vector Knowledge Layer (Table 3: template assembly, retrieval of past RFx materials)
        rfx_template_context = get_vector_context(
            category_id=case_summary.category_id,
            dtp_stage="DTP-03",
            topic="rfq_template"
        )
        
        # STEP 2: Retrieve category context for filling template
        category = get_category(case_summary.category_id)
        requirements = get_requirements(case_summary.category_id)
        suppliers = get_suppliers_by_category(case_summary.category_id)
        
        # Build prompt for template-driven generation
        prompt = f"""You are an RFx Draft Agent for dynamic sourcing pipelines (DTP-03).

Your role (Table 3 alignment):
- Assemble RFx draft using templates and structured generation
- Fill template sections with case-specific data
- Adapt language to category context
- Explain intent and adaptations

RFx Template Structure (from Vector Knowledge Layer):
{json.dumps(rfx_template_context, indent=2)}

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Category Information:
{json.dumps(category, indent=2) if category else "No category data"}

Category Requirements:
{json.dumps(requirements, indent=2) if requirements else "No requirements data"}

Available Suppliers (for context):
{json.dumps([s["supplier_id"] for s in suppliers[:5]], indent=2) if suppliers else "None"}

Your task:
1. Fill template sections with case-specific data:
   - Overview: Category and case context
   - Requirements: Category requirements (must-have and nice-to-have)
   - Evaluation Criteria: Human-defined evaluation criteria
   - Timeline: Suggested timeline based on urgency
   - Terms & Conditions: Standard terms (do NOT invent commercial terms)
2. Adapt language to category context
3. Explain intent and any adaptations made

IMPORTANT CONSTRAINTS:
- Use template structure provided above
- Do NOT invent commercial terms or binding clauses
- All terms require human/legal approval
- Controlled narrative generation - stay within template bounds

Respond with a JSON object matching this schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "rfx_sections": {{
    "Overview": "Section content",
    "Requirements": "Section content",
    "Evaluation Criteria": "Section content",
    "Timeline": "Section content",
    "Terms & Conditions": "Section content"
  }},
  "completeness_check": {{
    "all_sections_filled": true,
    "requirements_included": true,
    "evaluation_criteria_included": true
  }},
  "template_source": "rfq_template from Vector Knowledge Layer",
  "explanation": "Brief explanation of intent and adaptations"
}}

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "template_context": rfx_template_context,
            "category": category,
            "requirements": requirements
        }
        
        try:
            rfx_draft, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, RFxDraft, retry_on_invalid=True
            )
            
            # STEP 3: Rule-based completeness checks (Table 3: rule-based completeness checks)
            completeness_check = self._check_rfx_completeness(rfx_draft)
            rfx_draft.completeness_check = completeness_check
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    "rfx_draft",
                    case_summary
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (rfx_draft, llm_input_payload, output_dict))
            
            return rfx_draft, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(
                RFxDraft, case_summary.case_id, case_summary.category_id
            ), llm_input_payload, {}, 0, 0
    
    def _check_rfx_completeness(self, rfx_draft: RFxDraft) -> Dict[str, bool]:
        """
        Rule-based completeness checks (Table 3).
        Returns dictionary of completeness check results.
        """
        sections = rfx_draft.rfx_sections
        required_sections = ["Overview", "Requirements", "Evaluation Criteria", "Timeline", "Terms & Conditions"]
        
        all_sections_filled = all(
            section in sections and sections[section].strip() for section in required_sections
        )
        
        requirements_included = "Requirements" in sections and len(sections.get("Requirements", "")) > 50
        evaluation_criteria_included = "Evaluation Criteria" in sections and len(sections.get("Evaluation Criteria", "")) > 30
        
        return {
            "all_sections_filled": all_sections_filled,
            "requirements_included": requirements_included,
            "evaluation_criteria_included": evaluation_criteria_included
        }
    
    def create_fallback_output(self, schema: type, case_id: str, category_id: str) -> RFxDraft:
        """Fallback output when LLM fails"""
        return RFxDraft(
            case_id=case_id,
            category_id=category_id,
            rfx_sections={},
            completeness_check={"all_sections_filled": False},
            template_source="Fallback",
            explanation="Fallback output due to processing error"
        )







"""
Contract Support Agent (DTP-04/05) - Table 3 alignment.

Per Table 3:
- Extracts key award terms and prepares structured inputs for contracting
- Analytical Logic: Template-guided extraction; rule-based contract field validation;
  knowledge graph grounding for term alignment
"""
from typing import Dict, Any, Optional
from utils.schemas import ContractExtraction, CaseSummary
from utils.data_loader import get_category, get_contract, get_supplier, get_performance
from utils.knowledge_layer import get_vector_context
from agents.base_agent import BaseAgent
import json


class ContractSupportAgent(BaseAgent):
    """
    Contract Support Agent for DTP-04/05 (Table 3 aligned).
    
    Extraction and validation only.
    LLM reasons to explain mappings and flag inconsistencies.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("ContractSupport", tier)
    
    def extract_contract_terms(
        self,
        case_summary: CaseSummary,
        supplier_id: str,
        use_cache: bool = True
    ) -> tuple[ContractExtraction, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Extract contract terms using template-guided extraction (Table 3).
        Returns (contract_extraction, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "contract_extraction",
                case_summary,
                additional_inputs={"supplier_id": supplier_id}
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # STEP 1: Retrieve contract clause library from Vector Knowledge Layer (Table 3: knowledge graph grounding)
        contract_clauses_context = get_vector_context(
            category_id=case_summary.category_id,
            dtp_stage="DTP-04",
            topic="contract_clauses"
        )
        
        # STEP 2: Retrieve relevant data for extraction
        category = get_category(case_summary.category_id)
        contract = get_contract(case_summary.contract_id) if case_summary.contract_id else None
        supplier = get_supplier(supplier_id)
        performance = get_performance(supplier_id)
        
        # Get negotiation plan or supplier shortlist if available (for award terms)
        # This would come from latest_agent_output in practice
        
        # Build prompt for template-guided extraction
        prompt = f"""You are a Contract Support Agent for dynamic sourcing pipelines (DTP-04/05).

Your role (Table 3 alignment):
- Extract key award terms using template-guided extraction
- Validate contract fields using rules
- Explain term mappings and flag inconsistencies
- Prepare structured inputs for contracting

Contract Clause Library (from Vector Knowledge Layer - for grounding only):
{json.dumps(contract_clauses_context, indent=2)}

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Category Information:
{json.dumps(category, indent=2) if category else "No category data"}

Supplier Information:
{json.dumps(supplier, indent=2) if supplier else "No supplier data"}

Current Contract (if exists):
{json.dumps(contract, indent=2) if contract else "No existing contract"}

Supplier Performance:
{json.dumps(performance, indent=2) if performance else "No performance data"}

Your task:
1. Extract key award terms using template structure:
   - Service Levels
   - Payment Terms
   - Termination Clauses
   - Compliance Requirements
2. Map terms to contract clause library (explain mappings)
3. Flag any inconsistencies or missing required fields
4. Prepare structured extraction for contracting system

IMPORTANT CONSTRAINTS:
- Use clause library as reference only (not binding)
- Rule-based validation: check for required fields
- Explain mappings clearly
- Flag inconsistencies for human review
- Do NOT create new clauses or modify terms

Respond with a JSON object matching this EXACT schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "supplier_id": "{supplier_id}",
  "extracted_terms": {{
    "Service Levels": "99.5% uptime SLA with 4-hour response time",
    "Payment Terms": "Net 30 days from invoice date",
    "Termination": "90-day notice period with cure provisions",
    "Compliance": "SOC 2 Type II certification required"
  }},
  "validation_results": {{
    "required_fields_present": true,
    "service_levels_valid": true,
    "payment_terms_valid": true
  }},
  "mapping_explanations": {{
    "Service Levels": "Terms align with standard enterprise SLA template",
    "Payment Terms": "Matches approved payment terms for this category"
  }},
  "inconsistencies": ["Termination notice period differs from standard 60-day policy", "Missing liability cap clause"],
  "template_guidance": "contract_clauses from Vector Knowledge Layer"
}}

IMPORTANT: The "inconsistencies" field must contain simple strings, not objects.

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "supplier_id": supplier_id,
            "clause_context": contract_clauses_context,
            "category": category,
            "contract": contract,
            "supplier": supplier,
            "performance": performance
        }
        
        try:
            extraction, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, ContractExtraction, retry_on_invalid=True
            )
            
            # STEP 3: Rule-based field validation (Table 3: rule-based contract field validation)
            validation_results = self._validate_contract_fields(extraction)
            extraction.validation_results = validation_results
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    "contract_extraction",
                    case_summary,
                    additional_inputs={"supplier_id": supplier_id}
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (extraction, llm_input_payload, output_dict))
            
            return extraction, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(
                ContractExtraction, case_summary.case_id, case_summary.category_id, supplier_id
            ), llm_input_payload, {}, 0, 0
    
    def _validate_contract_fields(self, extraction: ContractExtraction) -> Dict[str, bool]:
        """
        Rule-based contract field validation (Table 3).
        Returns dictionary of validation results.
        """
        terms = extraction.extracted_terms
        required_fields = ["Service Levels", "Payment Terms"]
        
        required_fields_present = all(field in terms and terms[field].strip() for field in required_fields)
        service_levels_valid = "Service Levels" in terms and len(terms.get("Service Levels", "")) > 20
        payment_terms_valid = "Payment Terms" in terms and len(terms.get("Payment Terms", "")) > 20
        
        return {
            "required_fields_present": required_fields_present,
            "service_levels_valid": service_levels_valid,
            "payment_terms_valid": payment_terms_valid
        }
    
    def create_fallback_output(self, schema: type, case_id: str, category_id: str, supplier_id: str) -> ContractExtraction:
        """Fallback output when LLM fails"""
        return ContractExtraction(
            case_id=case_id,
            category_id=category_id,
            supplier_id=supplier_id,
            extracted_terms={},
            validation_results={"required_fields_present": False},
            mapping_explanations={},
            inconsistencies=["Fallback output - validation required"],
            template_guidance="Fallback"
        )








"""
Implementation Agent (DTP-05/06) - Table 3 alignment.

Per Table 3:
- Produces rollout steps and early post-award indicators
- Analytical Logic: Deterministic calculations; retrieval of rollout playbooks;
  structured reporting templates
"""
from typing import Dict, Any, Optional, List
from utils.schemas import ImplementationPlan, CaseSummary
from utils.data_loader import get_category, get_contract, get_supplier
from utils.knowledge_layer import get_vector_context
from agents.base_agent import BaseAgent
import json


class ImplementationAgent(BaseAgent):
    """
    Implementation Agent for DTP-05/06 (Table 3 aligned).
    
    Deterministic rollout calculations.
    LLM reasons to explain impacts, summarize KPIs.
    No strategic reasoning.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("Implementation", tier)
    
    def create_implementation_plan(
        self,
        case_summary: CaseSummary,
        supplier_id: str,
        use_cache: bool = True
    ) -> tuple[ImplementationPlan, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Create implementation plan with deterministic calculations (Table 3).
        Returns (implementation_plan, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "implementation_plan",
                case_summary,
                additional_inputs={"supplier_id": supplier_id}
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # STEP 1: Retrieve rollout playbook from Vector Knowledge Layer (Table 3: retrieval of rollout playbooks)
        rollout_playbook = get_vector_context(
            category_id=case_summary.category_id,
            dtp_stage="DTP-05",
            topic="rollout_playbook"
        )
        
        # STEP 2: Retrieve context for calculations
        category = get_category(case_summary.category_id)
        contract = get_contract(case_summary.contract_id) if case_summary.contract_id else None
        supplier = get_supplier(supplier_id)
        
        # STEP 3: Deterministic calculations (Table 3: deterministic calculations)
        projected_savings = self._calculate_projected_savings(contract, category)
        rollout_steps = self._determine_rollout_steps(rollout_playbook)
        
        # Build prompt for LLM explanation of impacts and KPIs
        prompt = f"""You are an Implementation Agent for dynamic sourcing pipelines (DTP-05/06).

Your role (Table 3 alignment):
- Explain impacts and summarize KPIs (structured reporting)
- No strategic reasoning - only explanation of deterministic outputs

Rollout Playbook (from Vector Knowledge Layer):
{json.dumps(rollout_playbook, indent=2)}

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Category Information:
{json.dumps(category, indent=2) if category else "No category data"}

Supplier Information:
{json.dumps(supplier, indent=2) if supplier else "No supplier data"}

Contract Information:
{json.dumps(contract, indent=2) if contract else "No contract data"}

Deterministic Calculations (already computed):
- Projected Savings: ${projected_savings:,.2f} (if applicable)
- Rollout Steps: {json.dumps(rollout_steps, indent=2)}

Your task:
1. Explain the impacts of this implementation (service levels, operational changes)
2. Summarize KPIs in structured format (savings realization, service levels, compliance metrics)
3. Structure the reporting based on rollout playbook template

IMPORTANT CONSTRAINTS:
- Use rollout playbook structure
- Explain deterministic calculations clearly
- Do NOT perform strategic reasoning
- Focus on structured reporting and impact explanation

Respond with a JSON object matching this EXACT schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "supplier_id": "{supplier_id}",
  "rollout_steps": [
    {{"step": "Contract Execution", "description": "Finalize and sign contract documents", "timeline": "Week 1"}},
    {{"step": "Supplier Onboarding", "description": "Complete vendor setup and system access", "timeline": "Week 2-3"}},
    {{"step": "Service Transition", "description": "Migrate services from incumbent supplier", "timeline": "Week 4-6"}}
  ],
  "projected_savings": {projected_savings if projected_savings else 0},
  "service_impacts": {{
    "service_level_changes": "Improved response times expected with new SLA terms",
    "operational_changes": "New ordering process will require team training"
  }},
  "kpi_summary": {{
    "savings_realization": "Target 10% cost reduction in first year",
    "service_levels": "99.5% uptime commitment with penalty clauses",
    "compliance_metrics": "Quarterly audit reports required"
  }},
  "explanation": "This implementation plan follows the standard rollout playbook with adjustments for category-specific requirements",
  "playbook_source": "rollout_playbook from Vector Knowledge Layer"
}}

IMPORTANT: Ensure all string fields contain actual text values, not null or empty strings.

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "supplier_id": supplier_id,
            "rollout_playbook": rollout_playbook,
            "deterministic_calculations": {
                "projected_savings": projected_savings,
                "rollout_steps": rollout_steps
            },
            "category": category,
            "contract": contract,
            "supplier": supplier
        }
        
        try:
            implementation_plan, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, ImplementationPlan, retry_on_invalid=True
            )
            
            # Set deterministic values (LLM should match these, but we enforce them)
            implementation_plan.projected_savings = projected_savings
            implementation_plan.rollout_steps = rollout_steps
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    "implementation_plan",
                    case_summary,
                    additional_inputs={"supplier_id": supplier_id}
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (implementation_plan, llm_input_payload, output_dict))
            
            return implementation_plan, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(
                ImplementationPlan, case_summary.case_id, case_summary.category_id, supplier_id
            ), llm_input_payload, {}, 0, 0
    
    def _calculate_projected_savings(self, contract: Optional[Dict[str, Any]], category: Optional[Dict[str, Any]]) -> Optional[float]:
        """
        Deterministic calculation of projected savings (Table 3).
        In production, this would use structured financial models.
        """
        if not contract:
            return None
        
        # Simple deterministic calculation: assume 5% savings on annual value for demonstration
        annual_value = contract.get("annual_value_usd", 0)
        if annual_value > 0:
            return annual_value * 0.05  # 5% projected savings
        return None
    
    def _determine_rollout_steps(self, rollout_playbook: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Determine rollout steps from playbook (Table 3: deterministic).
        """
        # Extract steps from playbook content
        steps_content = rollout_playbook.get("content", {}).get("steps", [])
        
        # Convert to structured format
        rollout_steps = []
        for i, step_name in enumerate(steps_content):
            rollout_steps.append({
                "step": step_name,
                "description": f"Execute {step_name} as per rollout playbook",
                "timeline": f"Week {i+1}-{i+2}"
            })
        
        # Default steps if playbook doesn't provide
        if not rollout_steps:
            rollout_steps = [
                {"step": "Contract execution", "description": "Finalize and execute contract", "timeline": "Week 1"},
                {"step": "Supplier onboarding", "description": "Onboard supplier to systems", "timeline": "Week 2-3"},
                {"step": "System integration", "description": "Integrate supplier systems", "timeline": "Week 4-6"},
                {"step": "Monitoring setup", "description": "Set up monitoring and KPIs", "timeline": "Week 7-8"}
            ]
        
        return rollout_steps
    
    def create_fallback_output(self, schema: type, case_id: str, category_id: str, supplier_id: str) -> ImplementationPlan:
        """Fallback output when LLM fails"""
        return ImplementationPlan(
            case_id=case_id,
            category_id=category_id,
            supplier_id=supplier_id,
            rollout_steps=[],
            projected_savings=None,
            service_impacts={},
            kpi_summary={},
            explanation="Fallback output due to processing error",
            playbook_source="Fallback"
        )


"""
Negotiation Support Agent (DTP-04) - Creates negotiation plans.
"""
from typing import Dict, Any
from utils.schemas import NegotiationPlan, CaseSummary
from utils.data_loader import get_contract, get_performance, get_market_data, get_category, get_requirements, get_supplier
from agents.base_agent import BaseAgent
import json


class NegotiationSupportAgent(BaseAgent):
    """Negotiation Support Agent for DTP-04"""
    
    def __init__(self, tier: int = 1):
        super().__init__("NegotiationSupport", tier)
    
    def create_negotiation_plan(
        self,
        case_summary: CaseSummary,
        supplier_id: str,
        use_cache: bool = True
    ) -> tuple[NegotiationPlan, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Create negotiation plan for a supplier.
        Returns (plan, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "negotiation_plan",
                case_summary,
                additional_inputs={"supplier_id": supplier_id}
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # Gather context
        contract = None
        performance = None
        market = None
        category = None
        requirements = None
        supplier = None
        
        if case_summary.contract_id:
            contract = get_contract(case_summary.contract_id)
        if supplier_id:
            performance = get_performance(supplier_id)
            supplier = get_supplier(supplier_id)
        if case_summary.category_id:
            market = get_market_data(case_summary.category_id)
            category = get_category(case_summary.category_id)
            requirements = get_requirements(case_summary.category_id)
        
        # Build prompt
        prompt = f"""You are a Negotiation Support Agent for dynamic sourcing pipelines (DTP-04).

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Target Supplier ID: {supplier_id}

Current Contract:
{json.dumps(contract, indent=2) if contract else "No existing contract"}

Supplier Performance:
{json.dumps(performance, indent=2) if performance else "No performance data"}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Create a negotiation plan. Consider:
1. Current contract terms and pricing
2. Supplier performance and relationship
3. Market benchmarks
4. Leverage points and negotiation objectives
5. Risk mitigation strategies

Respond with a JSON object matching this schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "supplier_id": "{supplier_id}",
  "negotiation_objectives": ["objective1", "objective2"],
  "target_terms": {{"key": "value"}},
  "leverage_points": ["leverage1", "leverage2"],
  "fallback_positions": {{"key": "value"}},
  "timeline": "Recommended negotiation timeline",
  "risk_mitigation": ["risk1 mitigation", "risk2 mitigation"]
}}

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "supplier_id": supplier_id,
            "contract": contract,
            "supplier": supplier,
            "performance": performance,
            "market": market,
            "category": category,
            "requirements": requirements
        }
        
        try:
            plan, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, NegotiationPlan, retry_on_invalid=True
            )
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    "negotiation_plan",
                    case_summary,
                    additional_inputs={"supplier_id": supplier_id}
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (plan, {}, {}))
            
            return plan, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(NegotiationPlan, case_summary.case_id, case_summary.category_id, supplier_id), llm_input_payload, {}, 0, 0
    
    def create_fallback_output(self, schema: type, case_id: str, category_id: str, supplier_id: str) -> NegotiationPlan:
        """Fallback output when LLM fails"""
        return NegotiationPlan(
            case_id=case_id,
            category_id=category_id,
            supplier_id=supplier_id,
            negotiation_objectives=["Fallback objective"],
            target_terms={},
            leverage_points=[],
            fallback_positions={},
            timeline="Review required",
            risk_mitigation=["Fallback risk mitigation"]
        )



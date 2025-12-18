"""
Negotiation Support Agent (DTP-04) - Table 3 alignment.

Per Table 3:
- Highlights bid differences, identifies negotiation levers
- Provides structured insights
- Analytical Logic: Structured bid comparison; ML price anomaly detection;
  benchmark retrieval; negotiation heuristics
- NO award decisions
- NO policy enforcement
"""
from typing import Dict, Any, Optional
from utils.schemas import NegotiationPlan, CaseSummary
from utils.data_loader import get_contract, get_performance, get_market_data, get_category, get_requirements, get_supplier
from utils.knowledge_layer import get_vector_context
from agents.base_agent import BaseAgent
import json


class NegotiationSupportAgent(BaseAgent):
    """
    Negotiation Support Agent for DTP-04 (Table 3 aligned).
    
    Comparative and advisory only.
    LLM reasons to: identify leverage, explain gaps, suggest scenarios.
    NO award decisions. NO policy enforcement.
    """
    
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
        
        # Retrieve negotiation playbook from Vector Knowledge Layer (Table 3: benchmark retrieval, negotiation heuristics)
        negotiation_playbook = get_vector_context(
            category_id=case_summary.category_id,
            dtp_stage="DTP-04",
            topic="negotiation_playbook"
        )
        
        # Build prompt aligned with Table 3: comparative and advisory only
        prompt = f"""You are a Negotiation Support Agent for dynamic sourcing pipelines (DTP-04).

Your role (Table 3 alignment):
- Highlight bid differences and identify negotiation levers
- Provide structured insights (comparative and advisory only)
- Use benchmarks and negotiation heuristics from playbook
- LLM reasons to: identify leverage, explain gaps, suggest scenarios
- NO award decisions (human makes final choice)
- NO policy enforcement (Supervisor enforces policy)

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Target Supplier ID: {supplier_id}

Current Contract:
{json.dumps(contract, indent=2) if contract else "No existing contract"}

Supplier Performance:
{json.dumps(performance, indent=2) if performance else "No performance data"}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Create a negotiation plan (comparative and advisory). Consider:
1. Current contract terms and pricing (bid comparison)
2. Supplier performance and relationship (context)
3. Market benchmarks (from playbook - for grounding only)
4. Leverage points (identify gaps and opportunities)
5. Negotiation scenarios (suggest approaches, do not decide)

Negotiation Playbook Context (for grounding only):
{json.dumps(negotiation_playbook, indent=2) if negotiation_playbook else "None"}

IMPORTANT:
- This plan is advisory - you do NOT make award decisions
- Policy enforcement is handled by Supervisor + humans
- Use benchmarks and heuristics as context, not as binding rules

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



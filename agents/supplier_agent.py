"""
Supplier Evaluation Agent (DTP-03/04) - Evaluates and shortlists suppliers.
"""
from typing import Dict, Any
from utils.schemas import SupplierShortlist, CaseSummary
from utils.data_loader import get_suppliers_by_category, get_performance, get_market_data
from agents.base_agent import BaseAgent
import json


class SupplierEvaluationAgent(BaseAgent):
    """Supplier Evaluation Agent for DTP-03/04"""
    
    def __init__(self, tier: int = 1):
        super().__init__("SupplierEvaluation", tier)
    
    def evaluate_suppliers(
        self,
        case_summary: CaseSummary,
        use_cache: bool = True
    ) -> tuple[SupplierShortlist, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Evaluate and shortlist suppliers for a category.
        Returns (shortlist, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "supplier_evaluation",
                case_summary
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # Gather context
        suppliers = get_suppliers_by_category(case_summary.category_id)
        market = get_market_data(case_summary.category_id)
        category = get_category(case_summary.category_id)
        requirements = get_requirements(case_summary.category_id)
        
        # Get performance for each supplier (with full details)
        suppliers_with_perf = []
        for supplier in suppliers:
            perf = get_performance(supplier["supplier_id"])
            suppliers_with_perf.append({
                "supplier": supplier,
                "performance": perf
            })
        
        # Build prompt
        prompt = f"""You are a Supplier Evaluation Agent for dynamic sourcing pipelines (DTP-03/04).

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Available Suppliers for Category {case_summary.category_id}:
{json.dumps(suppliers_with_perf, indent=2)}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Category Information:
{json.dumps(category, indent=2) if category else "No category data"}

Category Requirements:
{json.dumps(requirements, indent=2) if requirements else "No requirements data"}

Evaluate suppliers and create a shortlist. Consider:
1. Performance scores, trends, history, incidents, cost variance, and relationship quality
2. Supplier tier, relationship history, certifications, financial stability, geographic coverage
3. Supplier strengths, weaknesses, capabilities, and specializations
4. Market benchmarks, key suppliers, pricing drivers, and emerging trends
5. Fit for category requirements (must-have and nice-to-have) and evaluation criteria
6. Compliance status and regulatory requirements alignment

IMPORTANT: All supplier references must use supplier_id format "SUP-xxx"

Respond with a JSON object matching this schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "shortlisted_suppliers": [
    {{
      "supplier_id": "SUP-xxx",
      "name": "Supplier Name",
      "score": 0.0-10.0,
      "strengths": ["strength1", "strength2"],
      "concerns": ["concern1"] or []
    }}
  ],
  "evaluation_criteria": ["criterion1", "criterion2"],
  "recommendation": "Brief recommendation text",
  "top_choice_supplier_id": "SUP-xxx" or null,
  "comparison_summary": "Brief comparison of shortlisted suppliers"
}}

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "suppliers": suppliers_with_perf,
            "market": market,
            "category": category,
            "requirements": requirements
        }
        
        try:
            shortlist, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, SupplierShortlist, retry_on_invalid=True
            )
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    "supplier_evaluation",
                    case_summary
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (shortlist, {}, {}))
            
            return shortlist, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(SupplierShortlist, case_summary.case_id, case_summary.category_id), llm_input_payload, {}, 0, 0
    
    def create_fallback_output(self, schema: type, case_id: str, category_id: str) -> SupplierShortlist:
        """Fallback output when LLM fails"""
        return SupplierShortlist(
            case_id=case_id,
            category_id=category_id,
            shortlisted_suppliers=[],
            evaluation_criteria=["Fallback evaluation"],
            recommendation="Unable to evaluate suppliers - using fallback",
            comparison_summary="Fallback output due to processing error"
        )



"""
Strategy Agent (DTP-01) - Recommends sourcing strategy.
"""
from typing import Dict, Any
from utils.schemas import StrategyRecommendation, CaseSummary
from utils.data_loader import get_contract, get_performance, get_market_data, get_category, get_requirements
from agents.base_agent import BaseAgent
import json


class StrategyAgent(BaseAgent):
    """Strategy Agent for DTP-01"""
    
    def __init__(self, tier: int = 1):
        super().__init__("Strategy", tier)
    
    def recommend_strategy(
        self,
        case_summary: CaseSummary,
        user_intent: str = "",
        use_cache: bool = True
    ) -> tuple[StrategyRecommendation, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Recommend sourcing strategy.
        Returns (recommendation, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                user_intent.lower().strip(),
                case_summary,
                question_text=user_intent
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # Gather context
        contract = None
        performance = None
        market = None
        category = None
        requirements = None
        
        if case_summary.contract_id:
            contract = get_contract(case_summary.contract_id)
        if case_summary.supplier_id:
            performance = get_performance(case_summary.supplier_id)
        if case_summary.category_id:
            market = get_market_data(case_summary.category_id)
            category = get_category(case_summary.category_id)
            requirements = get_requirements(case_summary.category_id)
        
        # Build prompt
        prompt = f"""You are a Strategy Agent for dynamic sourcing pipelines (DTP-01).

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

User Intent:
{user_intent if user_intent else "No specific user intent provided"}

Contract Information:
{json.dumps(contract, indent=2) if contract else "No contract information"}

Supplier Performance:
{json.dumps(performance, indent=2) if performance else "No performance data"}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Category Information:
{json.dumps(category, indent=2) if category else "No category data"}

Analyze this case and recommend a sourcing strategy. Consider:
1. Contract expiry timing
2. Supplier performance trends
3. Market conditions and benchmarks
4. User intent if provided
5. Risk and opportunity factors

For predictable outputs:
- If contract expires in <= 60 days AND performance is declining/stable-low: recommend "RFx" or "Renegotiate"
- If contract expires in > 180 days AND performance is stable-good: recommend "Renew" or "Monitor"
- Consider market benchmarks for cost savings potential

Respond with a JSON object matching this schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "recommended_strategy": "Renew" | "Renegotiate" | "RFx" | "Terminate" | "Monitor",
  "confidence": 0.0-1.0,
  "rationale": ["bullet point 1", "bullet point 2", "bullet point 3"],
  "contract_id": "{case_summary.contract_id or ''}" or null,
  "supplier_id": "{case_summary.supplier_id or ''}" or null,
  "estimated_savings_potential": null or number,
  "risk_assessment": "Brief risk assessment",
  "timeline_recommendation": "Recommended timeline for action"
}}

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "user_intent": user_intent,
            "contract": contract,
            "performance": performance,
            "market": market,
            "category": category,
            "requirements": requirements
        }
        
        try:
            recommendation, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, StrategyRecommendation, retry_on_invalid=True
            )
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    user_intent.lower().strip(),
                    case_summary,
                    question_text=user_intent
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (recommendation, {}, {}))
            
            return recommendation, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(StrategyRecommendation, case_summary.case_id, case_summary.category_id), llm_input_payload, {}, 0, 0
    
    def create_fallback_output(self, schema: type, case_id: str, category_id: str) -> StrategyRecommendation:
        """Fallback output when LLM fails"""
        return StrategyRecommendation(
            case_id=case_id,
            category_id=category_id,
            recommended_strategy="Monitor",
            confidence=0.5,
            rationale=["Fallback recommendation due to processing error"],
            risk_assessment="Unable to assess risk",
            timeline_recommendation="Review required"
        )



"""
Signal Interpretation Agent - Interprets signals and recommends actions.
"""
from typing import Dict, Any
from utils.schemas import SignalAssessment, CaseSummary
from utils.data_loader import get_contract, get_performance, get_market_data, get_category, get_requirements, get_supplier
from agents.base_agent import BaseAgent
import json


class SignalInterpretationAgent(BaseAgent):
    """Signal Interpretation Agent"""
    
    def __init__(self, tier: int = 1):
        super().__init__("SignalInterpretation", tier)
    
    def interpret_signal(
        self,
        signal: Dict[str, Any],
        case_summary: CaseSummary,
        use_cache: bool = True
    ) -> tuple[SignalAssessment, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Interpret a signal and recommend action.
        Returns (assessment, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "signal_interpretation",
                case_summary,
                question_text=signal.get("description", "")
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
        
        if signal.get("contract_id"):
            contract = get_contract(signal["contract_id"])
        if signal.get("supplier_id"):
            performance = get_performance(signal["supplier_id"])
            supplier = get_supplier(signal["supplier_id"])
        if signal.get("category_id"):
            market = get_market_data(signal["category_id"])
            category = get_category(signal["category_id"])
            requirements = get_requirements(signal["category_id"])
        
        # Build prompt
        prompt = f"""You are a Signal Interpretation Agent for dynamic sourcing pipelines.

Signal Details:
- Signal ID: {signal.get('signal_id')}
- Type: {signal.get('signal_type')}
- Category: {signal.get('category_id')}
- Severity: {signal.get('severity')}
- Description: {signal.get('description')}

Contract Information:
{json.dumps(contract, indent=2) if contract else "No contract information"}

Supplier Performance:
{json.dumps(performance, indent=2) if performance else "No performance data"}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Analyze this signal and provide a structured assessment. Consider:
1. Contract expiry timing and urgency
2. Supplier performance trends
3. Market conditions
4. Risk factors

Respond with a JSON object matching this EXACT schema:
{{
  "signal_id": "{signal.get('signal_id')}",
  "category_id": "{signal.get('category_id')}",
  "assessment": "Contract expiring soon with declining supplier performance indicates need for competitive review",
  "recommended_action": "RFx",
  "confidence": 0.85,
  "rationale": ["Contract expires in 45 days requiring immediate action", "Supplier performance has declined 15% over past quarter"],
  "urgency_score": 8,
  "contract_id": "{signal.get('contract_id', '')}",
  "supplier_id": "{signal.get('supplier_id', '')}"
}}

IMPORTANT NOTES:
- "recommended_action" must be exactly one of: "Renew", "Renegotiate", "RFx", "Monitor", or "Terminate"
- "confidence" must be a decimal number between 0.0 and 1.0 (e.g., 0.85)
- "urgency_score" must be an integer between 1 and 10 (e.g., 8)
- "rationale" must be an array of simple strings, not objects

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "signal": signal,
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "contract": contract,
            "supplier": supplier,
            "performance": performance,
            "market": market,
            "category": category,
            "requirements": requirements
        }
        
        try:
            assessment, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, SignalAssessment, retry_on_invalid=True
            )
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    "signal_interpretation",
                    case_summary,
                    question_text=signal.get("description", "")
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (assessment, {}, {}))
            
            return assessment, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(SignalAssessment, signal.get('signal_id', ''), signal.get('category_id', '')), llm_input_payload, {}, 0, 0
    
    def create_fallback_output(self, schema: type, signal_id: str, category_id: str) -> SignalAssessment:
        """Fallback output when LLM fails"""
        return SignalAssessment(
            signal_id=signal_id,
            category_id=category_id,
            assessment="Unable to process signal - using fallback assessment",
            recommended_action="Monitor",
            confidence=0.5,
            rationale=["Fallback assessment due to processing error"],
            urgency_score=5
        )



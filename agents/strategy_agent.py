"""
Strategy Agent (DTP-01) - Applies rules first, then uses LLM for summarization only.

ARCHITECTURE: Rules > Retrieval > LLM Narration
- Rules are applied deterministically BEFORE LLM calls
- LLM is used ONLY for summarization, not decision-making
"""
from typing import Dict, Any
from utils.schemas import StrategyRecommendation, CaseSummary, DecisionImpact
from utils.data_loader import get_contract, get_performance, get_market_data, get_category, get_requirements
from utils.rules import RuleEngine
from agents.base_agent import BaseAgent
import json


class StrategyAgent(BaseAgent):
    """Strategy Agent for DTP-01 - Rule-first architecture"""
    
    def __init__(self, tier: int = 1):
        super().__init__("Strategy", tier)
        self.rule_engine = RuleEngine()
    
    def recommend_strategy(
        self,
        case_summary: CaseSummary,
        user_intent: str = "",
        use_cache: bool = True
    ) -> tuple[StrategyRecommendation, Dict[str, Any], Dict[str, Any], int, int]:
        """
        Recommend sourcing strategy following Rules > Retrieval > LLM pattern.
        Returns (recommendation, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # STEP 1: Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                user_intent.lower().strip(),
                case_summary,
                question_text=user_intent
            )
            if cache_meta.cache_hit and cached_value:
                return cached_value, {}, {}
        
        # STEP 2: Retrieve data (deterministic retrieval)
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
        
        # STEP 3: Apply deterministic rules FIRST (Priority 1)
        rule_based_strategy = self.rule_engine.apply_strategy_rules(
            contract, performance, market, case_summary
        )
        
        # STEP 4: If rule matched, create deterministic output (NO LLM CALL)
        if rule_based_strategy:
            recommendation = self._create_rule_based_recommendation(
                case_summary, rule_based_strategy, contract, performance, market
            )
            
            llm_input_payload = {
                "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
                "user_intent": user_intent,
                "contract": contract,
                "performance": performance,
                "market": market,
                "category": category,
                "requirements": requirements,
                "rule_applied": True,
                "rule_based_strategy": rule_based_strategy
            }
            
            output_dict = recommendation.model_dump() if hasattr(recommendation, "model_dump") else dict(recommendation)
            
            # Cache result
            if use_cache:
                cache_meta, _ = self.check_cache(
                    case_summary.case_id,
                    user_intent.lower().strip(),
                    case_summary,
                    question_text=user_intent
                )
                from utils.caching import set_cache
                set_cache(cache_meta.cache_key, (recommendation, llm_input_payload, output_dict))
            
            # Return with zero tokens (no LLM call)
            return recommendation, llm_input_payload, output_dict, 0, 0
        
        # STEP 5: No rule matched - use LLM for summarization ONLY (Priority 5)
        # LLM does NOT make decisions, only summarizes retrieved data
        prompt = self._build_summarization_prompt(
            case_summary, user_intent, contract, performance, market, category, requirements
        )
        
        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "user_intent": user_intent,
            "contract": contract,
            "performance": performance,
            "market": market,
            "category": category,
            "requirements": requirements,
            "rule_applied": False,
            "note": "No deterministic rule matched - LLM used for summarization only"
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
                set_cache(cache_meta.cache_key, (recommendation, llm_input_payload, output_dict))
            
            return recommendation, llm_input_payload, output_dict, input_tokens, output_tokens
        except Exception as e:
            # Fallback
            return self.create_fallback_output(StrategyRecommendation, case_summary.case_id, case_summary.category_id), llm_input_payload, {}, 0, 0
    
    def _create_rule_based_recommendation(
        self,
        case_summary: CaseSummary,
        strategy: str,
        contract: Optional[Dict[str, Any]],
        performance: Optional[Dict[str, Any]],
        market: Optional[Dict[str, Any]]
    ) -> StrategyRecommendation:
        """Create deterministic recommendation based on rule application."""
        rationale = []
        
        if contract:
            expiry_days = contract.get("expiry_days", 0)
            rationale.append(f"Contract expires in {expiry_days} days")
        
        if performance:
            perf_trend = performance.get("trend", "")
            perf_score = performance.get("overall_score", 0)
            rationale.append(f"Supplier performance: {perf_trend} (score: {perf_score:.1f})")
        
        if market:
            rationale.append(f"Market conditions analyzed for category {case_summary.category_id}")
        
        # Determine confidence based on data completeness
        confidence = 0.8 if (contract and performance) else 0.6
        
        # Determine decision impact
        decision_impact = DecisionImpact.HIGH if strategy in ["RFx", "Terminate"] else DecisionImpact.MEDIUM
        
        return StrategyRecommendation(
            case_id=case_summary.case_id,
            category_id=case_summary.category_id,
            recommended_strategy=strategy,
            confidence=confidence,
            rationale=rationale,
            contract_id=case_summary.contract_id,
            supplier_id=case_summary.supplier_id,
            estimated_savings_potential=None,  # Requires market analysis
            risk_assessment="Rule-based assessment - see rationale",
            timeline_recommendation="Immediate action recommended" if strategy in ["RFx", "Renegotiate"] else "Monitor and plan",
            decision_impact=decision_impact
        )
    
    def _build_summarization_prompt(
        self,
        case_summary: CaseSummary,
        user_intent: str,
        contract: Optional[Dict[str, Any]],
        performance: Optional[Dict[str, Any]],
        market: Optional[Dict[str, Any]],
        category: Optional[Dict[str, Any]],
        requirements: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for LLM summarization (NOT decision-making)."""
        return f"""You are a Strategy Agent for dynamic sourcing pipelines (DTP-01).

Your role is LIMITED to:
1. Summarizing the retrieved contract, performance, and market data
2. Explaining the context and implications
3. Providing narrative rationale for strategy consideration

IMPORTANT CONSTRAINTS:
- You do NOT make strategy decisions (rules determine strategy when applicable)
- You do NOT override policy rules
- You do NOT invent criteria
- You ONLY summarize and explain retrieved data

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

User Intent:
{user_intent if user_intent else "No specific user intent provided"}

Retrieved Data:

Contract Information:
{json.dumps(contract, indent=2) if contract else "No contract information"}

Supplier Performance:
{json.dumps(performance, indent=2) if performance else "No performance data"}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Category Information:
{json.dumps(category, indent=2) if category else "No category data"}

Your task: Provide a clear, grounded summary explaining:
1. What the retrieved data shows
2. Key factors to consider (contract timing, performance trends, market conditions)
3. Risks and opportunities based on the data
4. Recommended strategy based on data analysis (choose from: Renew, Renegotiate, RFx, Terminate, Monitor)

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



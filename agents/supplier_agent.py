"""
Supplier Scoring Agent (DTP-02/03) - Table 3 alignment.

Per Table 3:
- Converts human-defined evaluation criteria into structured score inputs
- Processes historical performance and risk data
- Analytical Logic: Deterministic scoring logic; ML performance normalization;
  rule-based eligibility checks; optional explanatory generation
- Does NOT select winners (that's a human decision)

LLM reasoning allowed:
- Explains differences between suppliers
- Summarizes risks
- Structures comparisons
"""
from typing import Dict, Any, Optional, List
from utils.schemas import SupplierShortlist, CaseSummary
from utils.data_loader import get_suppliers_by_category, get_performance, get_market_data, get_category, get_requirements
from utils.rules import RuleEngine
from utils.knowledge_layer import get_vector_context
from agents.base_agent import BaseAgent
import json


class SupplierEvaluationAgent(BaseAgent):
    """
    Supplier Scoring Agent for DTP-02/03 (Table 3 aligned).
    
    Converts human-defined criteria into structured scores.
    Uses deterministic eligibility checks + LLM reasoning for explanations.
    Does NOT select winners - only scores and structures comparisons.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("SupplierEvaluation", tier)
        self.rule_engine = RuleEngine()
    
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
                # Detect and skip cached error/fallback results
                # Fallback results have 0 suppliers and error messages in comparison_summary
                cached_shortlist = cached_value[0] if isinstance(cached_value, tuple) else cached_value
                is_cached_error = (
                    isinstance(cached_shortlist, SupplierShortlist) and
                    len(cached_shortlist.shortlisted_suppliers) == 0 and
                    ("error" in cached_shortlist.comparison_summary.lower() or
                     "fallback" in cached_shortlist.comparison_summary.lower() or
                     "LLM" in cached_shortlist.comparison_summary)
                )
                
                if is_cached_error:
                    # Skip cached error - retry the operation
                    print(f"⚠️ Skipping cached error result for case {case_summary.case_id} - retrying operation")
                else:
                    # Valid cached result - return it
                    # #region debug_log_h1_cache_hit
                    try:
                        from pathlib import Path
                        debug_path = Path(r"c:\Users\Diandra Riando\OneDrive\Documents\Capstone\Cursor Code\.cursor\debug.log")
                        with open(debug_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "pre-fix",
                                "hypothesisId": "H2",
                                "location": "agents/supplier_agent.py:evaluate_suppliers",
                                "message": "SupplierEvaluationAgent cache hit",
                                "data": {
                                    "case_id": case_summary.case_id,
                                    "category_id": case_summary.category_id,
                                    "cache_key": cache_meta.cache_key
                                },
                                "timestamp": __import__("time").time()
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion debug_log_h1_cache_hit
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
        
        # STEP 1: Apply deterministic eligibility checks (Table 3: rule-based eligibility checks)
        # Filter suppliers using RuleEngine eligibility rules (must-haves only)
        eligible_suppliers = []
        for supplier_data in suppliers_with_perf:
            supplier = supplier_data["supplier"]
            performance = supplier_data["performance"]
            
            # Apply deterministic scoring rules (returns 0.0 if fails eligibility, None if requires scoring)
            rule_score = self.rule_engine.apply_supplier_scoring_rules(
                supplier, performance, requirements
            )
            
            if rule_score is not None and rule_score == 0.0:
                # Failed eligibility check (below threshold or missing must-haves) - exclude
                continue
            else:
                # Passed eligibility or requires scoring - include for LLM evaluation
                eligible_suppliers.append(supplier_data)
        
        # If no eligible suppliers after deterministic filtering, return empty shortlist
        if not eligible_suppliers:
            empty_shortlist = SupplierShortlist(
                case_id=case_summary.case_id,
                category_id=case_summary.category_id,
                shortlisted_suppliers=[],
                evaluation_criteria=requirements.get("must_have", []) if requirements else [],
                recommendation="No suppliers passed eligibility checks (performance threshold or must-have requirements)",
                comparison_summary="All suppliers filtered out by deterministic eligibility rules"
            )
            llm_input_payload = {
                "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
                "eligible_suppliers_count": 0,
                "filtered_out_count": len(suppliers_with_perf),
                "deterministic_filtering_applied": True
            }
            return empty_shortlist, llm_input_payload, {}, 0, 0
        
        # STEP 2: Normalize performance data (Table 3: ML performance normalization)
        # For POC, we do simple normalization here. In production, this would use ML models.
        normalized_suppliers = []
        for supplier_data in eligible_suppliers:
            supplier = supplier_data["supplier"]
            performance = supplier_data["performance"]
            
            # Simple normalization: scale performance score to 0-10 range
            perf_score = performance.get("overall_score", 5.0) if performance else 5.0
            normalized_score = min(10.0, max(0.0, perf_score))  # Already in 0-10 range in data
            
            normalized_suppliers.append({
                "supplier": supplier,
                "performance": performance,
                "normalized_score": normalized_score
            })
        
        # Build prompt aligned with Table 3: LLM reasons to explain differences, summarize risks, structure comparisons
        # IMPORTANT: Does NOT select winners - that's a human decision
        prompt = f"""You are a Supplier Scoring Agent for dynamic sourcing pipelines (DTP-02/03).

Your role (Table 3 alignment):
- Convert human-defined evaluation criteria into structured score inputs
- Process historical performance and risk data
- Structure comparisons and explain differences
- Summarize risks and opportunities
- You do NOT select winners - you provide structured scores and explanations

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Eligible Suppliers for Category {case_summary.category_id} (after deterministic eligibility filtering):
{json.dumps(normalized_suppliers, indent=2)}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Category Information:
{json.dumps(category, indent=2) if category else "No category data"}

Category Requirements (Human-defined evaluation criteria):
{json.dumps(requirements, indent=2) if requirements else "No requirements data"}

Your task:
1. Score each eligible supplier based on performance data and category requirements
2. Structure comparisons to highlight differences
3. Explain risks and opportunities for each supplier
4. Provide structured shortlist with scores and explanations

IMPORTANT CONSTRAINTS:
- All supplier references must use supplier_id format "SUP-xxx"
- You do NOT select winners - only score and explain
- top_choice_supplier_id is OPTIONAL and non-binding (human makes final choice)
- Focus on explaining differences and summarizing risks

Respond with a JSON object matching this EXACT schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "shortlisted_suppliers": [
    {{
      "supplier_id": "SUP-xxx",
      "name": "Supplier Name",
      "score": 8.5,
      "strengths": ["strength1", "strength2"],
      "concerns": ["concern1"]
    }}
  ],
  "evaluation_criteria": ["Price competitiveness", "Quality rating", "Delivery performance"],
  "recommendation": "Brief recommendation text explaining the scoring and comparisons",
  "top_choice_supplier_id": "SUP-xxx" or null (optional, non-binding),
  "comparison_summary": "Structured comparison explaining differences between suppliers"
}}

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "eligible_suppliers_count": len(eligible_suppliers),
            "filtered_out_count": len(suppliers_with_perf) - len(eligible_suppliers),
            "normalized_suppliers": normalized_suppliers,
            "market": market,
            "category": category,
            "requirements": requirements,
            "deterministic_filtering_applied": True
        }
        
        try:
            shortlist, output_dict, input_tokens, output_tokens = self.call_llm_with_schema(
                prompt, SupplierShortlist, retry_on_invalid=True
            )

            # #region debug_log_h1_llm_shortlist
            try:
                from pathlib import Path
                debug_path = Path(r"c:\Users\Diandra Riando\OneDrive\Documents\Capstone\Cursor Code\.cursor\debug.log")
                with open(debug_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "pre-fix",
                        "hypothesisId": "H2",
                        "location": "agents/supplier_agent.py:evaluate_suppliers",
                        "message": "LLM-produced supplier shortlist",
                        "data": {
                            "case_id": case_summary.case_id,
                            "category_id": case_summary.category_id,
                            "shortlisted_count": len(shortlist.shortlisted_suppliers),
                            "used_fallback": False
                        },
                        "timestamp": __import__("time").time()
                    }) + "\n")
            except Exception:
                pass
            # #endregion debug_log_h1_llm_shortlist
            
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
            # Log the actual error for debugging
            print(f"⚠️ SupplierEvaluationAgent LLM call failed: {type(e).__name__}: {str(e)}")
            
            # Fallback with more descriptive error message
            fallback = SupplierShortlist(
                case_id=case_summary.case_id,
                category_id=case_summary.category_id,
                shortlisted_suppliers=[],
                evaluation_criteria=["Fallback evaluation"],
                recommendation=f"Unable to evaluate suppliers due to LLM error: {type(e).__name__}",
                comparison_summary=f"LLM processing error: {str(e)[:200]}"
            )

            # #region debug_log_h2_fallback
            try:
                from pathlib import Path
                debug_path = Path(r"c:\Users\Diandra Riando\OneDrive\Documents\Capstone\Cursor Code\.cursor\debug.log")
                with open(debug_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "pre-fix",
                        "hypothesisId": "H2",
                        "location": "agents/supplier_agent.py:evaluate_suppliers",
                        "message": "SupplierEvaluationAgent used fallback output",
                        "data": {
                            "case_id": case_summary.case_id,
                            "category_id": case_summary.category_id,
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                            "shortlisted_count": len(fallback.shortlisted_suppliers),
                            "recommendation": fallback.recommendation
                        },
                        "timestamp": __import__("time").time()
                    }) + "\n")
            except Exception:
                pass
            # #endregion debug_log_h2_fallback

            # DO NOT cache fallback/error results - they should be retried
            return fallback, llm_input_payload, {}, 0, 0
    
    def create_fallback_output(self, schema: type, case_id: str, category_id: str, error_msg: str = "") -> SupplierShortlist:
        """Fallback output when LLM fails (deprecated - use inline fallback in except block)"""
        return SupplierShortlist(
            case_id=case_id,
            category_id=category_id,
            shortlisted_suppliers=[],
            evaluation_criteria=["Fallback evaluation"],
            recommendation=f"Unable to evaluate suppliers - {error_msg}" if error_msg else "Unable to evaluate suppliers - fallback invoked",
            comparison_summary="Fallback output - check logs for details"
        )



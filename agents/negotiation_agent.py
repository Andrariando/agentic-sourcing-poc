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
from utils.schemas import NegotiationPlan, CaseSummary, AgentDialogue
from utils.data_loader import get_contract, get_performance, get_market_data, get_category, get_requirements, get_supplier
from utils.knowledge_layer import get_vector_context
from agents.base_agent import BaseAgent
from pydantic import BaseModel, Field
from typing import Literal, Union
import json


class NegotiationDecision(BaseModel):
    """Internal decision on whether to proceed or talk back"""
    action: Literal["Proceed", "NeedClarification", "ConcernRaised", "SuggestAlternative"]
    reasoning: str
    message_to_supervisor: Optional[str] = None



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
        use_cache: bool = True,
        user_intent: str = "",
        conversation_history: Optional[list[dict]] = None
    ) -> tuple[Union[NegotiationPlan, AgentDialogue], Dict[str, Any], Dict[str, Any], int, int]:
        """
        Create negotiation plan OR return AgentDialogue/ClarificationRequest.
        Returns (plan_or_dialogue, llm_input_payload, output_payload, input_tokens, output_tokens)
        """
        # Check cache
        if use_cache:
            cache_meta, cached_value = self.check_cache(
                case_summary.case_id,
                "negotiation_plan",
                case_summary,
                additional_inputs={"supplier_id": supplier_id},
                question_text=user_intent # Add intent to cache key
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
        
        
        # Retrieve Case Documents via RAG
        retrieved_docs = []
        try:
            from backend.rag.vector_store import get_vector_store
            vector_store = get_vector_store()
            if case_summary.case_id:
                rag_results = vector_store.search(
                    query=f"proposal contract terms pricing for {case_summary.case_id}",
                    n_results=3,
                    where={"case_id": case_summary.case_id}
                )
                if rag_results and rag_results.get("documents"):
                    data = rag_results["documents"][0]
                    metas = rag_results["metadatas"][0]
                    for i, text in enumerate(data):
                        fname = metas[i].get("filename", "Doc")
                        dtype = metas[i].get("document_type", "Unknown")
                        retrieved_docs.append(f"DOCUMENT [{dtype}] {fname}:\\n{text}")
        except Exception as e:
            print(f"RAG Error: {e}")

        # Step 1: Reasoning & Critique Loop
        # Agent decides whether to proceed or talk back
        reasoning_prompt = f"""You are a Negotiation Support Agent (DTP-04).
        User Intent: {user_intent if user_intent else "No instructions"}
        
        Information Available:
        - Case: {case_summary.case_id} ({case_summary.category_id})
        - Supplier: {supplier_id}
        - Contract: {"Available" if contract else "Missing"}
        - Performance: {"Available" if performance else "Missing"}
        - Market Data: {"Available" if market else "Missing"}
        - Retrieved Documents: {len(retrieved_docs)} found
        
        Review the request and available data.
        1. Do you have enough information to create a negotiation plan? (Missing contract/performance is critical)
        2. Is the request feasible given the market data?
        3. Is the strategy (Negotiation) appropriate?
        
        Decide:
        - "Proceed": Logic is sound, data is sufficient (or can be inferred).
        - "NeedClarification": Critical data missing (e.g. which supplier?) or ambiguous intent.
        - "ConcernRaised": Significant risk detected (e.g. trying to negotiate with a sole-source without leverage).
        - "SuggestAlternative": Strategy seems wrong (e.g. should be RFx instead).
        
        Respond with JSON:
        {{
            "action": "Proceed" | "NeedClarification" | "ConcernRaised" | "SuggestAlternative",
            "reasoning": "Internal thought process...",
            "message_to_supervisor": "Message if not Proceeding..."
        }}
        """
        
        reasoning_decision, _, _, r_input, r_output = self.call_llm_with_schema(
            reasoning_prompt, NegotiationDecision
        )
        
        if reasoning_decision.action != "Proceed":
             # Return AgentDialogue
            dialogue = AgentDialogue(
                agent_name=self.name,
                message=reasoning_decision.message_to_supervisor or reasoning_decision.reasoning,
                reasoning=reasoning_decision.reasoning,
                status=reasoning_decision.action,
                metadata={"case_id": case_summary.case_id}
            )
            return dialogue, {"reasoning_prompt": reasoning_prompt}, {}, r_input, r_output

        # Step 2: Proceed to Plan Generation (if Proceed)
        # Build prompt aligned with Table 3: comparative and advisory only
        
        # Prepare retrieved documents text
        retrieved_docs_text = "\n".join(retrieved_docs) if retrieved_docs else "No specific documents found."
        
        # Prepare Key Findings
        key_findings_text = "None"
        if hasattr(case_summary, "key_findings") and case_summary.key_findings:
            key_findings_list = [
                f"- {f.get('text', str(f)) if isinstance(f, dict) else str(f)}" 
                for f in case_summary.key_findings
            ]
            key_findings_text = "\n".join(key_findings_list)
            
        prompt = f"""You are a Negotiation Support Agent for dynamic sourcing pipelines (DTP-04).
        REASONING CONTEXT: {reasoning_decision.reasoning}

Your role (Table 3 alignment):
- Highlight bid differences and identify negotiation levers
- Provide structured insights (comparative and advisory only)
- Use benchmarks and negotiation heuristics from playbook
- LLM reasons to: identify leverage, explain gaps, suggest scenarios
- NO award decisions (human makes final choice)
- NO policy enforcement (Supervisor enforces policy)

Case Summary:
{case_summary.model_dump_json() if hasattr(case_summary, 'model_dump_json') else json.dumps(dict(case_summary))}

Key Findings (CRITICAL LEVERAGE):
{key_findings_text}

Target Supplier ID: {supplier_id}

User Intent / Instructions:
{user_intent if user_intent else "No specific instructions provided"}

Conversation History:
{json.dumps(conversation_history, indent=2) if conversation_history else "No previous conversation"}

Current Contract:
{json.dumps(contract, indent=2) if contract else "No existing contract"}

Supplier Performance:
{json.dumps(performance, indent=2) if performance else "No performance data"}

Market Context:
{json.dumps(market, indent=2) if market else "No market data"}

Retrieved Documents (Proposals / Contracts):
{retrieved_docs_text}

Create a negotiation plan (comparative and advisory). Consider:
1. Current contract terms and pricing (bid comparison)
2. Supplier performance and relationship (context)
3. Market benchmarks (from playbook - for grounding only)
4. Leverage points (identify gaps and opportunities)
5. Negotiation scenarios (suggest approaches, do not decide)
6. Specific user instructions (prioritize mentioned terms or levers)

Negotiation Playbook Context (for grounding only):
{json.dumps(negotiation_playbook, indent=2) if negotiation_playbook else "None"}

IMPORTANT:
- This plan is advisory - you do NOT make award decisions
- Policy enforcement is handled by Supervisor + humans
- Use benchmarks and heuristics as context, not as binding rules

Respond with a JSON object matching this EXACT schema:
{{
  "case_id": "{case_summary.case_id}",
  "category_id": "{case_summary.category_id}",
  "supplier_id": "{supplier_id}",
  "negotiation_objectives": ["Reduce unit price by 10%", "Extend payment terms to Net 45", "Include performance guarantees"],
  "target_terms": {{"price_reduction": "10%", "payment_terms": "Net 45", "warranty": "24 months"}},
  "leverage_points": ["Strong market competition available", "Volume commitment can be increased", "Long-term partnership value"],
  "fallback_positions": {{"minimum_price_reduction": "5%", "alternative_payment": "Net 30"}},
  "timeline": "Complete negotiations within 3 weeks",
  "risk_mitigation": ["Document all agreed terms in writing", "Include penalty clauses for non-performance", "Establish escalation procedures"]
}}

IMPORTANT: All list fields must contain simple strings, not objects.

Provide ONLY valid JSON, no markdown formatting."""

        llm_input_payload = {
            "case_summary": case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary),
            "supplier_id": supplier_id,
            "contract": contract,
            "supplier": supplier,
            "performance": performance,
            "market": market,
            "category": category,
            "requirements": requirements,
            "user_intent": user_intent
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
            print(f"DEBUG EXCEPTION IN NEGOTIATION AGENT: {e}")
            import traceback
            traceback.print_exc()
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



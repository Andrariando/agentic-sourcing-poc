"""
Negotiation Support Agent (DTP-04) with retrieval tools.
"""
import json
from typing import Dict, Any, Optional

from backend.agents.base import BaseAgent


class NegotiationAgent(BaseAgent):
    """
    Negotiation Support Agent for DTP-04.
    
    Uses retrieval tools to:
    - Get contract terms
    - Get supplier performance history
    - Get SLA events
    
    Creates negotiation plans grounded in data.
    NOTE: Does NOT execute negotiations or make awards.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("NegotiationSupport", tier)
    
    def execute(
        self,
        case_context: Dict[str, Any],
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Create negotiation plan.
        
        Returns plan with leverage points grounded in data.
        """
        case_id = case_context.get("case_id")
        category_id = case_context.get("category_id")
        supplier_id = case_context.get("supplier_id")
        
        if not supplier_id:
            return {
                "output": {
                    "case_id": case_id,
                    "error": "No supplier specified for negotiation"
                },
                "agent_name": self.name,
                "tokens_used": 0
            }
        
        # STEP 1: Retrieve contract documents
        retrieved_docs = self.retrieve_documents(
            query=f"contract terms negotiation {supplier_id}",
            supplier_id=supplier_id,
            category_id=category_id,
            dtp_stage="DTP-04",
            document_types=["Contract", "Performance Report"],
            top_k=5
        )
        
        # STEP 2: Get supplier performance
        supplier_perf = self.get_supplier_performance(
            supplier_id=supplier_id,
            category_id=category_id
        )
        
        # STEP 3: Get SLA events for leverage
        sla_events = self.get_sla_events(
            supplier_id=supplier_id
        )
        
        # STEP 4: Build negotiation prompt
        prompt = self._build_negotiation_prompt(
            case_context, user_intent, retrieved_docs, supplier_perf, sla_events
        )
        
        # STEP 5: Call LLM
        try:
            response, input_tokens, output_tokens = self.call_llm(prompt)
            
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except:
                    response = {"negotiation_objectives": [response]}
            
            grounded_in = [
                chunk.get("metadata", {}).get("document_id")
                for chunk in retrieved_docs.get("chunks", [])
                if chunk.get("metadata", {}).get("document_id")
            ]
            
            return {
                "output": {
                    "case_id": case_id,
                    "category_id": category_id,
                    "supplier_id": supplier_id,
                    "negotiation_objectives": response.get("negotiation_objectives", []),
                    "target_terms": response.get("target_terms", {}),
                    "leverage_points": response.get("leverage_points", []),
                    "fallback_positions": response.get("fallback_positions", {}),
                    "timeline": response.get("timeline", ""),
                    "risk_mitigation": response.get("risk_mitigation", []),
                    "grounded_in": grounded_in
                },
                "agent_name": self.name,
                "tokens_used": input_tokens + output_tokens,
                "retrieval_context": {
                    "documents_retrieved": len(retrieved_docs.get("chunks", [])),
                    "performance_available": len(supplier_perf.get("records", [])) > 0,
                    "sla_events_count": len(sla_events.get("records", []))
                }
            }
            
        except Exception as e:
            return {
                "output": {
                    "case_id": case_id,
                    "supplier_id": supplier_id,
                    "negotiation_objectives": ["Unable to create plan - insufficient data"],
                    "error": str(e)
                },
                "agent_name": self.name,
                "tokens_used": 0,
                "error": str(e)
            }
    
    def _build_negotiation_prompt(
        self,
        case_context: Dict[str, Any],
        user_intent: str,
        retrieved_docs: Dict[str, Any],
        supplier_perf: Dict[str, Any],
        sla_events: Dict[str, Any]
    ) -> str:
        """Build negotiation planning prompt."""
        
        doc_context = ""
        if retrieved_docs and retrieved_docs.get("chunks"):
            doc_context = "\n\n--- CONTRACT/PERFORMANCE DATA ---\n"
            for chunk in retrieved_docs["chunks"]:
                doc_context += f"\n[Document: {chunk.get('metadata', {}).get('filename', 'Unknown')}]\n"
                doc_context += chunk.get("content", "")[:800] + "\n"
        
        perf_context = ""
        if supplier_perf and supplier_perf.get("summary"):
            perf_context = "\n\n--- SUPPLIER PERFORMANCE ---\n"
            perf_context += json.dumps(supplier_perf.get("summary", {}), indent=2)
        
        sla_context = ""
        if sla_events and sla_events.get("summary"):
            sla_context = "\n\n--- SLA EVENTS ---\n"
            sla_context += json.dumps(sla_events.get("summary", {}), indent=2)
        
        return f"""You are a Negotiation Support Agent (DTP-04).

IMPORTANT: You provide negotiation SUPPORT only. You do NOT:
- Execute negotiations
- Make awards or commitments
- Approve terms

CASE CONTEXT:
- Case ID: {case_context.get('case_id')}
- Category: {case_context.get('category_id')}
- Supplier: {case_context.get('supplier_id')}

USER REQUEST:
{user_intent}

{doc_context}
{perf_context}
{sla_context}

INSTRUCTIONS:
1. Analyze the contract and performance data
2. Identify leverage points from SLA events and performance gaps
3. Suggest negotiation objectives and target terms
4. Ground all recommendations in the retrieved data
5. Include fallback positions

Respond with JSON:
{{
    "negotiation_objectives": ["objective 1", "objective 2"],
    "target_terms": {{"term": "target value"}},
    "leverage_points": ["leverage point citing data"],
    "fallback_positions": {{"term": "fallback value"}},
    "timeline": "Recommended negotiation timeline",
    "risk_mitigation": ["risk mitigation strategy"]
}}

Provide ONLY valid JSON."""


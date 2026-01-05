"""
Signal Interpretation Agent with retrieval tools.
"""
import json
from typing import Dict, Any, Optional

from backend.agents.base import BaseAgent


class SignalAgent(BaseAgent):
    """
    Signal Interpretation Agent.
    
    Interprets signals (contract expiry, performance alerts, etc.)
    and recommends actions grounded in data.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("SignalInterpretation", tier)
    
    def execute(
        self,
        case_context: Dict[str, Any],
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Interpret a signal and recommend action.
        """
        signal = case_context.get("signal", {})
        category_id = signal.get("category_id") or case_context.get("category_id")
        supplier_id = signal.get("supplier_id") or case_context.get("supplier_id")
        contract_id = signal.get("contract_id") or case_context.get("contract_id")
        
        # STEP 1: Retrieve relevant context
        retrieved_docs = self.retrieve_documents(
            query=f"signal {signal.get('signal_type', '')} {category_id}",
            supplier_id=supplier_id,
            category_id=category_id,
            document_types=["Contract", "Performance Report", "Policy"],
            top_k=5
        )
        
        # STEP 2: Get structured data
        supplier_perf = None
        if supplier_id:
            supplier_perf = self.get_supplier_performance(supplier_id=supplier_id)
        
        # STEP 3: Build prompt
        prompt = self._build_signal_prompt(
            signal, retrieved_docs, supplier_perf
        )
        
        # STEP 4: Call LLM
        try:
            response, input_tokens, output_tokens = self.call_llm(prompt)
            
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except:
                    response = {"recommended_action": "Monitor", "assessment": response}
            
            grounded_in = [
                chunk.get("metadata", {}).get("document_id")
                for chunk in retrieved_docs.get("chunks", [])
                if chunk.get("metadata", {}).get("document_id")
            ]
            
            return {
                "output": {
                    "signal_id": signal.get("signal_id", ""),
                    "category_id": category_id,
                    "assessment": response.get("assessment", ""),
                    "recommended_action": response.get("recommended_action", "Monitor"),
                    "confidence": response.get("confidence", 0.7),
                    "rationale": response.get("rationale", []),
                    "urgency_score": response.get("urgency_score", 5),
                    "contract_id": contract_id,
                    "supplier_id": supplier_id,
                    "grounded_in": grounded_in
                },
                "agent_name": self.name,
                "tokens_used": input_tokens + output_tokens
            }
            
        except Exception as e:
            return {
                "output": {
                    "signal_id": signal.get("signal_id", ""),
                    "recommended_action": "Monitor",
                    "assessment": "Unable to assess signal",
                    "error": str(e)
                },
                "agent_name": self.name,
                "tokens_used": 0,
                "error": str(e)
            }
    
    def _build_signal_prompt(
        self,
        signal: Dict[str, Any],
        retrieved_docs: Dict[str, Any],
        supplier_perf: Optional[Dict[str, Any]]
    ) -> str:
        """Build signal interpretation prompt."""
        
        doc_context = ""
        if retrieved_docs and retrieved_docs.get("chunks"):
            doc_context = "\n\n--- RETRIEVED CONTEXT ---\n"
            for chunk in retrieved_docs["chunks"]:
                doc_context += chunk.get("content", "")[:500] + "\n"
        
        perf_context = ""
        if supplier_perf and supplier_perf.get("summary"):
            perf_context = "\n\n--- SUPPLIER PERFORMANCE ---\n"
            perf_context += json.dumps(supplier_perf.get("summary", {}), indent=2)
        
        return f"""You are a Signal Interpretation Agent.

SIGNAL:
- Type: {signal.get('signal_type', 'Unknown')}
- Severity: {signal.get('severity', 'Medium')}
- Description: {signal.get('description', '')}
- Category: {signal.get('category_id', '')}
- Supplier: {signal.get('supplier_id', 'N/A')}

{doc_context}
{perf_context}

Assess this signal and recommend an action.
Ground your assessment in the retrieved data.

Respond with JSON:
{{
    "assessment": "Brief assessment of the signal",
    "recommended_action": "Renew" | "Renegotiate" | "RFx" | "Monitor" | "Terminate",
    "confidence": 0.0-1.0,
    "rationale": ["reason 1", "reason 2"],
    "urgency_score": 1-10
}}

Provide ONLY valid JSON."""







"""
Strategy Agent (DTP-01) with retrieval tools.
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from backend.agents.base import BaseAgent


class StrategyAgent(BaseAgent):
    """
    Strategy Agent for DTP-01.
    
    Uses retrieval tools to:
    - Get contract documents
    - Get supplier performance data
    - Get market reports
    
    All recommendations must be grounded in retrieved data.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("Strategy", tier)
    
    def execute(
        self,
        case_context: Dict[str, Any],
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute strategy analysis.
        
        Returns strategy recommendation grounded in retrieved data.
        """
        case_id = case_context.get("case_id")
        category_id = case_context.get("category_id")
        supplier_id = case_context.get("supplier_id")
        contract_id = case_context.get("contract_id")
        
        # STEP 1: Retrieve relevant documents
        retrieved_docs = self.retrieve_documents(
            query=f"sourcing strategy {category_id} contract renewal",
            case_id=case_id,
            category_id=category_id,
            dtp_stage="DTP-01",
            document_types=["Contract", "Policy", "Market Report"],
            top_k=5
        )
        
        # STEP 2: Get structured data if supplier exists
        supplier_data = None
        if supplier_id:
            supplier_data = self.get_supplier_performance(
                supplier_id=supplier_id,
                category_id=category_id
            )
        
        spend_data = None
        if category_id:
            spend_data = self.get_supplier_spend(category_id=category_id)
        
        # STEP 3: Build grounded prompt
        prompt = self._build_strategy_prompt(
            case_context, user_intent, retrieved_docs, supplier_data, spend_data
        )
        
        # STEP 4: Call LLM for analysis
        try:
            response, input_tokens, output_tokens = self.call_llm(prompt)
            
            # Parse JSON response
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except:
                    response = {"recommended_strategy": "Monitor", "rationale": [response]}
            
            # Add grounding information
            grounded_in = [
                chunk.get("metadata", {}).get("document_id")
                for chunk in retrieved_docs.get("chunks", [])
                if chunk.get("metadata", {}).get("document_id")
            ]
            
            return {
                "output": {
                    "case_id": case_id,
                    "category_id": category_id,
                    "recommended_strategy": response.get("recommended_strategy", "Monitor"),
                    "confidence": response.get("confidence", 0.7),
                    "rationale": response.get("rationale", []),
                    "risk_assessment": response.get("risk_assessment", ""),
                    "timeline_recommendation": response.get("timeline_recommendation", ""),
                    "grounded_in": grounded_in
                },
                "agent_name": self.name,
                "tokens_used": input_tokens + output_tokens,
                "retrieval_context": {
                    "documents_retrieved": len(retrieved_docs.get("chunks", [])),
                    "supplier_data_available": supplier_data is not None,
                    "spend_data_available": spend_data is not None
                }
            }
            
        except Exception as e:
            return {
                "output": {
                    "case_id": case_id,
                    "category_id": category_id,
                    "recommended_strategy": "Monitor",
                    "confidence": 0.5,
                    "rationale": ["Unable to complete analysis - using fallback"],
                    "error": str(e)
                },
                "agent_name": self.name,
                "tokens_used": 0,
                "error": str(e)
            }
    
    def _build_strategy_prompt(
        self,
        case_context: Dict[str, Any],
        user_intent: str,
        retrieved_docs: Dict[str, Any],
        supplier_data: Optional[Dict[str, Any]],
        spend_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build strategy analysis prompt with retrieved context."""
        
        # Format retrieved documents
        doc_context = ""
        if retrieved_docs and retrieved_docs.get("chunks"):
            doc_context = "\n\n--- RETRIEVED DOCUMENTS ---\n"
            for chunk in retrieved_docs["chunks"]:
                doc_context += f"\n[Document: {chunk.get('metadata', {}).get('filename', 'Unknown')}]\n"
                doc_context += f"Type: {chunk.get('metadata', {}).get('document_type', 'Unknown')}\n"
                doc_context += chunk.get("content", "")[:800] + "\n"
        
        # Format supplier data
        supplier_context = ""
        if supplier_data and supplier_data.get("records"):
            supplier_context = "\n\n--- SUPPLIER PERFORMANCE DATA ---\n"
            supplier_context += json.dumps(supplier_data.get("summary", {}), indent=2)
        
        # Format spend data
        spend_context = ""
        if spend_data and spend_data.get("records"):
            spend_context = "\n\n--- SPEND DATA ---\n"
            spend_context += json.dumps(spend_data.get("summary", {}), indent=2)
        
        return f"""You are a Strategy Agent for sourcing decisions (DTP-01).

CASE CONTEXT:
- Case ID: {case_context.get('case_id')}
- Category: {case_context.get('category_id')}
- Supplier: {case_context.get('supplier_id', 'Not specified')}
- Contract: {case_context.get('contract_id', 'Not specified')}

USER REQUEST:
{user_intent}

{doc_context}
{supplier_context}
{spend_context}

INSTRUCTIONS:
1. Analyze the retrieved data to understand the current situation
2. Consider contract timing, supplier performance, and market conditions
3. Recommend ONE strategy: Renew, Renegotiate, RFx, Monitor, or Terminate
4. Ground your rationale in the specific data retrieved above
5. Do NOT make up facts - only use information from the retrieved context

Respond with JSON:
{{
    "recommended_strategy": "Renew" | "Renegotiate" | "RFx" | "Monitor" | "Terminate",
    "confidence": 0.0-1.0,
    "rationale": ["reason 1 citing data", "reason 2 citing data", "reason 3"],
    "risk_assessment": "Brief risk assessment based on data",
    "timeline_recommendation": "Recommended timeline"
}}

Provide ONLY valid JSON, no other text."""








"""
Supplier Evaluation Agent (DTP-03/04) with retrieval tools.
"""
import json
from typing import Dict, Any, Optional, List

from backend.agents.base import BaseAgent


class SupplierEvaluationAgent(BaseAgent):
    """
    Supplier Evaluation Agent for DTP-03/04.
    
    Uses retrieval tools to:
    - Get supplier performance reports
    - Get SLA event history
    - Get spend data
    
    All evaluations must be grounded in retrieved data.
    """
    
    def __init__(self, tier: int = 1):
        super().__init__("SupplierEvaluation", tier)
    
    def execute(
        self,
        case_context: Dict[str, Any],
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute supplier evaluation.
        
        Returns supplier shortlist grounded in retrieved data.
        """
        case_id = case_context.get("case_id")
        category_id = case_context.get("category_id")
        
        # STEP 1: Retrieve performance reports
        retrieved_docs = self.retrieve_documents(
            query=f"supplier performance evaluation {category_id}",
            category_id=category_id,
            dtp_stage="DTP-03",
            document_types=["Performance Report", "Contract"],
            top_k=5
        )
        
        # STEP 2: Get structured performance data for known suppliers
        # In a real system, we'd query for all suppliers in category
        supplier_data = {}
        
        # STEP 3: Get spend data for category
        spend_data = self.get_supplier_spend(category_id=category_id)
        
        # STEP 4: Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            case_context, user_intent, retrieved_docs, supplier_data, spend_data
        )
        
        # STEP 5: Call LLM for evaluation
        try:
            response, input_tokens, output_tokens = self.call_llm(prompt)
            
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except:
                    response = {"shortlisted_suppliers": [], "recommendation": response}
            
            grounded_in = [
                chunk.get("metadata", {}).get("document_id")
                for chunk in retrieved_docs.get("chunks", [])
                if chunk.get("metadata", {}).get("document_id")
            ]
            
            return {
                "output": {
                    "case_id": case_id,
                    "category_id": category_id,
                    "shortlisted_suppliers": response.get("shortlisted_suppliers", []),
                    "evaluation_criteria": response.get("evaluation_criteria", []),
                    "recommendation": response.get("recommendation", ""),
                    "top_choice_supplier_id": response.get("top_choice_supplier_id"),
                    "comparison_summary": response.get("comparison_summary", ""),
                    "grounded_in": grounded_in
                },
                "agent_name": self.name,
                "tokens_used": input_tokens + output_tokens,
                "retrieval_context": {
                    "documents_retrieved": len(retrieved_docs.get("chunks", [])),
                    "spend_data_available": spend_data is not None
                }
            }
            
        except Exception as e:
            return {
                "output": {
                    "case_id": case_id,
                    "category_id": category_id,
                    "shortlisted_suppliers": [],
                    "recommendation": "Unable to evaluate suppliers - insufficient data",
                    "error": str(e)
                },
                "agent_name": self.name,
                "tokens_used": 0,
                "error": str(e)
            }
    
    def _build_evaluation_prompt(
        self,
        case_context: Dict[str, Any],
        user_intent: str,
        retrieved_docs: Dict[str, Any],
        supplier_data: Dict[str, Any],
        spend_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build supplier evaluation prompt with retrieved context."""
        
        doc_context = ""
        if retrieved_docs and retrieved_docs.get("chunks"):
            doc_context = "\n\n--- RETRIEVED PERFORMANCE DATA ---\n"
            for chunk in retrieved_docs["chunks"]:
                doc_context += f"\n[Document: {chunk.get('metadata', {}).get('filename', 'Unknown')}]\n"
                doc_context += chunk.get("content", "")[:800] + "\n"
        
        spend_context = ""
        if spend_data and spend_data.get("records"):
            spend_context = "\n\n--- SPEND DATA ---\n"
            spend_context += json.dumps(spend_data.get("summary", {}), indent=2)
        
        return f"""You are a Supplier Evaluation Agent (DTP-03/04).

CASE CONTEXT:
- Case ID: {case_context.get('case_id')}
- Category: {case_context.get('category_id')}

USER REQUEST:
{user_intent}

{doc_context}
{spend_context}

INSTRUCTIONS:
1. Analyze the retrieved supplier data
2. Evaluate suppliers based on performance, quality, delivery, cost
3. Create a shortlist of qualified suppliers
4. Ground all assessments in the retrieved data
5. Do NOT make up supplier names or scores - only use data from context

Respond with JSON:
{{
    "shortlisted_suppliers": [
        {{
            "supplier_id": "SUP-XXX",
            "name": "Supplier Name",
            "score": 0.0-10.0,
            "strengths": ["strength 1", "strength 2"],
            "concerns": ["concern 1"] or []
        }}
    ],
    "evaluation_criteria": ["criterion 1", "criterion 2"],
    "recommendation": "Brief recommendation text",
    "top_choice_supplier_id": "SUP-XXX" or null,
    "comparison_summary": "Brief comparison"
}}

If no supplier data is available, return empty shortlist with explanation.
Provide ONLY valid JSON."""





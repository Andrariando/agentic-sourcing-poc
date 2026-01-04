"""
Base agent class with retrieval tools.
All agents inherit from this and use controlled retrieval.
"""
import os
import json
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from backend.rag.retriever import get_retriever


class BaseAgent(ABC):
    """
    Base class for all agents.
    
    Agents:
    - Can only retrieve data via explicit tools (retriever)
    - Cannot modify state directly
    - Return structured outputs
    - Must ground responses in retrieved data
    """
    
    def __init__(self, name: str, tier: int = 1):
        self.name = name
        self.tier = tier
        self.model_name = "gpt-4o-mini" if tier == 1 else "gpt-4o"
        self.temperature = 0.2 if tier == 1 else 0.1
        self.max_tokens = 2000 if tier == 1 else 4000
        
        self.retriever = get_retriever()
        
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key
            )
        else:
            self.llm = None
    
    def retrieve_documents(
        self,
        query: str,
        case_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        dtp_stage: Optional[str] = None,
        document_types: Optional[List[str]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve relevant documents for context.
        This is the ONLY way agents can access document data.
        """
        return self.retriever.retrieve_documents(
            query=query,
            case_id=case_id,
            supplier_id=supplier_id,
            category_id=category_id,
            dtp_stage=dtp_stage,
            document_types=document_types,
            top_k=top_k
        )
    
    def get_supplier_performance(
        self,
        supplier_id: str,
        category_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get supplier performance data.
        This is the ONLY way agents can access structured supplier data.
        """
        return self.retriever.get_supplier_performance(
            supplier_id=supplier_id,
            category_id=category_id
        )
    
    def get_supplier_spend(
        self,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get spend data for supplier or category."""
        return self.retriever.get_supplier_spend(
            supplier_id=supplier_id,
            category_id=category_id
        )
    
    def get_sla_events(
        self,
        supplier_id: str,
        severity: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get SLA events for a supplier."""
        return self.retriever.get_sla_events(
            supplier_id=supplier_id,
            severity=severity
        )
    
    def call_llm(
        self,
        prompt: str,
        output_schema: Optional[type] = None
    ) -> tuple[Any, int, int]:
        """
        Call LLM with prompt.
        
        Returns:
            (response_content, input_tokens, output_tokens)
        """
        if not self.llm:
            raise ValueError("LLM not initialized - OPENAI_API_KEY not set")
        
        response = self.llm.invoke(prompt)
        
        # Extract tokens
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'response_metadata') and response.response_metadata:
            usage = response.response_metadata.get('token_usage', {})
            input_tokens = usage.get('prompt_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0)
        
        content = response.content
        
        # Parse JSON if schema provided
        if output_schema and content:
            try:
                # Extract JSON from response
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                
                data = json.loads(json_str)
                return data, input_tokens, output_tokens
            except Exception:
                pass
        
        return content, input_tokens, output_tokens
    
    @abstractmethod
    def execute(
        self,
        case_context: Dict[str, Any],
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute agent task.
        
        Args:
            case_context: Case information from Supervisor
            user_intent: User's request
            
        Returns:
            Dict with agent output, grounded_in (doc IDs), tokens used
        """
        pass
    
    def _build_grounded_prompt(
        self,
        base_prompt: str,
        retrieved_context: Dict[str, Any]
    ) -> str:
        """Build prompt with retrieved context for grounding."""
        context_text = ""
        
        if retrieved_context and retrieved_context.get("chunks"):
            context_text = "\n\n--- RETRIEVED CONTEXT (ground your response in this) ---\n"
            for chunk in retrieved_context["chunks"]:
                context_text += f"\n[Source: {chunk.get('metadata', {}).get('filename', 'Unknown')}]\n"
                context_text += chunk.get("content", "")[:500] + "\n"
            context_text += "\n--- END RETRIEVED CONTEXT ---\n"
        
        return base_prompt + context_text






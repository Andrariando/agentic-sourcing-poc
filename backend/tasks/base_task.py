"""
Base task class for all agent sub-tasks.

Implements the decision logic hierarchy:
1. run_rules() - Deterministic rules/policy checks
2. run_retrieval() - ChromaDB + SQLite data retrieval
3. run_analytics() - Scoring/normalization/comparison
4. run_llm() - LLM narration ONLY after 1-3
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from shared.schemas import GroundingReference


@dataclass
class TaskResult:
    """Result from a task execution."""
    task_name: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    grounded_in: List[GroundingReference] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    tokens_used: int = 0
    execution_time_ms: int = 0
    
    def add_grounding(
        self,
        ref_id: str,
        ref_type: str,
        source_name: str = "",
        excerpt: Optional[str] = None
    ):
        """Add a grounding reference."""
        self.grounded_in.append(GroundingReference(
            ref_id=ref_id,
            ref_type=ref_type,
            source_name=source_name,
            excerpt=excerpt
        ))


class BaseTask(ABC):
    """
    Base class for all agent sub-tasks.
    
    Tasks follow a strict execution order:
    1. Rules - deterministic checks
    2. Retrieval - get data from DB/vector store
    3. Analytics - compute scores/metrics
    4. LLM - narrative generation (optional)
    
    Sub-tasks NEVER mutate case state directly.
    They only return TaskResult which the agent aggregates.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._retriever = None
        self._llm = None
    
    @property
    def retriever(self):
        """Lazy load retriever."""
        if self._retriever is None:
            from backend.rag.retriever import get_retriever
            self._retriever = get_retriever()
        return self._retriever
    
    @property
    def llm(self):
        """Lazy load LLM."""
        if self._llm is None:
            import os
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.2,
                    max_tokens=2000,
                    api_key=api_key
                )
        return self._llm
    
    def execute(self, context: Dict[str, Any]) -> TaskResult:
        """
        Execute task following the decision hierarchy.
        
        Args:
            context: Task context including case data, inputs, etc.
            
        Returns:
            TaskResult with data, grounding, and any errors
        """
        start_time = datetime.now()
        result = TaskResult(task_name=self.name)
        
        try:
            # Step 1: Run rules/policy checks
            rules_result = self.run_rules(context)
            result.data.update(rules_result.get("data", {}))
            result.grounded_in.extend(rules_result.get("grounded_in", []))
            
            # Check if rules short-circuit execution
            if rules_result.get("stop"):
                result.data["stopped_at"] = "rules"
                result.data["stop_reason"] = rules_result.get("stop_reason", "")
                return result
            
            # Step 2: Run retrieval
            retrieval_result = self.run_retrieval(context, rules_result)
            result.data.update(retrieval_result.get("data", {}))
            result.grounded_in.extend(retrieval_result.get("grounded_in", []))
            
            # Step 3: Run analytics
            analytics_result = self.run_analytics(context, rules_result, retrieval_result)
            result.data.update(analytics_result.get("data", {}))
            result.grounded_in.extend(analytics_result.get("grounded_in", []))
            
            # Step 4: Run LLM narration (optional)
            if self.needs_llm_narration(context, analytics_result):
                llm_result = self.run_llm(context, rules_result, retrieval_result, analytics_result)
                result.data.update(llm_result.get("data", {}))
                result.tokens_used = llm_result.get("tokens_used", 0)
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
        
        # Calculate execution time
        end_time = datetime.now()
        result.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return result
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 1: Run deterministic rules and policy checks.
        
        Override in subclass for task-specific rules.
        
        Returns:
            Dict with "data", "grounded_in", "stop" (optional), "stop_reason" (optional)
        """
        return {"data": {}, "grounded_in": []}
    
    def run_retrieval(
        self,
        context: Dict[str, Any],
        rules_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 2: Retrieve data from ChromaDB and/or SQLite.
        
        Override in subclass for task-specific retrieval.
        
        Returns:
            Dict with "data", "grounded_in"
        """
        return {"data": {}, "grounded_in": []}
    
    def run_analytics(
        self,
        context: Dict[str, Any],
        rules_result: Dict[str, Any],
        retrieval_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 3: Run analytics - scoring, normalization, comparison.
        
        Override in subclass for task-specific analytics.
        
        Returns:
            Dict with "data", "grounded_in"
        """
        return {"data": {}, "grounded_in": []}
    
    def needs_llm_narration(
        self,
        context: Dict[str, Any],
        analytics_result: Dict[str, Any]
    ) -> bool:
        """
        Determine if LLM narration is needed.
        
        Override in subclass. Default is False - prefer structured output.
        """
        return False
    
    def run_llm(
        self,
        context: Dict[str, Any],
        rules_result: Dict[str, Any],
        retrieval_result: Dict[str, Any],
        analytics_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 4: Generate LLM narration/summary.
        
        Only called if needs_llm_narration returns True.
        
        Returns:
            Dict with "data", "tokens_used"
        """
        return {"data": {}, "tokens_used": 0}
    
    def _call_llm(self, prompt: str) -> tuple[str, int]:
        """Helper to call LLM and get response with token count."""
        if not self.llm:
            return "", 0
        
        response = self.llm.invoke(prompt)
        tokens = 0
        if hasattr(response, 'response_metadata') and response.response_metadata:
            usage = response.response_metadata.get('token_usage', {})
            tokens = usage.get('total_tokens', 0)
        
        return response.content, tokens


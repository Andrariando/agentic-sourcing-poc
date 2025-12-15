"""
Base agent class with common functionality.
"""
from typing import Dict, Any, Optional
from utils.schemas import CaseSummary, CacheMeta
from utils.caching import get_cache_meta, set_cache
from utils.token_accounting import calculate_cost, update_budget_state, TIER_1_MAX_OUTPUT_TOKENS, TIER_2_MAX_OUTPUT_TOKENS
from utils.logging_utils import create_agent_log
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
import json
import os


class BaseAgent:
    """Base class for all agents"""
    
    def __init__(self, name: str, tier: int = 1):
        self.name = name
        self.tier = tier
        self.model_name = "gpt-4o-mini" if tier == 1 else "gpt-4o"
        self.max_output_tokens = TIER_1_MAX_OUTPUT_TOKENS if tier == 1 else TIER_2_MAX_OUTPUT_TOKENS
        self.temperature = 0.2 if tier == 1 else 0.1
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_output_tokens,
            api_key=api_key
        )
    
    def check_cache(
        self,
        case_id: str,
        normalized_intent: str,
        case_summary: CaseSummary,
        question_text: str = "",
        additional_inputs: Dict[str, Any] = None
    ) -> tuple[CacheMeta, Optional[Any]]:
        """Check cache for existing result"""
        return get_cache_meta(case_id, self.name, normalized_intent, case_summary, question_text, additional_inputs)
    
    def call_llm_with_schema(
        self,
        prompt: str,
        schema: type[BaseModel],
        retry_on_invalid: bool = True
    ) -> tuple[BaseModel, Dict[str, Any], int, int]:
        """
        Call LLM with structured output schema.
        Returns (parsed_output, raw_response_dict, input_tokens, output_tokens)
        """
        try:
            # Use structured output if available (LangChain supports this)
            response = self.llm.invoke(prompt)
            
            # Extract tokens from response metadata if available
            if hasattr(response, 'response_metadata') and response.response_metadata:
                usage = response.response_metadata.get('token_usage', {})
                input_tokens = usage.get('prompt_tokens', len(prompt.split()) * 1.3)
                output_tokens = usage.get('completion_tokens', len(response.content.split()) * 1.3)
            else:
                # Fallback estimation
                input_tokens = int(len(prompt.split()) * 1.3)
                output_tokens = int(len(response.content.split()) * 1.3)
            
            # Try to parse as JSON first
            try:
                # Try to extract JSON from response
                content = response.content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                
                # Remove markdown code blocks if present
                json_str = json_str.strip().strip("```").strip()
                
                data = json.loads(json_str)
                parsed = schema(**data)
                return parsed, data, int(input_tokens), int(output_tokens)
            except (json.JSONDecodeError, Exception) as e:
                if retry_on_invalid:
                    # Retry with stricter prompt
                    strict_prompt = f"{prompt}\n\nIMPORTANT: Respond with ONLY valid JSON, no markdown, no explanations."
                    response = self.llm.invoke(strict_prompt)
                    content = response.content.strip().strip("```").strip()
                    data = json.loads(content)
                    parsed = schema(**data)
                    return parsed, data, int(input_tokens), int(output_tokens)
                else:
                    # Fallback to template
                    raise ValueError(f"Failed to parse LLM response: {e}")
        except Exception as e:
            raise ValueError(f"LLM call failed: {e}")
    
    def create_fallback_output(self, schema: type[BaseModel], case_id: str, category_id: str) -> BaseModel:
        """Create fallback output when LLM fails"""
        # This should be overridden by each agent
        raise NotImplementedError("Subclasses must implement create_fallback_output")


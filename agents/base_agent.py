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
                
                # Normalize data to fix common LLM output issues
                data = self._normalize_llm_output(data, schema)
                
                parsed = schema(**data)
                return parsed, data, int(input_tokens), int(output_tokens)
            except (json.JSONDecodeError, Exception) as e:
                if retry_on_invalid:
                    # Retry with stricter prompt
                    strict_prompt = f"{prompt}\n\nIMPORTANT: Respond with ONLY valid JSON, no markdown, no explanations. All list fields must contain simple strings, not objects."
                    response = self.llm.invoke(strict_prompt)
                    content = response.content.strip().strip("```").strip()
                    data = json.loads(content)
                    
                    # Normalize data to fix common LLM output issues
                    data = self._normalize_llm_output(data, schema)
                    
                    parsed = schema(**data)
                    return parsed, data, int(input_tokens), int(output_tokens)
                else:
                    # Fallback to template
                    raise ValueError(f"Failed to parse LLM response as JSON: {e}")
        except Exception as e:
            # Provide more specific error messages
            error_str = str(e)
            if "api_key" in error_str.lower() or "authentication" in error_str.lower():
                raise ValueError(f"OpenAI API authentication failed. Please check your OPENAI_API_KEY environment variable. Error: {e}")
            elif "rate" in error_str.lower() and "limit" in error_str.lower():
                raise ValueError(f"OpenAI API rate limit reached. Please wait and try again. Error: {e}")
            elif "connection" in error_str.lower() or "network" in error_str.lower():
                raise ValueError(f"Network connection error. Please check your internet connection. Error: {e}")
            else:
                raise ValueError(f"LLM call failed: {e}")
    
    def _normalize_llm_output(self, data: Dict[str, Any], schema: type[BaseModel]) -> Dict[str, Any]:
        """
        Normalize LLM output to fix common schema mismatches.
        Converts objects to strings where string lists are expected.
        """
        # Fields that should be List[str] but LLM sometimes returns List[Dict]
        string_list_fields = [
            "evaluation_criteria",
            "rationale", 
            "strengths",
            "concerns",
            "leverage_points",
            "risk_mitigation",
            "negotiation_objectives",
            "questions",
            "missing_information",
            "suggested_options",
            "inconsistencies"
        ]
        
        for field in string_list_fields:
            if field in data and isinstance(data[field], list):
                normalized = []
                for item in data[field]:
                    if isinstance(item, str):
                        normalized.append(item)
                    elif isinstance(item, dict):
                        # Convert dict to string - try common keys first
                        if "name" in item:
                            normalized.append(str(item["name"]))
                        elif "criterion" in item:
                            normalized.append(str(item["criterion"]))
                        elif "description" in item:
                            normalized.append(str(item["description"]))
                        elif "text" in item:
                            normalized.append(str(item["text"]))
                        elif "value" in item:
                            normalized.append(str(item["value"]))
                        else:
                            # Just use the first value or stringify the whole thing
                            values = list(item.values())
                            if values:
                                normalized.append(str(values[0]))
                            else:
                                normalized.append(str(item))
                    else:
                        normalized.append(str(item))
                data[field] = normalized
        
        # Normalize nested structures (like shortlisted_suppliers)
        if "shortlisted_suppliers" in data and isinstance(data["shortlisted_suppliers"], list):
            for supplier in data["shortlisted_suppliers"]:
                if isinstance(supplier, dict):
                    for field in ["strengths", "concerns"]:
                        if field in supplier and isinstance(supplier[field], list):
                            normalized = []
                            for item in supplier[field]:
                                if isinstance(item, str):
                                    normalized.append(item)
                                elif isinstance(item, dict):
                                    values = list(item.values())
                                    normalized.append(str(values[0]) if values else str(item))
                                else:
                                    normalized.append(str(item))
                            supplier[field] = normalized
        
        return data
    
    def create_fallback_output(self, schema: type[BaseModel], case_id: str, category_id: str) -> BaseModel:
        """Create fallback output when LLM fails"""
        # This should be overridden by each agent
        raise NotImplementedError("Subclasses must implement create_fallback_output")


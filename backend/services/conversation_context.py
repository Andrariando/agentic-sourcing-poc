"""
Conversation Context Manager - Cost-aware conversation memory.

Manages conversation history with intelligent context selection,
summarization, and cost estimation to enable ChatGPT-like multi-turn
conversations while maintaining cost controls.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
from sqlmodel import select
from datetime import datetime

from backend.persistence.database import get_db_session
from backend.persistence.models import ChatMessage as ChatMessageModel
from backend.services.case_service import CaseService

logger = logging.getLogger(__name__)

# Try to import tiktoken for accurate token estimation
try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    logger.warning("tiktoken not available, using approximation for token estimation")


class ConversationContextManager:
    """
    Manages conversation context with cost awareness.
    
    Features:
    - Retrieve recent messages within token budget
    - Summarize older conversations
    - Estimate token costs before execution
    - Filter messages by relevance
    """
    
    def __init__(self, case_service: CaseService):
        self.case_service = case_service
        self.max_context_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "1500"))
        self.recent_messages_count = int(os.getenv("RECENT_MESSAGES_COUNT", "10"))
        self.summarize_threshold = int(os.getenv("SUMMARIZE_THRESHOLD", "20"))
        self.enable_summarization = os.getenv("ENABLE_SUMMARIZATION", "true").lower() == "true"
        
        # Initialize tiktoken encoding if available
        self.encoding = None
        if HAS_TIKTOKEN:
            try:
                self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
            except Exception as e:
                logger.warning(f"Failed to initialize tiktoken: {e}")
                self.encoding = None
    
    def estimate_context_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Estimate token count for message list.
        
        Uses tiktoken if available, else approximation (4 chars ≈ 1 token).
        """
        if not messages:
            return 0
        
        if self.encoding:
            try:
                total = 0
                for msg in messages:
                    # Format: "role: content\n"
                    text = f"{msg['role']}: {msg['content']}\n"
                    total += len(self.encoding.encode(text))
                return total
            except Exception as e:
                logger.warning(f"Token estimation error: {e}, falling back to approximation")
        
        # Fallback: approximation (4 characters per token - conservative)
        total_chars = sum(len(f"{m['role']}: {m['content']}\n") for m in messages)
        return int(total_chars / 4)
    
    def get_recent_messages(
        self,
        case_id: str,
        limit: int = 50
    ) -> List[ChatMessageModel]:
        """Retrieve recent messages for a case, ordered by creation time."""
        session = get_db_session()
        try:
            messages = session.exec(
                select(ChatMessageModel)
                .where(ChatMessageModel.case_id == case_id)
                .order_by(ChatMessageModel.created_at.desc())
                .limit(limit)
            ).all()
            session.close()
            # Return in chronological order (oldest first)
            return list(reversed(messages))
        except Exception as e:
            logger.error(f"Error retrieving messages for case {case_id}: {e}")
            session.close()
            return []
    
    def get_relevant_context(
        self,
        case_id: str,
        current_message: str,
        max_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get relevant conversation history within token budget.
        
        Strategy:
        1. Get recent messages (last N)
        2. If total tokens > threshold, summarize older messages
        3. Return formatted context list
        
        Returns: List of {role, content} dicts for LLM prompt
        """
        max_tokens = max_tokens or self.max_context_tokens
        
        # Get recent messages
        all_messages = self.get_recent_messages(case_id, limit=100)
        
        if not all_messages:
            return []
        
        # Start with most recent messages
        recent_messages = all_messages[-self.recent_messages_count:]
        
        # Convert to dict format
        context = [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages
        ]
        
        # Estimate tokens
        estimated_tokens = self.estimate_context_tokens(context)
        
        # If we have more messages and tokens are under budget, try to include more
        if len(all_messages) > self.recent_messages_count:
            older_messages = all_messages[:-self.recent_messages_count]
            
            # If we have many older messages and summarization is enabled, summarize them
            if len(older_messages) > self.summarize_threshold and self.enable_summarization:
                try:
                    summary = self.summarize_conversation(case_id, [m.message_id for m in older_messages])
                    if summary:
                        # Add summary as a system message
                        summary_context = [{"role": "system", "content": f"Previous conversation summary: {summary}"}]
                        full_context = summary_context + context
                        full_tokens = self.estimate_context_tokens(full_context)
                        
                        if full_tokens <= max_tokens:
                            context = full_context
                        # If summary + recent is still too large, just use recent
                except Exception as e:
                    logger.warning(f"Summarization failed: {e}, using only recent messages")
            else:
                # Try to include more messages if under token limit
                for msg in reversed(older_messages):
                    test_context = [{"role": msg.role, "content": msg.content}] + context
                    test_tokens = self.estimate_context_tokens(test_context)
                    if test_tokens <= max_tokens:
                        context = test_context
                    else:
                        break
        
        # Final check: trim if still over limit
        while self.estimate_context_tokens(context) > max_tokens and len(context) > 1:
            context = context[1:]  # Remove oldest message
        
        return context
    
    def summarize_conversation(
        self,
        case_id: str,
        message_ids: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Create cost-effective summary of older messages.
        Uses cheaper model (gpt-4o-mini) for summarization.
        
        TODO: Implement LLM-based summarization (future enhancement)
        For now, returns None (summarization not implemented yet).
        This allows the system to work without summarization.
        """
        # Future: Implement with LLM call to gpt-4o-mini
        # For now, return None to allow system to work without summarization
        return None
    
    def estimate_execution_cost(
        self,
        conversation_history: List[Dict[str, str]],
        user_message: str,
        agent_name: str,
        use_tier_2: bool = False
    ) -> Tuple[int, float]:
        """
        Estimate tokens and cost before execution.
        
        Returns: (estimated_tokens, estimated_cost_usd)
        """
        # Estimate context tokens
        context_tokens = self.estimate_context_tokens(conversation_history)
        
        # Estimate user message tokens
        user_tokens = self.estimate_context_tokens([{"role": "user", "content": user_message}])
        
        # Estimate agent execution (varies by agent, use average)
        # Base tokens for agent prompt construction
        agent_base_tokens = 500  # Conservative estimate
        
        # Estimate output tokens (varies by agent)
        output_tokens = 500  # Conservative estimate
        
        total_input_tokens = context_tokens + user_tokens + agent_base_tokens
        total_tokens = total_input_tokens + output_tokens
        
        # Calculate cost (using current OpenAI pricing)
        if use_tier_2:
            input_cost = (total_input_tokens / 1000) * 5.00  # GPT-4o input
            output_cost = (output_tokens / 1000) * 15.00  # GPT-4o output
        else:
            input_cost = (total_input_tokens / 1000) * 0.15  # GPT-4o-mini input
            output_cost = (output_tokens / 1000) * 0.60  # GPT-4o-mini output
        
        total_cost = input_cost + output_cost
        
        return total_tokens, total_cost
    
    def save_message(
        self,
        case_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Persist chat message to database.
        
        Returns: message_id
        """
        metadata = metadata or {}
        
        session = get_db_session()
        try:
            message = ChatMessageModel(
                message_id=str(uuid4()),
                case_id=case_id,
                role=role,
                content=content,
                intent_classified=metadata.get("intent"),
                agents_called=json.dumps(metadata.get("agents_called", [])) if metadata.get("agents_called") else None,
                tokens_used=metadata.get("tokens_used"),
                estimated_cost_usd=metadata.get("estimated_cost_usd")
            )
            session.add(message)
            session.commit()
            session.refresh(message)
            message_id = message.message_id
            session.close()
            return message_id
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error saving message: {e}")
            raise


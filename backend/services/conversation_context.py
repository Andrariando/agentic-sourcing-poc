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
from backend.services.llm_provider import get_langchain_chat_model

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
        self.summary_intent_key = "memory_summary_v1"
        self.max_structured_memory_chars = int(os.getenv("MAX_STRUCTURED_MEMORY_CHARS", "2400"))
        
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
            structured_memory = self._build_structured_case_memory(case_id)
            if not structured_memory:
                return []
            return [{"role": "system", "content": structured_memory}]

        # Exclude summary-cache rows from normal chat replay; they are injected explicitly.
        all_messages = [
            m for m in all_messages
            if str(getattr(m, "intent_classified", "") or "") != self.summary_intent_key
        ]
        if not all_messages:
            structured_memory = self._build_structured_case_memory(case_id)
            if not structured_memory:
                return []
            return [{"role": "system", "content": structured_memory}]
        
        # Start with most recent messages
        recent_messages = all_messages[-self.recent_messages_count:]
        
        # Convert to dict format
        context = [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages
        ]
        
        # Estimate tokens
        estimated_tokens = self.estimate_context_tokens(context)
        
        summary_context: List[Dict[str, str]] = []
        structured_memory = self._build_structured_case_memory(case_id)
        if structured_memory:
            summary_context.append({"role": "system", "content": structured_memory})

        # If we have more messages and tokens are under budget, try to include more
        if len(all_messages) > self.recent_messages_count:
            older_messages = all_messages[:-self.recent_messages_count]
            
            # If we have many older messages and summarization is enabled, summarize them
            if len(older_messages) > self.summarize_threshold and self.enable_summarization:
                try:
                    summary = self.summarize_conversation(case_id, [m.message_id for m in older_messages])
                    if summary:
                        # Add summary as a system message
                        summary_context.append({"role": "system", "content": f"Previous conversation summary: {summary}"})
                        full_context = summary_context + context
                        full_tokens = self.estimate_context_tokens(full_context)
                        
                        if full_tokens <= max_tokens:
                            context = full_context
                        # If summary + recent is still too large, just use recent
                except Exception as e:
                    logger.warning(f"Summarization failed: {e}, using only recent messages")
                    if summary_context:
                        test_context = summary_context + context
                        if self.estimate_context_tokens(test_context) <= max_tokens:
                            context = test_context
            else:
                # Try to include more messages if under token limit
                for msg in reversed(older_messages):
                    test_context = [{"role": msg.role, "content": msg.content}] + context
                    test_tokens = self.estimate_context_tokens(test_context)
                    if test_tokens <= max_tokens:
                        context = test_context
                    else:
                        break
                if summary_context:
                    test_context = summary_context + context
                    if self.estimate_context_tokens(test_context) <= max_tokens:
                        context = test_context
        elif summary_context:
            test_context = summary_context + context
            if self.estimate_context_tokens(test_context) <= max_tokens:
                context = test_context
        
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
        
        Uses a summary cache row keyed by the latest covered message_id to avoid
        regenerating summaries on every turn.
        """
        if not message_ids:
            return None

        # 1) Reuse cached summary when the covered history has not changed.
        target_last_id = str(message_ids[-1])
        cached = self._get_cached_summary(case_id, target_last_id)
        if cached:
            return cached

        # 2) Load older messages and build compact transcript.
        all_messages = self.get_recent_messages(case_id, limit=150)
        idx = set(str(m) for m in message_ids)
        selected = [m for m in all_messages if str(getattr(m, "message_id", "")) in idx]
        if not selected:
            return None

        transcript_lines: List[str] = []
        for m in selected:
            role = str(getattr(m, "role", "user") or "user")
            content = str(getattr(m, "content", "") or "").strip()
            if not content:
                continue
            transcript_lines.append(f"{role}: {content[:800]}")
            if len("\n".join(transcript_lines)) > 24000:
                break
        if not transcript_lines:
            return None
        transcript = "\n".join(transcript_lines)

        # 3) Ask a cheap model for durable memory summary; fallback to heuristic.
        prompt_system = (
            "You summarize procurement copilots for long-term memory.\n"
            "Output plain text with concise bullets under these headings:\n"
            "Decisions, Constraints, User preferences, Open questions.\n"
            "Keep only durable facts and explicit commitments.\n"
            "Do not include transient chatter."
        )
        prompt_user = f"Summarize this prior conversation:\n\n{transcript}"

        summary_text: Optional[str] = None
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            llm = get_langchain_chat_model(
                default_model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=450,
                deployment_env="AZURE_OPENAI_SUMMARY_DEPLOYMENT",
            )
            if llm is not None:
                out = llm.invoke(
                    [SystemMessage(content=prompt_system), HumanMessage(content=prompt_user)]
                )
                summary_text = str(getattr(out, "content", "") or "").strip()[:4000] or None
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
            summary_text = None

        if not summary_text:
            # Deterministic fallback summary for reliability without LLM creds.
            tail = transcript_lines[-18:]
            summary_text = "Decisions/constraints/preferences/open questions (fallback memory):\n- " + "\n- ".join(tail[:12])

        self._save_summary_cache(case_id, summary_text, target_last_id, len(selected))
        return summary_text

    def _build_structured_case_memory(self, case_id: str) -> Optional[str]:
        """
        Compact snapshot of human-editable case memory (stage intake + working docs).
        Injected as system context so edits remain sticky across long chats.
        """
        try:
            state = self.case_service.get_case_state(case_id) or {}
        except Exception:
            return None

        hd = state.get("human_decision") or {}
        if not isinstance(hd, dict):
            hd = {}

        lines: List[str] = []
        lines.append("Structured memory snapshot (human-confirmed inputs):")
        dtp_stage = str(state.get("dtp_stage") or "DTP-01")
        lines.append(f"- Current stage: {dtp_stage}")

        for stage, row in hd.items():
            if not isinstance(row, dict):
                continue
            intake = row.get("_stage_intake")
            if not isinstance(intake, dict):
                continue
            vals = intake.get("values")
            if not isinstance(vals, dict) or not vals:
                continue
            lines.append(f"- {stage} intake:")
            for k, v in list(vals.items())[:24]:
                sv = str(v).strip()
                if sv:
                    lines.append(f"  - {k}: {sv[:160]}")

        wd = state.get("working_documents") or {}
        if hasattr(wd, "model_dump"):
            try:
                wd = wd.model_dump()
            except Exception:
                wd = {}
        if isinstance(wd, dict):
            for role in ("rfx", "contract"):
                slot = wd.get(role)
                if not isinstance(slot, dict):
                    continue
                plain = str(slot.get("plain_text") or "").strip()
                if plain:
                    lines.append(f"- Working {role} draft exists ({len(plain)} chars)")

        text = "\n".join(lines).strip()
        if len(text) > self.max_structured_memory_chars:
            text = text[: self.max_structured_memory_chars] + "..."
        return text if len(text) > 60 else None

    def _get_cached_summary(self, case_id: str, covered_last_message_id: str) -> Optional[str]:
        session = get_db_session()
        try:
            row = session.exec(
                select(ChatMessageModel)
                .where(ChatMessageModel.case_id == case_id)
                .where(ChatMessageModel.intent_classified == self.summary_intent_key)
                .order_by(ChatMessageModel.created_at.desc())
                .limit(1)
            ).first()
            if not row:
                return None
            meta_raw = str(getattr(row, "agents_called", "") or "").strip()
            if not meta_raw:
                return None
            try:
                meta = json.loads(meta_raw)
            except json.JSONDecodeError:
                return None
            if str(meta.get("covered_last_message_id") or "") != covered_last_message_id:
                return None
            content = str(getattr(row, "content", "") or "").strip()
            return content or None
        finally:
            session.close()

    def _save_summary_cache(
        self,
        case_id: str,
        summary: str,
        covered_last_message_id: str,
        covered_message_count: int,
    ) -> None:
        session = get_db_session()
        try:
            msg = ChatMessageModel(
                message_id=str(uuid4()),
                case_id=case_id,
                role="assistant",
                content=summary,
                intent_classified=self.summary_intent_key,
                agents_called=json.dumps(
                    {
                        "covered_last_message_id": covered_last_message_id,
                        "covered_message_count": int(covered_message_count),
                    }
                ),
                created_at=datetime.now().isoformat(),
            )
            session.add(msg)
            session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist summary cache: {e}")
            session.rollback()
        finally:
            session.close()
    
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



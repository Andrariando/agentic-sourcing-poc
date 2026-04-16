"""
LLM revision pass for user working documents (RFX / contract plain text from Word).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from backend.services.llm_provider import get_langchain_chat_model

logger = logging.getLogger(__name__)


def revise_working_document_text(
    *,
    role: str,
    current_text: str,
    instruction: str,
    case_name: str,
    category_id: str,
    dtp_stage: str,
) -> Optional[str]:
    """
    Return full revised plain text, or None if API unavailable / error.
    """
    instr = (instruction or "").strip()
    if not instr:
        instr = "Improve clarity, fix inconsistencies, and strengthen procurement-appropriate language. Keep the same sections."

    doc_label = "RFx (RFP / RFQ / RFI) draft" if role == "rfx" else "contract / commercial draft"

    system = f"""You are a senior procurement counsel and sourcing lead helping edit a {doc_label}.
The user will paste the current plain-text version of a document (extracted from Microsoft Word).
Revise the ENTIRE document according to their instruction.

Rules:
- Output ONLY the revised document body as plain text. No preamble or postscript.
- Preserve logical structure: keep section headings as their own lines; keep numbered/bulleted lists readable.
- Do not add a title like "Here is the revised document".
- If the draft is empty or nonsense, produce a concise professional template appropriate for the case context."""

    user = f"""Case name: {case_name}
Category: {category_id}
DTP stage: {dtp_stage}

USER INSTRUCTION:
{instr}

CURRENT DRAFT (plain text):
{current_text[:98000]}
"""

    try:
        llm = get_langchain_chat_model(
            default_model="gpt-4o-mini",
            temperature=0.25,
            max_tokens=4096,
            deployment_env="AZURE_OPENAI_WORKING_DOC_DEPLOYMENT",
        )
        if llm is None:
            logger.warning("OpenAI/Azure configuration missing — cannot revise working document")
            return None
        msg = llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        out = (msg.content or "").strip()
        return out if out else None
    except Exception as e:
        logger.exception("revise_working_document_text failed: %s", e)
        return None

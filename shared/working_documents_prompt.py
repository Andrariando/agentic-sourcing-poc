"""
Format stored Word round-trip drafts for LLM prompts (copilot sees user-edited text).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

# Max characters per slot injected into prompts (full text still stored on case)
_DEFAULT_SLOT = 14_000


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def format_working_documents_for_prompt(working_documents: Optional[Any]) -> str:
    """
    Summarize RFX + contract working copies for the responder / intent model.
    ``working_documents`` is typically a dict or WorkingDocumentsState dump.
    """
    if not working_documents:
        return "—"
    if hasattr(working_documents, "model_dump"):
        data = working_documents.model_dump()
    elif isinstance(working_documents, dict):
        data = working_documents
    else:
        return "—"

    cap = _env_int("LLM_WORKING_DOC_SLOT_CHARS", _DEFAULT_SLOT)
    lines = []
    for key, label in (("rfx", "RFx / RFP draft (Word round-trip)"), ("contract", "Contract draft (Word round-trip)")):
        slot = data.get(key)
        if not slot or not isinstance(slot, dict):
            continue
        txt = (slot.get("plain_text") or "").strip()
        if not txt:
            continue
        src = slot.get("source_filename") or "—"
        meta = f"updated {slot.get('updated_at') or '?'} by {slot.get('updated_by') or '?'} from {src}"
        if len(txt) > cap:
            txt = txt[:cap] + "\n… [truncated for prompt; full text stored on case]"
        lines.append(f"### {label}\n({meta})\n\n{txt}")
    return "\n\n".join(lines) if lines else "—"

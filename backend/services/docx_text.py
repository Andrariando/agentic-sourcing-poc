"""Extract plain text from .docx bytes (shared by ingestion and working-document upload)."""
from __future__ import annotations

import io
from typing import List


def extract_text_from_docx_bytes(content: bytes) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(content))
    text_parts: List[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)
    return "\n\n".join(text_parts)

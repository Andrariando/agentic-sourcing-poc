"""
Optional LLM interpreter helpers for the Heatmap scoring system.

Goal: make the system more robust to messy / semi-structured inputs without
making the scoring engine LLM-dependent.

Design:
- Only invoked as a fallback when deterministic parsing fails or inputs are missing.
- Returns structured JSON, validated + clamped on the server before use.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, Tuple

from backend.services.llm_provider import get_openai_client, resolve_chat_model


def _interpreter_model() -> str:
    default_model = os.getenv("HEATMAP_INTERPRETER_MODEL") or "gpt-4o-mini"
    return resolve_chat_model(default_model, deployment_env="AZURE_OPENAI_HEATMAP_INTERPRETER_DEPLOYMENT")


def _openai_client():
    return get_openai_client()


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_iso_date(s: str) -> bool:
    return bool(_ISO_DATE_RE.match((s or "").strip()))


def extract_expiration_date_iso(
    contract_details: Dict[str, Any],
) -> Tuple[Optional[str], float, str, bool]:
    """
    Try to extract an ISO expiration date (YYYY-MM-DD) from a messy contract_details dict.

    Returns: (expiration_date_iso, confidence_0_1, note, used_llm)
    """
    if not isinstance(contract_details, dict) or not contract_details:
        return None, 0.0, "No contract_details available for extraction.", False

    client = _openai_client()
    if not client:
        return None, 0.0, "LLM interpreter unavailable (missing OpenAI/Azure configuration).", False

    # Keep the payload small and safe.
    # Prefer the most likely fields, but also include a short flattened blob.
    exp = str(contract_details.get("Expiration Date") or "").strip()
    eff = str(contract_details.get("Effective Date") or "").strip()
    title = str(contract_details.get("Contract Title") or contract_details.get("Title") or "").strip()

    # Flatten a subset of keys to avoid sending huge dictionaries.
    flat_pairs = []
    for k in sorted(contract_details.keys()):
        if k in ("Expiration Date", "Effective Date", "Contract Title", "Title"):
            continue
        v = contract_details.get(k)
        if v is None:
            continue
        sv = str(v).strip()
        if not sv:
            continue
        if len(sv) > 220:
            sv = sv[:217] + "..."
        flat_pairs.append(f"{k}: {sv}")
        if len(flat_pairs) >= 24:
            break
    flat_blob = "\n".join(flat_pairs)

    prompt = f"""You extract structured fields from messy contract metadata.

Return ONLY valid JSON with keys:
- expiration_date_iso: string in format YYYY-MM-DD or null if unknown
- confidence: number between 0 and 1
- note: short reason (one sentence)

Rules:
- Prefer explicit "Expiration Date" if present.
- If multiple dates exist, choose the contract END/EXPIRATION date (not effective/start).
- If only month/year is available, set expiration_date_iso to null and explain in note.
- Do NOT guess wildly; use null when uncertain.

INPUT (may be incomplete):
Contract Title: {title or "(none)"}
Expiration Date field: {exp or "(empty)"}
Effective Date field: {eff or "(empty)"}
Other fields:
{flat_blob or "(none)"}
"""

    try:
        resp = client.chat.completions.create(
            model=_interpreter_model(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=220,
        )
        import json

        data = json.loads(resp.choices[0].message.content or "{}")
        iso = data.get("expiration_date_iso")
        conf = float(data.get("confidence", 0) or 0)
        note = str(data.get("note", "") or "").strip()
    except Exception as e:
        return None, 0.0, f"LLM expiration extraction failed: {e!s}", False

    conf = max(0.0, min(1.0, conf))
    if isinstance(iso, str):
        iso = iso.strip()
    else:
        iso = None

    if iso and not _is_iso_date(iso):
        return None, conf, f"LLM returned non-ISO date '{iso}'.", True

    if not note:
        note = "Extracted from contract metadata."

    return iso, conf, note[:220], True


def normalize_preferred_status_token(raw_status: Optional[str]) -> Tuple[Optional[str], float, str, bool]:
    """
    Map messy preferred-supplier labels to a canonical token:
    preferred | allowed | nonpreferred | straightpo | unknown

    Returns: (normalized_token_or_none, confidence_0_1, note, used_llm)
    """
    s = (raw_status or "").strip()
    if not s:
        return None, 0.0, "No explicit preferred status provided.", False

    # Fast path: already looks canonical.
    t = s.lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "straight_to_po": "straightpo",
        "straighttopo": "straightpo",
        "non_preferred": "nonpreferred",
        "nonpreferred_supplier": "nonpreferred",
        "preferred_supplier": "preferred",
        "allowed_supplier": "allowed",
    }
    t = aliases.get(t, t)
    if t in ("preferred", "allowed", "nonpreferred", "straightpo", "unknown"):
        return t, 1.0, "Already canonical.", False

    client = _openai_client()
    if not client:
        return None, 0.0, "LLM interpreter unavailable to normalize status.", False

    prompt = f"""You normalize a supplier preference status label to a canonical token.

Return ONLY valid JSON:
{{
  "token": "preferred|allowed|nonpreferred|straightpo|unknown",
  "confidence": <number 0..1>,
  "note": "<one sentence>"
}}

Input label:
{s}
"""
    try:
        resp = client.chat.completions.create(
            model=_interpreter_model(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=160,
        )
        import json

        data = json.loads(resp.choices[0].message.content or "{}")
        token = str(data.get("token", "") or "").strip().lower()
        conf = float(data.get("confidence", 0) or 0)
        note = str(data.get("note", "") or "").strip()
    except Exception as e:
        return None, 0.0, f"LLM status normalization failed: {e!s}", True

    conf = max(0.0, min(1.0, conf))
    if token not in ("preferred", "allowed", "nonpreferred", "straightpo", "unknown"):
        return None, conf, f"LLM returned invalid token '{token}'.", True
    if not note:
        note = "Normalized from raw label."
    return token, conf, note[:220], True


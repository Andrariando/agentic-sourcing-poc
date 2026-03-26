"""
Retrieval + bounded adjustment from past human heatmap feedback (Chroma).
Uses OpenAI chat (gpt-4o-mini by default) when OPENAI_API_KEY is set; otherwise heuristic fallback.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.heatmap.persistence.heatmap_vector_store import get_heatmap_vector_store

MAX_ABS_DELTA = 0.6
TOP_K = 5


def _tier_from_total(total: float) -> str:
    if total >= 8.0:
        return "T1"
    if total >= 6.0:
        return "T2"
    if total >= 4.0:
        return "T3"
    return "T4"


def _build_query(
    *,
    category: str,
    subcategory: Optional[str],
    supplier_name: Optional[str],
    is_new: bool,
    baseline_summary: str,
) -> str:
    kind = "new sourcing request" if is_new else "contract renewal"
    parts = [
        category,
        subcategory or "",
        supplier_name or "",
        kind,
        baseline_summary,
    ]
    return " ".join(p for p in parts if p).strip() or baseline_summary


def _parse_chroma_results(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    docs = raw.get("documents") or []
    metas = raw.get("metadatas") or []
    if not docs or not isinstance(docs, list):
        return []
    row0 = docs[0] if docs and isinstance(docs[0], list) else docs
    m0 = metas[0] if metas and isinstance(metas[0], list) else (metas if metas else [])
    if not row0:
        return []
    out: List[Dict[str, Any]] = []
    for i, text in enumerate(row0):
        meta = m0[i] if i < len(m0) else {}
        out.append({"text": text or "", "meta": meta or {}})
    return out


def _retrieve_snippets(query: str, *, n_results: int = TOP_K) -> List[Dict[str, Any]]:
    query = (query or "").strip()
    if len(query) < 8:
        return []
    try:
        vs = get_heatmap_vector_store()
        raw = vs.search(query, n_results=n_results)
        return _parse_chroma_results(raw)
    except Exception:
        return []


def _deterministic_nudge(snippets: List[Dict[str, Any]], base_total: float) -> Tuple[float, str]:
    """Lightweight fallback when OpenAI is unavailable."""
    if not snippets:
        return 0.0, ""
    deltas: List[float] = []
    for s in snippets[:4]:
        meta = s.get("meta") or {}
        comp = str(meta.get("component") or "").lower()
        try:
            adj = float(meta.get("adjustment_value", 0) or 0)
        except (TypeError, ValueError):
            adj = 0.0
        if "tier" in comp:
            if adj >= 3.5:
                deltas.append(-0.12)
            elif adj <= 2.5:
                deltas.append(0.1)
        text_l = (s.get("text") or "").lower()
        if any(w in text_l for w in ("downgrade", "lower tier", "defer", "wait", "monitor")):
            deltas.append(-0.08)
        if any(w in text_l for w in ("critical", "escalate", "immediate", "urgent")):
            deltas.append(0.06)
    if not deltas:
        return 0.0, ""
    avg = sum(deltas) / len(deltas)
    avg = max(-MAX_ABS_DELTA, min(MAX_ABS_DELTA, avg))
    note = (
        f"Informed by {len(snippets)} similar past review(s); score nudged by {avg:+.2f} "
        "(deterministic fallback — set OPENAI_API_KEY for richer explanations)."
    )
    return round(avg, 2), note


def _llm_nudge(
    snippets: List[Dict[str, Any]],
    *,
    contract_blurb: str,
    baseline_summary: str,
    base_total: float,
    is_new: bool,
    weights: Optional[Dict[str, float]],
) -> Tuple[float, str]:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key or not snippets:
        return _deterministic_nudge(snippets, base_total)
    try:
        from openai import OpenAI
    except ImportError:
        return _deterministic_nudge(snippets, base_total)

    past_lines: List[str] = []
    for s in snippets[:4]:
        t = (s.get("text") or "").strip().replace("\n", " ")
        if len(t) > 450:
            t = t[:447] + "..."
        past_lines.append(f"- {t}")
    past_block = "\n".join(past_lines) if past_lines else "(none)"

    w = weights or {}
    if is_new:
        comp_keys = ["ius", "es", "csis", "sas"]
        w_block = {
            "w_ius": float(w.get("w_ius", 0.30)),
            "w_es": float(w.get("w_es", 0.30)),
            "w_csis": float(w.get("w_csis", 0.25)),
            "w_sas": float(w.get("w_sas", 0.15)),
        }
    else:
        comp_keys = ["eus", "fis", "rss", "scs", "sas"]
        w_block = {
            "w_eus": float(w.get("w_eus", 0.30)),
            "w_fis": float(w.get("w_fis", 0.25)),
            "w_rss": float(w.get("w_rss", 0.20)),
            "w_scs": float(w.get("w_scs", 0.15)),
            "w_sas": float(w.get("w_sas", 0.10)),
        }

    prompt = f"""You help a sourcing prioritization heatmap learn from how humans corrected past scores.

Current opportunity summary:
{contract_blurb}

Scoring engine baseline:
{baseline_summary}
Baseline total on 0–10 scale: {base_total:.2f}

Similar past human corrections from reviewers:
{past_block}

Weights used by the scoring engine (do not change these):
{json.dumps(w_block, indent=2)}

Task:
1) Propose SMALL bounded adjustments to component scores (not directly to the total) when clearly supported by similar past reviews.
2) Output deltas for the following components only: {", ".join(comp_keys)}.

Rules:
- Each component delta must be between -0.5 and 0.5 (inclusive). Use 0 when not applicable.
- Prefer sparse deltas (usually 0–2 components changed).
- These deltas will be applied to the baseline via the existing weighted formula; you are NOT directly setting tier.
- user_note: one concise sentence for a business user (no bullets). If all deltas are 0, say no strong precedent applied.

Respond with ONLY a JSON object:
{{
  "component_deltas": {{
    "{comp_keys[0]}": <number>,
    "...": <number>
  }},
  "user_note": "<string>"
}}"""

    model = os.getenv("HEATMAP_LEARNING_MODEL", "gpt-4o-mini")
    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.15,
            max_tokens=220,
        )
        content = (resp.choices[0].message.content or "").strip()
        data = json.loads(content)
        deltas_obj = data.get("component_deltas") or {}
        note = str(data.get("user_note", "")).strip()
    except Exception:
        return _deterministic_nudge(snippets, base_total)

    # Convert component deltas into a total delta via weights (still bounded).
    # Missing components default to 0.
    comp_delta: Dict[str, float] = {}
    for k in comp_keys:
        try:
            v = float((deltas_obj or {}).get(k, 0) or 0)
        except (TypeError, ValueError):
            v = 0.0
        v = max(-0.5, min(0.5, v))
        if abs(v) < 0.01:
            v = 0.0
        comp_delta[k] = round(v, 2)

    if is_new:
        total_delta = (
            w_block["w_ius"] * comp_delta["ius"]
            + w_block["w_es"] * comp_delta["es"]
            + w_block["w_csis"] * comp_delta["csis"]
            + w_block["w_sas"] * comp_delta["sas"]
        )
    else:
        total_delta = (
            w_block["w_eus"] * comp_delta["eus"]
            + w_block["w_fis"] * comp_delta["fis"]
            + w_block["w_rss"] * comp_delta["rss"]
            + w_block["w_scs"] * comp_delta["scs"]
            + w_block["w_sas"] * comp_delta["sas"]
        )

    delta = max(-MAX_ABS_DELTA, min(MAX_ABS_DELTA, float(total_delta)))
    delta = round(delta, 2)
    if abs(delta) < 0.01:
        delta = 0.0
    if not note:
        note = "Prior reviewer patterns reviewed; no material score change." if delta == 0 else f"Learning from past reviews (Δ{delta:+.2f})."
    note = re.sub(r"\s+", " ", note)[:320]
    return delta, note


def apply_learning_nudge(
    *,
    category: str,
    subcategory: Optional[str],
    supplier_name: Optional[str],
    is_new: bool,
    baseline_summary: str,
    base_total: float,
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, str, float, str]:
    """
    Retrieve similar feedback and compute bounded adjustment.

    Returns: delta, user_visible_note, adjusted_total, adjusted_tier
    """
    if (os.getenv("HEATMAP_LEARNING") or "1").lower() in ("0", "false", "no", "off"):
        b = max(0.0, min(10.0, float(base_total)))
        return 0.0, "", round(b, 2), _tier_from_total(b)

    base_total = max(0.0, min(10.0, float(base_total)))
    contract_blurb = (
        f"Category: {category}. Subcategory: {subcategory or '—'}. "
        f"Supplier: {supplier_name or '—'}. "
        f"Type: {'new intake request' if is_new else 'existing contract / renewal'}."
    )
    q = _build_query(
        category=category,
        subcategory=subcategory,
        supplier_name=supplier_name,
        is_new=is_new,
        baseline_summary=baseline_summary,
    )
    snippets = _retrieve_snippets(q)
    if not snippets:
        return 0.0, "", round(base_total, 2), _tier_from_total(base_total)

    delta, note = _llm_nudge(
        snippets,
        contract_blurb=contract_blurb,
        baseline_summary=baseline_summary,
        base_total=base_total,
        is_new=is_new,
        weights=weights,
    )
    adjusted = round(max(0.0, min(10.0, base_total + delta)), 2)
    tier = _tier_from_total(adjusted)
    return delta, note, adjusted, tier

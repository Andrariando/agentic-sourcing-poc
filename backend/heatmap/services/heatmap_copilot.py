"""
Heatmap copilot: explain-only Q&A over DB + feedback RAG, policy checks vs category cards,
and suggested category-card JSON (preview only — does not write files).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from backend.heatmap.context_builder import load_category_cards
from backend.heatmap.persistence.heatmap_models import Opportunity, ReviewFeedback
from backend.heatmap.persistence.heatmap_vector_store import get_heatmap_vector_store
from backend.heatmap.services.feedback_memory import _parse_chroma_results

MAX_OPPS_IN_CONTEXT = 80
MAX_FEEDBACK_ROWS = 40
CHROMA_QA_TOP_K = 8


def _copilot_model() -> str:
    return os.getenv("HEATMAP_COPILOT_MODEL") or os.getenv("HEATMAP_LEARNING_MODEL") or "gpt-4o-mini"


def _openai_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except ImportError:
        return None


def _format_opportunity_line(o: Opportunity) -> str:
    cid = o.contract_id or "—"
    rid = o.request_id or "—"
    sup = o.supplier_name or "—"
    parts = [
        f"id={o.id}",
        f"supplier={sup}",
        f"category={o.category}",
        f"subcat={o.subcategory or '—'}",
        f"contract_id={cid}",
        f"request_id={rid}",
        f"tier={o.tier}",
        f"total={o.total_score:.2f}",
        f"EUS={o.eus_score}",
        f"IUS={o.ius_score}",
        f"FIS={o.fis_score}",
        f"ES={o.es_score}",
        f"RSS={o.rss_score}",
        f"SCS={o.scs_score}",
        f"CSIS={o.csis_score}",
        f"SAS={o.sas_score}",
        f"source={o.source}",
    ]
    return " | ".join(str(p) for p in parts)


def build_opportunities_context(session: Session) -> str:
    stmt = select(Opportunity).order_by(Opportunity.total_score.desc())
    rows = session.exec(stmt).all()
    if not rows:
        return "(No opportunities in database.)"
    lines = [_format_opportunity_line(o) for o in rows[:MAX_OPPS_IN_CONTEXT]]
    if len(rows) > MAX_OPPS_IN_CONTEXT:
        lines.append(f"... and {len(rows) - MAX_OPPS_IN_CONTEXT} more rows not shown.")
    return "\n".join(lines)


def build_sql_feedback_context(session: Session) -> str:
    stmt = select(ReviewFeedback).order_by(ReviewFeedback.timestamp.desc()).limit(MAX_FEEDBACK_ROWS * 3)
    rows = session.exec(stmt).all()
    rows = [r for r in rows if (r.comment_text or "").strip()][:MAX_FEEDBACK_ROWS]
    if not rows:
        return "(No feedback comments in SQLite.)"
    lines = []
    for r in rows:
        lines.append(
            f"opp_id={r.opportunity_id} | {r.component_affected} | {r.adjustment_type} "
            f"| val={r.adjustment_value} | reason={r.reason_code} | {r.comment_text[:500]}"
        )
    return "\n".join(lines)


def chroma_snippets_for_question(question: str) -> str:
    q = (question or "").strip()
    if len(q) < 3:
        return ""
    try:
        vs = get_heatmap_vector_store()
        raw = vs.search(q, n_results=CHROMA_QA_TOP_K)
        hits = _parse_chroma_results(raw)
    except Exception:
        return ""
    if not hits:
        return ""
    lines = []
    for h in hits:
        t = (h.get("text") or "").replace("\n", " ").strip()
        meta = h.get("meta") or {}
        if len(t) > 600:
            t = t[:597] + "..."
        lines.append(f"- {t} | meta={meta}")
    return "Similar stored reviewer notes (vector retrieval):\n" + "\n".join(lines)


def answer_heatmap_question(session: Session, question: str) -> Tuple[str, bool]:
    """
    Returns (answer_markdown_or_text, used_llm).
    """
    question = (question or "").strip()
    if len(question) < 3:
        return "Please enter a longer question.", False

    opps = build_opportunities_context(session)
    fb_sql = build_sql_feedback_context(session)
    fb_chroma = chroma_snippets_for_question(question)

    context = f"""=== OPPORTUNITIES (authoritative scores & tiers) ===
{opps}

=== RECENT FEEDBACK COMMENTS (SQLite) ===
{fb_sql}

=== VECTOR-RETRIEVED FEEDBACK SNIPPETS (may overlap SQLite) ===
{fb_chroma or "(none)"}
"""

    client = _openai_client()
    if not client:
        return (
            "OpenAI API key is not configured. Showing raw context only (first 4000 chars):\n\n"
            + context[:4000],
            False,
        )

    prompt = f"""You are a procurement heatmap analyst assistant.

Rules (must follow):
1) Use ONLY information in <DATA> below for facts (scores, tiers, supplier names, categories). Do not invent opportunities.
2) You MUST NOT change, recalculate, or contradict the stored total_score or tier — treat them as ground truth.
3) For comparisons ("why is X above Y"), locate both rows in <DATA> by supplier name and/or request_id/contract_id/id. Compare total_score and tier; briefly cite relevant sub-scores if present.
4) If you cannot find an entity in <DATA>, say so clearly instead of guessing.
5) Be concise (2–6 short paragraphs or bullet list). Plain English.

<DATA>
{context}
</DATA>

USER QUESTION:
{question}
"""

    try:
        resp = client.chat.completions.create(
            model=_copilot_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=900,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or "(No content returned.)", True
    except Exception as e:
        return f"The explanation service failed: {e!s}", False


def _norm_pref_token(raw: str) -> str:
    s = raw.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "non_preferred": "nonpreferred",
        "nonpreferred_supplier": "nonpreferred",
        "preferred_supplier": "preferred",
        "allowed_supplier": "allowed",
        "straight_to_po": "straightpo",
        "straighttopo": "straightpo",
    }
    return aliases.get(s, s)


def _validate_category_patch(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError("Proposed card must be a JSON object.")
    out: Dict[str, Any] = {}
    if "default_preferred_status" in obj:
        out["default_preferred_status"] = _norm_pref_token(str(obj["default_preferred_status"]))
    if "category_strategy_sas" in obj:
        out["category_strategy_sas"] = float(obj["category_strategy_sas"])
    if "supplier_preferred_status" in obj and isinstance(obj["supplier_preferred_status"], dict):
        sp: Dict[str, str] = {}
        for k, val in obj["supplier_preferred_status"].items():
            sp[str(k)] = _norm_pref_token(str(val))
        out["supplier_preferred_status"] = sp
    return out


def check_feedback_vs_policy(
    *,
    feedback_text: str,
    category: str,
    supplier_name: Optional[str],
    current_tier: Optional[str],
) -> Tuple[Dict[str, Any], bool]:
    """Returns { contradicts, severity, summary, suggestion } and used_llm."""
    feedback_text = (feedback_text or "").strip()
    category = (category or "").strip()
    if len(feedback_text) < 5:
        return {"contradicts": False, "severity": "none", "summary": "Feedback text too short.", "suggestion": ""}, False

    cards = load_category_cards()
    card = cards.get(category) or cards.get(category.strip(), {})
    policy_blob = json.dumps(card, indent=2) if card else "(No category card found for this category.)"

    client = _openai_client()
    if not client:
        return {
            "contradicts": False,
            "severity": "unknown",
            "summary": "OpenAI API key not set; cannot analyze policy alignment.",
            "suggestion": "Configure OPENAI_API_KEY for automatic checks.",
        }, False

    tier_hint = f"Current AI/human tier context: {current_tier}" if current_tier else "Tier context: unknown."
    sup_hint = f"Supplier: {supplier_name}" if supplier_name else ""

    prompt = f"""You check whether written human sourcing feedback aligns with CATEGORY POLICY (preferred supplier rules).

Category: {category}
{sup_hint}
{tier_hint}

CATEGORY POLICY (from category_cards.json for this category):
{policy_blob}

HUMAN FEEDBACK (reviewer comment / rationale):
{feedback_text}

Respond with ONLY valid JSON:
{{
  "contradicts": <true|false>,
  "severity": "none|low|medium|high",
  "summary": "<one or two sentences>",
  "suggestion": "<optional actionable hint for reviewer or policy admin; empty string if none>"
}}

"contradicts" means the feedback implies actions that conflict with preferred/allowed/nonpreferred guidance or category_strategy_sas intent. If policy block is empty, set contradicts false and explain in summary."""

    try:
        resp = client.chat.completions.create(
            model=_copilot_model(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=400,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return {
            "contradicts": bool(data.get("contradicts")),
            "severity": str(data.get("severity") or "none"),
            "summary": str(data.get("summary") or "").strip(),
            "suggestion": str(data.get("suggestion") or "").strip(),
        }, True
    except Exception as e:
        return {
            "contradicts": False,
            "severity": "error",
            "summary": f"Policy check failed: {e!s}",
            "suggestion": "",
        }, False


def assist_category_card_edit(*, category: str, instruction: str) -> Tuple[Dict[str, Any], bool]:
    """
    Returns { "category": str, "proposed_patch": dict, "notes": str } for manual merge into category_cards.json.
    """
    category = (category or "").strip()
    instruction = (instruction or "").strip()
    if len(category) < 1 or len(instruction) < 10:
        return {"category": category, "proposed_patch": {}, "notes": "Category and instruction (10+ chars) required."}, False

    cards = load_category_cards()
    current = cards.get(category) or cards.get(category.strip(), {})
    current_json = json.dumps(current, indent=2) if current else "{}"

    client = _openai_client()
    if not client:
        return {
            "category": category,
            "proposed_patch": {},
            "notes": "OPENAI_API_KEY not set.",
        }, False

    prompt = f"""You help edit sourcing category_cards.json entries.

Current JSON for category "{category}":
{current_json}

USER INSTRUCTION (what to change or add):
{instruction}

Provide ONLY valid JSON with this shape:
{{
  "proposed_patch": {{
    "default_preferred_status": "<optional>",
    "category_strategy_sas": <optional number 0-10>,
    "supplier_preferred_status": {{ "<Supplier Name>": "preferred|allowed|nonpreferred|straightpo" }}
  }},
  "notes": "<brief explanation of changes; mention any manual review needed>"
}}

Rules:
- Include ONLY keys that should change; omit keys that stay as-is.
- Supplier names must be concrete strings.
- Prefer conservative policy wording in notes if unsure."""

    try:
        resp = client.chat.completions.create(
            model=_copilot_model(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=800,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        patch_raw = data.get("proposed_patch") or {}
        notes = str(data.get("notes") or "").strip()
        patch = _validate_category_patch(patch_raw)
        return {"category": category, "proposed_patch": patch, "notes": notes}, True
    except Exception as e:
        return {"category": category, "proposed_patch": {}, "notes": f"Assist failed: {e!s}"}, False

"""
Heatmap copilot: explain-only Q&A over DB + feedback RAG, policy checks vs category cards,
and suggested category-card JSON (preview only — does not write files).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from backend.heatmap.context_builder import load_category_cards
from backend.heatmap.persistence.heatmap_models import Opportunity, ReviewFeedback
from backend.infrastructure.storage_providers import get_heatmap_vector_store
from backend.heatmap.services.feedback_memory import _parse_chroma_results
from backend.services.llm_provider import get_openai_client, resolve_chat_model

MAX_OPPS_IN_CONTEXT = 80
MAX_TARGETED_OPPS_IN_CONTEXT = 40
MAX_FEEDBACK_ROWS = 40
CHROMA_QA_TOP_K = 8


def _copilot_model() -> str:
    default_model = os.getenv("HEATMAP_COPILOT_MODEL") or os.getenv("HEATMAP_LEARNING_MODEL") or "gpt-4o-mini"
    return resolve_chat_model(default_model, deployment_env="AZURE_OPENAI_HEATMAP_COPILOT_DEPLOYMENT")


def _openai_client():
    return get_openai_client()


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
        f"status={o.status}",
        f"window={o.recommended_action_window or '—'}",
        f"contract_end_date={o.contract_end_date.isoformat() if o.contract_end_date else '—'}",
        f"est_spend_usd={o.estimated_spend_usd}",
        f"impl_months={o.implementation_timeline_months}",
    ]
    if o.contract_end_date:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        end_dt = o.contract_end_date
        if end_dt.tzinfo is not None:
            end_dt = end_dt.astimezone(tz=None).replace(tzinfo=None)
        days = int((end_dt - now).total_seconds() // 86400)
        parts.append(f"days_to_expiry={days}")
    if o.justification_summary:
        brief = str(o.justification_summary).replace("\n", " ").strip()
        if len(brief) > 180:
            brief = brief[:177] + "..."
        parts.append(f"justification={brief}")
    return " | ".join(str(p) for p in parts)


def _extract_query_terms(question: str) -> List[str]:
    q = (question or "").strip()
    if not q:
        return []
    terms: List[str] = []
    # Likely IDs (REQ-..., CNT-..., etc.)
    for t in re.findall(r"\b[A-Za-z]{2,6}-[A-Za-z0-9][A-Za-z0-9\-_]{2,}\b", q):
        terms.append(t.lower())
    # Quoted entity names ("CloudServe Group")
    for t in re.findall(r"\"([^\"]{3,})\"", q):
        terms.append(t.strip().lower())
    # Deduplicate, keep only meaningful terms.
    out: List[str] = []
    seen = set()
    for t in terms:
        tt = t.strip()
        if len(tt) < 3:
            continue
        if tt in seen:
            continue
        seen.add(tt)
        out.append(tt)
    return out


def _row_match_blob(o: Opportunity) -> str:
    return " ".join(
        [
            str(o.id or ""),
            str(o.supplier_name or ""),
            str(o.contract_id or ""),
            str(o.request_id or ""),
            str(o.request_title or ""),
            str(o.category or ""),
            str(o.subcategory or ""),
        ]
    ).lower()


def build_opportunities_context(session: Session, question: str = "") -> str:
    stmt = select(Opportunity).order_by(Opportunity.total_score.desc())
    rows = session.exec(stmt).all()
    if not rows:
        return "(No opportunities in database.)"

    top_rows = rows[:MAX_OPPS_IN_CONTEXT]
    lines = [_format_opportunity_line(o) for o in top_rows]

    query_terms = _extract_query_terms(question)
    if query_terms:
        top_ids = {int(o.id or -1) for o in top_rows}
        targeted: List[Opportunity] = []
        for o in rows:
            if int(o.id or -1) in top_ids:
                continue
            blob = _row_match_blob(o)
            if any(t in blob for t in query_terms):
                targeted.append(o)
            if len(targeted) >= MAX_TARGETED_OPPS_IN_CONTEXT:
                break
        if targeted:
            lines.append("")
            lines.append("=== TARGETED MATCHES FOR QUESTION TERMS ===")
            lines.extend(_format_opportunity_line(o) for o in targeted)

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

    opps = build_opportunities_context(session, question)
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
5) If asked about expiry timing, use `window` and `EUS` (expiry urgency score) to explain when action is needed.
6) If asked for score details, provide a short breakdown using total + available component scores (EUS/IUS/FIS/ES/RSS/SCS/CSIS/SAS) and mention the tier.
7) Be concise (2–6 short paragraphs or bullet list). Plain English.

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
    if "scoring_mix" in obj:
        from backend.heatmap.category_scoring_mix import validate_scoring_mix_for_patch

        sm = validate_scoring_mix_for_patch(obj["scoring_mix"])
        if sm is not None:
            out["scoring_mix"] = sm
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
            "summary": "OpenAI/Azure OpenAI is not configured; cannot analyze policy alignment.",
            "suggestion": "Configure OPENAI_API_KEY or AZURE_OPENAI_* variables for automatic checks.",
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
            "notes": "OpenAI/Azure OpenAI is not configured.",
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
    "supplier_preferred_status": {{ "<Supplier Name>": "preferred|allowed|nonpreferred|straightpo" }},
    "scoring_mix": {{
      "plain_english": "<optional note for humans; ignored by scoring>",
      "new_sourcing_request": {{
        "implementation_urgency_IUS": 0.30,
        "estimated_spend_ES": 0.30,
        "category_spend_importance_CSIS": 0.25,
        "strategic_alignment_SAS": 0.15
      }},
      "existing_contract_renewal": {{
        "expiry_urgency_EUS": 0.30,
        "financial_impact_FIS": 0.25,
        "supplier_risk_RSS": 0.20,
        "spend_concentration_SCS": 0.15,
        "strategic_alignment_SAS": 0.10
      }}
    }}
  }},
  "notes": "<brief explanation of changes; mention any manual review needed>"
}}

Rules:
- Include ONLY keys that should change; omit keys that stay as-is.
- scoring_mix: block names must be exactly "new_sourcing_request" and/or "existing_contract_renewal" (or aliases contract, new_request, ps_new, ps_contract, renewal). Weight key names must match the examples (human-readable suffixes _IUS, _ES, etc.).
- Percentages are shares of the formula for that row type; they should sum to about 1.0 (server renormalizes).
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


_STATUS_PATTERN = re.compile(
    r"\b(preferred|allowed|non[\s\-_]?preferred|straight[\s\-_]?to[\s\-_]?po|straightpo)\b",
    re.IGNORECASE,
)
_SAS_PATTERN = re.compile(
    r"\b(?:category[_\s-]*strategy[_\s-]*sas|sas|strategy score)\b[^0-9-]{0,24}(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _clip_sas(value: float) -> float:
    return max(0.0, min(10.0, float(value)))


def _extract_patch_from_unstructured_text(raw_text: str) -> Dict[str, Any]:
    """
    Quick-win deterministic parser for freeform category policy notes.
    Recognizes:
      - default status hints
      - category_strategy_sas numeric hint
      - per-supplier status lines
    """
    text = (raw_text or "").strip()
    if not text:
        return {}

    patch: Dict[str, Any] = {}
    supplier_map: Dict[str, str] = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for line in lines:
        # Parse common line forms:
        # "Supplier X: preferred", "Supplier X - allowed", "Supplier X = non preferred"
        if ":" in line:
            left, right = line.split(":", 1)
        elif " - " in line:
            left, right = line.split(" - ", 1)
        elif "=" in line:
            left, right = line.split("=", 1)
        else:
            left, right = "", line

        m_status = _STATUS_PATTERN.search(right)
        if m_status:
            status = _norm_pref_token(m_status.group(1))
            left_clean = left.strip(" -*\t")
            left_l = left_clean.lower()
            if left_clean and "default" not in left_l and "supplier default" not in left_l:
                supplier_map[left_clean] = status
            elif "default" in line.lower():
                patch["default_preferred_status"] = status

        m_sas = _SAS_PATTERN.search(line)
        if m_sas:
            try:
                patch["category_strategy_sas"] = _clip_sas(float(m_sas.group(1)))
            except ValueError:
                pass

    # Additional default hints in paragraph text.
    if "default_preferred_status" not in patch:
        low = text.lower()
        if "default" in low:
            m = _STATUS_PATTERN.search(text)
            if m:
                patch["default_preferred_status"] = _norm_pref_token(m.group(1))

    if supplier_map:
        patch["supplier_preferred_status"] = supplier_map
    return _validate_category_patch(patch)


def assist_category_card_from_unstructured(
    *,
    category: str,
    raw_text: str,
) -> Tuple[Dict[str, Any], bool]:
    """
    Build a category_cards-style patch from unstructured text.
    Returns payload and used_llm (always False for deterministic quick-win path).
    """
    category = (category or "").strip()
    raw_text = (raw_text or "").strip()
    if len(category) < 1:
        return {"category": category, "proposed_patch": {}, "notes": "Category is required."}, False
    if len(raw_text) < 20:
        return {
            "category": category,
            "proposed_patch": {},
            "notes": "Provide more policy text (at least 20 chars) for extraction.",
        }, False

    patch = _extract_patch_from_unstructured_text(raw_text)
    if not patch:
        return {
            "category": category,
            "proposed_patch": {},
            "notes": "No structured policy signals detected; refine text with supplier:status or SAS hints.",
        }, False
    return {
        "category": category,
        "proposed_patch": patch,
        "notes": "Extracted from unstructured text. Review before merging into category_cards.json.",
    }, False

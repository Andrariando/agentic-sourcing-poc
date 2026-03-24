"""
Stage-aware copilot hints derived from DTP_DECISIONS and recorded human_decision.
Used by Case API and LLM prompts so chat feels proactive without duplicating form state.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared.decision_definitions import DTP_DECISIONS


def _answer_filled(answers: Dict[str, Any], qid: str) -> bool:
    v = answers.get(qid)
    if v is None:
        return False
    if isinstance(v, dict):
        return bool(v.get("answer") and str(v.get("answer")).strip())
    return bool(str(v).strip())


def build_copilot_focus(dtp_stage: str, human_decision: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    stage_def = DTP_DECISIONS.get(dtp_stage)
    if not stage_def:
        return {
            "stage": dtp_stage,
            "stage_title": dtp_stage,
            "stage_description": "",
            "pending_questions": [],
            "suggested_chat_prompts": [
                "What's next for this case?",
                "Summarize risks I should watch.",
            ],
        }

    hd = human_decision or {}
    stage_block = hd.get(dtp_stage) or {}
    if not isinstance(stage_block, dict):
        stage_block = {}

    pending: List[Dict[str, Any]] = []
    for q in stage_def.get("questions", []):
        if not q.get("required", False):
            continue
        if "dependency" in q:
            dep_key, dep_val = list(q["dependency"].items())[0]
            dep_obj = stage_block.get(dep_key) or {}
            parental = dep_obj.get("answer") if isinstance(dep_obj, dict) else dep_obj
            if parental != dep_val:
                continue
        qid = q["id"]
        if not _answer_filled(stage_block, qid):
            opts = q.get("options") or []
            pending.append(
                {
                    "id": qid,
                    "text": q.get("text", ""),
                    "type": q.get("type", "choice"),
                    "option_labels": [o.get("label", str(o.get("value", ""))) for o in opts],
                }
            )

    prompts: List[str] = []
    if pending:
        first = pending[0]
        prompts.append(f"Help me decide: {first['text']}")
        if first.get("option_labels"):
            prompts.append("What are the tradeoffs between the main options?")
        prompts.append("What would you recommend and why?")
        if len(pending) > 1:
            prompts.append(f"I also need clarity on: {pending[1]['text']}")
    else:
        prompts.append("What's the smartest next step from here?")
        prompts.append("What should I watch out for if we advance?")

    return {
        "stage": dtp_stage,
        "stage_title": stage_def.get("title", ""),
        "stage_description": stage_def.get("description", ""),
        "pending_questions": pending,
        "suggested_chat_prompts": prompts[:4],
    }


def format_copilot_focus_for_prompt(focus: Optional[Dict[str, Any]]) -> str:
    if not focus:
        return ""
    lines = [
        f"Current stage: {focus.get('stage', '')} — {focus.get('stage_title', '')}",
        f"Stage purpose: {focus.get('stage_description', '')}",
    ]
    pq = focus.get("pending_questions") or []
    if pq:
        lines.append("Open formal decisions this stage (help user reason before they record answers elsewhere):")
        for q in pq:
            labels = q.get("option_labels") or []
            opt_txt = f" Options: {' | '.join(labels)}" if labels else ""
            lines.append(f"  - [{q.get('id')}]: {q.get('text', '')}{opt_txt}")
    else:
        lines.append("All formal checklist items for this stage appear complete; focus on next-step advice and risk.")
    return "\n".join(lines)

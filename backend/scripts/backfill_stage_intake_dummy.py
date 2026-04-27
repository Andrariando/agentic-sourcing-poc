#!/usr/bin/env python3
"""
Backfill missing System 2 stage-intake values with editable dummy defaults.

Purpose:
- Pre-fill every existing case with a complete stage-intake payload for DTP-01..DTP-06
- Preserve any human-entered values already stored
- Keep everything editable in the copilot UI

Run from repo root:
  python backend/scripts/backfill_stage_intake_dummy.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Dict, Any

from sqlmodel import Session, select

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.persistence.database import get_engine, init_db
from backend.persistence.models import CaseState


def _safe_text(v: Any, fallback: str) -> str:
    t = str(v or "").strip()
    return t if t else fallback


def _stage_defaults(case: CaseState) -> Dict[str, Dict[str, str]]:
    today = date.today()
    req_start = (today + timedelta(days=90)).isoformat()
    rfx_issue = (today + timedelta(days=7)).isoformat()
    rfx_due = (today + timedelta(days=28)).isoformat()
    owner_signoff = (today + timedelta(days=45)).isoformat()
    legal_signoff = (today + timedelta(days=50)).isoformat()

    case_name = _safe_text(getattr(case, "name", None), "S2C Case")
    category = _safe_text(getattr(case, "category_id", None), "General Services")
    supplier = _safe_text(getattr(case, "supplier_id", None), "TBD Supplier")
    contract_id = _safe_text(getattr(case, "contract_id", None), "CT-TBD-001")
    spend = _safe_text(getattr(case, "estimated_spend_usd", None), "1200000")

    return {
        "DTP-01": {
            "request_title": case_name,
            "business_unit": "IT Infrastructure",
            "scope_summary": f"Initial sourcing scope for {category}; baseline assumptions prefilled for user refinement.",
            "estimated_annual_value_usd": spend,
            "required_start_date": req_start,
            "implementation_urgency": "6-12 months",
        },
        "DTP-02": {
            "evaluation_criteria": "Commercial fit 30%; technical fit 35%; delivery capacity 20%; risk/compliance 15%.",
            "mandatory_requirements": "Security baseline compliance; data residency alignment; auditability and SLA traceability.",
            "supplier_longlist": f"{supplier}\nAlternative Supplier A\nAlternative Supplier B",
            "risk_constraints": "No high unresolved security risk; legal exceptions require explicit signoff.",
        },
        "DTP-03": {
            "rfx_title": f"RFX-{today.year}-{_safe_text(case.case_id, 'CASE')}",
            "rfx_issue_date": rfx_issue,
            "response_due_date": rfx_due,
            "supplier_clarification_feedback": "Clarification tracker initialized; vendor questions to be consolidated weekly.",
        },
        "DTP-04": {
            "supplier_response_received": "2/3",
            "supplier_evaluation_feedback": "Initial evaluation indicates acceptable baseline capability; commercial terms under review.",
            "negotiation_feedback": "Requested price harmonization and clearer implementation milestones.",
            "award_recommendation": f"Recommend shortlist leader with fallback option; current lead: {supplier}.",
        },
        "DTP-05": {
            "contract_signed": "no",
            "contract_owner_signoff": f"Owner signoff pending - target {owner_signoff}",
            "legal_signoff": f"Legal signoff pending - target {legal_signoff}",
            "contract_reference": contract_id,
        },
        "DTP-06": {
            "execution_started": "no",
            "implementation_milestones": "Kickoff; design validation; pilot; production rollout.",
            "kpi_monitoring_status": "KPI dashboard baseline configured; first monthly checkpoint pending.",
            "execution_confirmed_by_human": "no",
        },
    }


def _merge_intake(existing: Dict[str, Any], defaults: Dict[str, str]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for key, default_value in defaults.items():
        current = existing.get(key)
        if str(current or "").strip():
            merged[key] = str(current)
        else:
            merged[key] = default_value
    return merged


def _working_doc_templates(case: CaseState) -> Dict[str, Dict[str, str]]:
    today = date.today().isoformat()
    case_name = _safe_text(getattr(case, "name", None), "S2C Case")
    category = _safe_text(getattr(case, "category_id", None), "General Services")
    supplier = _safe_text(getattr(case, "supplier_id", None), "TBD Supplier")
    contract_id = _safe_text(getattr(case, "contract_id", None), "CT-TBD-001")
    rfx_text = (
        f"RFx Working Draft - {case_name}\n"
        f"Date: {today}\n\n"
        "1. Background\n"
        f"- Category: {category}\n"
        f"- Business Need: Source and contract suitable suppliers for {category}.\n\n"
        "2. Scope\n"
        "- Define technical and commercial requirements.\n"
        "- Confirm implementation timeline and governance checkpoints.\n\n"
        "3. Evaluation Approach\n"
        "- Technical fit, commercial fit, delivery capability, and risk/compliance.\n\n"
        "4. Response Requirements\n"
        "- Supplier must provide implementation plan, pricing model, and SLA commitments.\n"
    )
    contract_text = (
        f"Contract Working Draft - {case_name}\n"
        f"Date: {today}\n\n"
        "1. Parties\n"
        f"- Buyer: Internal Procurement Team\n"
        f"- Supplier: {supplier}\n\n"
        "2. Reference\n"
        f"- Contract Reference: {contract_id}\n\n"
        "3. Scope of Services\n"
        f"- Category: {category}\n"
        "- Deliverables, milestones, and acceptance criteria to be confirmed.\n\n"
        "4. Commercial Terms\n"
        "- Pricing, payment terms, and change-control governance.\n\n"
        "5. Risk and Compliance\n"
        "- Security, legal, and audit obligations.\n"
    )
    return {
        "rfx": {"plain_text": rfx_text, "source_filename": "dummy_rfx_prefill.docx"},
        "contract": {"plain_text": contract_text, "source_filename": "dummy_contract_prefill.docx"},
    }


def _chat_prefill_messages(case: CaseState) -> list[dict[str, str]]:
    stage = _safe_text(getattr(case, "dtp_stage", None), "DTP-01")
    category = _safe_text(getattr(case, "category_id", None), "General Services")
    return [
        {
            "role": "assistant",
            "content": (
                "I have prefilled a baseline workspace so you can edit quickly. "
                "Please review critical fields first, then ask me to extract or refine details."
            ),
            "timestamp": datetime.now().isoformat(),
        },
        {
            "role": "assistant",
            "content": (
                f"Current stage: {stage}. Category context: {category}. "
                "I can help draft RFx/contract language after you confirm missing fields."
            ),
            "timestamp": datetime.now().isoformat(),
        },
    ]


def main() -> None:
    print("=" * 72)
    print("Backfilling stage-intake dummy values for all existing System 2 cases")
    print("=" * 72)

    init_db()
    engine = get_engine()
    touched_cases = 0
    touched_stages = 0
    touched_working_docs = 0
    touched_chat_seed = 0

    with Session(engine) as session:
        cases = session.exec(select(CaseState)).all()
        for case in cases:
            try:
                hd = json.loads(case.human_decision) if case.human_decision else {}
                if not isinstance(hd, dict):
                    hd = {}
            except json.JSONDecodeError:
                hd = {}

            defaults_by_stage = _stage_defaults(case)
            case_changed = False

            for stage, defaults in defaults_by_stage.items():
                row = hd.get(stage)
                if not isinstance(row, dict):
                    row = {}
                intake = row.get("_stage_intake")
                if not isinstance(intake, dict):
                    intake = {}
                existing_values = intake.get("values")
                if not isinstance(existing_values, dict):
                    existing_values = {}

                merged_values = _merge_intake(existing_values, defaults)
                if merged_values != existing_values or not intake:
                    row["_stage_intake"] = {
                        "values": merged_values,
                        "source": "dummy_prefill_backfill",
                        "updated_by": "system-backfill",
                        "updated_at": datetime.now().isoformat(),
                    }
                    hd[stage] = row
                    touched_stages += 1
                    case_changed = True

            # Deeper layer: prefill editable working-document slots if missing.
            templates = _working_doc_templates(case)
            wd_changed = False
            wd: Dict[str, Any] = {}
            if case.working_documents_json:
                try:
                    loaded = json.loads(case.working_documents_json)
                    if isinstance(loaded, dict):
                        wd = loaded
                except json.JSONDecodeError:
                    wd = {}
            for role, tpl in templates.items():
                slot = wd.get(role)
                has_text = isinstance(slot, dict) and str(slot.get("plain_text") or "").strip()
                if has_text:
                    continue
                wd[role] = {
                    "plain_text": tpl["plain_text"],
                    "source_filename": tpl["source_filename"],
                    "updated_at": datetime.now().isoformat(),
                    "updated_by": "system-backfill",
                }
                wd_changed = True
            if wd_changed:
                case.working_documents_json = json.dumps(wd)
                touched_working_docs += 1
                case_changed = True

            # Deeper layer: seed lightweight chat guidance if empty.
            if not str(case.chat_history or "").strip():
                case.chat_history = json.dumps(_chat_prefill_messages(case))
                touched_chat_seed += 1
                case_changed = True

            if case_changed:
                case.human_decision = json.dumps(hd)
                case.updated_at = datetime.now().isoformat()
                session.add(case)
                touched_cases += 1

        session.commit()

    print(f"Cases updated: {touched_cases}")
    print(f"Stage intake records updated: {touched_stages}")
    print(f"Working-document slots prefilled: {touched_working_docs}")
    print(f"Chat history seeded: {touched_chat_seed}")
    print("=" * 72)
    print("Done. All existing cases now have editable baseline stage-intake context.")
    print("=" * 72)


if __name__ == "__main__":
    main()


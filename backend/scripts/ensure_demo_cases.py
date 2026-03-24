#!/usr/bin/env python3
"""
Refresh CASE-001..006 demo payloads, fix legacy 'Heatmap Approved:' titles on bridged cases,
and clear copilot-only governance flags from stored human_decision (so UI matches pre-approval).

Run from repo root:
  python backend/scripts/ensure_demo_cases.py
"""
import json
import sys
from pathlib import Path

from sqlmodel import Session, select

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.persistence.database import get_engine, init_db
from backend.persistence.models import CaseState
from backend.heatmap.services.case_bridge import get_case_bridge_service
from backend.scripts.seed_it_demo_data import upsert_pillar_cases


def rename_heatmap_prefixed_cases(session: Session) -> int:
    bridge = get_case_bridge_service()
    rows = session.exec(
        select(CaseState).where(CaseState.name.startswith("Heatmap Approved:"))
    ).all()
    n = 0
    for c in rows:
        supplier = (
            (c.supplier_id or "").strip()
            or c.name.replace("Heatmap Approved:", "").strip()
            or "New request"
        )
        template = bridge._find_template_case(c.category_id or "")
        if template and template.name:
            c.name = f"{supplier} – {template.name}"
        else:
            c.name = f"{supplier} – {c.category_id}"
        session.add(c)
        n += 1
    session.commit()
    return n


def strip_governance_console_flags(session: Session) -> int:
    """Remove Next.js copilot governance_* keys from all stages (demo reset)."""
    rows = session.exec(select(CaseState)).all()
    changed = 0
    for c in rows:
        if not c.human_decision:
            continue
        try:
            hd = json.loads(c.human_decision)
        except json.JSONDecodeError:
            continue
        modified = False
        for stage_answers in hd.values():
            if not isinstance(stage_answers, dict):
                continue
            for key in ("governance_soc2_status", "governance_infra_status"):
                if key in stage_answers:
                    del stage_answers[key]
                    modified = True
        if modified:
            c.human_decision = json.dumps(hd)
            session.add(c)
            changed += 1
    session.commit()
    return changed


def main():
    print("=" * 60)
    print("Ensure demo pillar cases + fix bridged case titles")
    print("=" * 60)
    init_db()
    engine = get_engine()
    with Session(engine) as session:
        upsert_pillar_cases(session)
        nr = rename_heatmap_prefixed_cases(session)
        ns = strip_governance_console_flags(session)
    print("=" * 60)
    print(f"Done. Renamed {nr} legacy title(s); reset governance UI keys on {ns} case(s).")
    print("=" * 60)


if __name__ == "__main__":
    main()

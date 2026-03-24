#!/usr/bin/env python3
"""
Print stage-readiness for every case in the DB (human decisions + derived context).

Run from repo root:
  python backend/scripts/audit_case_readiness.py
"""
import sys
from pathlib import Path

from sqlmodel import Session, select

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.persistence.database import get_engine, init_db
from backend.persistence.models import CaseState
from backend.services.case_service import get_case_service
from backend.services.chat_service import check_stage_readiness


def main():
    init_db()
    engine = get_engine()
    svc = get_case_service()
    print("case_id".ljust(16), "stage".ljust(8), "ready", "missing / notes")
    print("-" * 72)
    with Session(engine) as session:
        rows = session.exec(select(CaseState).order_by(CaseState.case_id)).all()
    for row in rows:
        case = svc.get_case(row.case_id)
        state = svc.get_case_state(row.case_id)
        if not case or not state:
            print(row.case_id.ljust(16), row.dtp_stage.ljust(8), "?", "no case state")
            continue
        r = check_stage_readiness(case, state)
        note = "; ".join(r["missing"]) if r["missing"] else "ok"
        print(
            row.case_id.ljust(16),
            row.dtp_stage.ljust(8),
            str(r["ready"]).ljust(5),
            note[:200],
        )


if __name__ == "__main__":
    main()

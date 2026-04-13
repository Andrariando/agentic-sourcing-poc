from typing import List, Optional, Dict, Tuple
import re
from datetime import datetime
from uuid import uuid4
from sqlmodel import select

from backend.services.case_service import get_case_service
from backend.persistence.database import get_db_session
from backend.persistence.models import CaseState
from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import Opportunity, AuditLog


class CaseBridgeService:
    """
    Bridge between Opportunity Prioritization and Case Management systems.
    This is the ONLY touchpoint between the two agentic systems.
    """

    def _bridged_case_title(self, opp: Opportunity, template: Optional[CaseState]) -> str:
        """
        Display name for a casework row cloned from heatmap (avoid implying prior approval).
        """
        supplier = (opp.supplier_name or opp.supplier_id or "New request").strip()
        if template and template.name:
            return f"{supplier} – {template.name}"
        cat = (opp.category or "General").strip()
        return f"{supplier} – {cat}"

    def _find_template_case(self, opportunity_category: str) -> Optional[CaseState]:
        """
        Try to reuse an existing rich demo case path, prioritized by category match.
        """
        session = get_db_session()
        try:
            category_like = (opportunity_category or "").replace(" ", "_").upper()
            # Align to pre-seeded demo journey cases where possible.
            category_map = [
                (["CLOUD", "INFRASTRUCTURE"], "CASE-002"),
                (["SAAS"], "CASE-003"),
                (["SOFTWARE", "IT"], "CASE-004"),
                (["SECURITY"], "CASE-006"),
                (["TELECOM"], "CASE-001"),
            ]
            for keywords, case_id in category_map:
                if any(k in category_like for k in keywords):
                    mapped = session.exec(
                        select(CaseState).where(CaseState.case_id == case_id)
                    ).first()
                    if mapped:
                        return mapped

            candidates = session.exec(
                select(CaseState).order_by(CaseState.updated_at.desc())
            ).all()
            for case in candidates:
                case_cat = (case.category_id or "").replace(" ", "_").upper()
                if case_cat == category_like:
                    return case
            return candidates[0] if candidates else None
        finally:
            session.close()

    def _create_case_from_template(self, opp: Opportunity) -> str:
        """
        Create a new case by cloning a template path (DTP data/history) and filling
        opportunity-specific identifiers.
        """
        template = self._find_template_case(opp.category)
        if not template:
            return get_case_service().create_case(
                category_id=opp.category,
                trigger_source="OpportunityHeatmap",
                contract_id=opp.contract_id,
                supplier_id=opp.supplier_id or opp.supplier_name,
                name=self._bridged_case_title(opp, None),
            )

        now = datetime.now().isoformat()
        new_case_id = f"CASE-{uuid4().hex[:8].upper()}"
        new_case = CaseState(
            case_id=new_case_id,
            category_id=template.category_id or opp.category,
            contract_id=opp.contract_id or template.contract_id,
            supplier_id=opp.supplier_id or opp.supplier_name or template.supplier_id,
            trigger_source="OpportunityHeatmap",
            dtp_stage="DTP-01",
            status="In Progress",
            name=self._bridged_case_title(opp, template),
            summary_text=template.summary_text or f"Sourced from priority heatmap – {opp.category}",
            key_findings=template.key_findings,
            recommended_action=template.recommended_action,
            latest_agent_output=template.latest_agent_output,
            latest_agent_name=template.latest_agent_name,
            latest_artifact_pack_id=None,
            artifact_index=None,
            next_actions_cache=None,
            human_decision=None,
            activity_log=None,
            chat_history=None,
            created_at=now,
            updated_at=now,
        )

        session = get_db_session()
        try:
            session.add(new_case)
            session.commit()
        finally:
            session.close()
        return new_case_id

    def _existing_case_for_opportunity(self, session, opp_id: int) -> Optional[str]:
        """If this opportunity was already bridged, return legacy case_id (idempotent approve)."""
        row = session.exec(
            select(AuditLog).where(
                AuditLog.event_type == "CASE_APPROVED",
                AuditLog.entity_id == str(opp_id),
            )
        ).first()
        if not row or not row.new_value:
            return None
        m = re.search(r"Linked to Case:\s*(\S+)", row.new_value)
        return m.group(1) if m else None

    def approve_opportunities(
        self, opportunity_ids: List[int], approver_id: str
    ) -> Tuple[int, Dict[int, str], Dict[int, bool]]:
        """
        Bridge approved opportunities to case management.
        Returns (approved_count_this_call, mapping opportunity_id -> case_id, already_linked flags).
        Skips opportunities already bridged (audit log) to avoid duplicates on double-submit.
        """
        session = heatmap_db.get_db_session()
        approved_count = 0
        cases: dict[int, str] = {}
        already_linked: dict[int, bool] = {}

        try:
            for opp_id in opportunity_ids:
                opp = session.get(Opportunity, opp_id)
                if not opp:
                    continue

                if opp.disposition in {"not_pursuing", "supplier_exit_planned"}:
                    continue

                existing = self._existing_case_for_opportunity(session, opp_id)
                if existing:
                    if opp.status != "Approved":
                        opp.status = "Approved"
                        session.add(opp)
                    cases[opp_id] = existing
                    already_linked[opp_id] = True
                    continue

                # Marked approved in UI or manually, but no audit row — do not create another case.
                if opp.status == "Approved":
                    continue

                try:
                    case_id = self._create_case_from_template(opp)

                    opp.status = "Approved"
                    session.add(opp)

                    audit = AuditLog(
                        event_type="CASE_APPROVED",
                        entity_id=str(opp.id),
                        new_value=f"Linked to Case: {case_id}",
                        user_id=approver_id,
                    )
                    session.add(audit)
                    approved_count += 1
                    cases[opp_id] = case_id
                    already_linked[opp_id] = False

                except Exception as e:
                    print(f"Failed to bridge opportunity {opp_id} to legacy system: {e}")

            session.commit()
        finally:
            session.close()

        return approved_count, cases, already_linked


def get_case_bridge_service() -> CaseBridgeService:
    return CaseBridgeService()


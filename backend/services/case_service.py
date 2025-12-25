"""
Case management service.
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from sqlmodel import select

from backend.persistence.database import get_db_session
from backend.persistence.models import CaseState
from backend.supervisor.state import StateManager, SupervisorState
from shared.schemas import CaseSummary, CaseDetail


class CaseService:
    """
    Service for case management.
    
    All case operations go through this service,
    which enforces governance via the Supervisor.
    """
    
    def list_cases(
        self,
        status: Optional[str] = None,
        dtp_stage: Optional[str] = None,
        category_id: Optional[str] = None,
        limit: int = 50
    ) -> List[CaseSummary]:
        """Get list of cases with optional filters."""
        session = get_db_session()
        
        query = select(CaseState)
        
        if status:
            query = query.where(CaseState.status == status)
        if dtp_stage:
            query = query.where(CaseState.dtp_stage == dtp_stage)
        if category_id:
            query = query.where(CaseState.category_id == category_id)
        
        query = query.order_by(CaseState.updated_at.desc()).limit(limit)
        
        results = session.exec(query).all()
        session.close()
        
        return [
            CaseSummary(
                case_id=c.case_id,
                name=c.name,
                category_id=c.category_id,
                contract_id=c.contract_id,
                supplier_id=c.supplier_id,
                dtp_stage=c.dtp_stage,
                trigger_source=c.trigger_source,
                status=c.status,
                created_date=c.created_at[:10],
                updated_date=c.updated_at[:10],
                summary_text=c.summary_text,
                key_findings=json.loads(c.key_findings) if c.key_findings else [],
                recommended_action=c.recommended_action
            )
            for c in results
        ]
    
    def get_case(self, case_id: str) -> Optional[CaseDetail]:
        """Get full case details."""
        session = get_db_session()
        
        case = session.exec(
            select(CaseState).where(CaseState.case_id == case_id)
        ).first()
        
        session.close()
        
        if not case:
            return None
        
        # Build summary
        summary = CaseSummary(
            case_id=case.case_id,
            name=case.name,
            category_id=case.category_id,
            contract_id=case.contract_id,
            supplier_id=case.supplier_id,
            dtp_stage=case.dtp_stage,
            trigger_source=case.trigger_source,
            status=case.status,
            created_date=case.created_at[:10],
            updated_date=case.updated_at[:10],
            summary_text=case.summary_text,
            key_findings=json.loads(case.key_findings) if case.key_findings else [],
            recommended_action=case.recommended_action
        )
        
        return CaseDetail(
            case_id=case.case_id,
            name=case.name,
            category_id=case.category_id,
            contract_id=case.contract_id,
            supplier_id=case.supplier_id,
            dtp_stage=case.dtp_stage,
            trigger_source=case.trigger_source,
            status=case.status,
            created_date=case.created_at[:10],
            updated_date=case.updated_at[:10],
            created_timestamp=case.created_at,
            updated_timestamp=case.updated_at,
            summary=summary,
            latest_agent_output=json.loads(case.latest_agent_output) if case.latest_agent_output else None,
            latest_agent_name=case.latest_agent_name,
            activity_log=json.loads(case.activity_log) if case.activity_log else [],
            human_decision=json.loads(case.human_decision) if case.human_decision else None
        )
    
    def create_case(
        self,
        category_id: str,
        trigger_source: str = "User",
        contract_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> str:
        """Create a new case."""
        case_id = f"CASE-{uuid4().hex[:8].upper()}"
        now = datetime.now().isoformat()
        
        if not name:
            name = f"New {category_id} Case"
        
        case = CaseState(
            case_id=case_id,
            category_id=category_id,
            contract_id=contract_id,
            supplier_id=supplier_id,
            trigger_source=trigger_source,
            dtp_stage="DTP-01",
            status="In Progress",
            name=name,
            summary_text=f"New case for category {category_id}",
            created_at=now,
            updated_at=now
        )
        
        session = get_db_session()
        session.add(case)
        session.commit()
        session.close()
        
        return case_id
    
    def update_case(
        self,
        case_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update case fields."""
        session = get_db_session()
        
        case = session.exec(
            select(CaseState).where(CaseState.case_id == case_id)
        ).first()
        
        if not case:
            session.close()
            return False
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(case, key):
                if key in ["key_findings", "activity_log", "latest_agent_output", "human_decision"]:
                    # JSON fields
                    setattr(case, key, json.dumps(value) if value else None)
                else:
                    setattr(case, key, value)
        
        case.updated_at = datetime.now().isoformat()
        
        session.add(case)
        session.commit()
        session.close()
        
        return True
    
    def get_case_state(self, case_id: str) -> Optional[SupervisorState]:
        """Get case state for Supervisor."""
        case = self.get_case(case_id)
        if not case:
            return None
        
        return SupervisorState(
            case_id=case.case_id,
            dtp_stage=case.dtp_stage,
            category_id=case.category_id,
            contract_id=case.contract_id,
            supplier_id=case.supplier_id,
            trigger_source=case.trigger_source,
            status=case.status,
            user_intent="",
            intent_classification="UNKNOWN",
            latest_agent_output=case.latest_agent_output,
            latest_agent_name=case.latest_agent_name,
            activity_log=case.activity_log or [],
            human_decision=case.human_decision,
            waiting_for_human=case.status == "Waiting for Human Decision",
            retrieval_context=None,
            documents_retrieved=[],
            allowed_actions=StateManager.ALLOWED_TRANSITIONS.get(case.dtp_stage, []),
            blocked_reason=None,
            error_state=None
        )
    
    def save_case_state(self, state: SupervisorState) -> bool:
        """Save Supervisor state back to case."""
        return self.update_case(
            state["case_id"],
            {
                "dtp_stage": state["dtp_stage"],
                "status": state["status"],
                "latest_agent_output": state.get("latest_agent_output"),
                "latest_agent_name": state.get("latest_agent_name"),
                "activity_log": state.get("activity_log"),
                "human_decision": state.get("human_decision")
            }
        )


# Singleton
_case_service = None


def get_case_service() -> CaseService:
    global _case_service
    if _case_service is None:
        _case_service = CaseService()
    return _case_service




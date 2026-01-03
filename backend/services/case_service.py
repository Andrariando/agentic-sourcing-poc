"""
Case management service.
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from sqlmodel import select

from backend.persistence.database import get_db_session
from backend.persistence.models import (
    CaseState, 
    Artifact as ArtifactModel,
    ArtifactPack as ArtifactPackModel
)
from backend.supervisor.state import StateManager, SupervisorState
from shared.schemas import (
    CaseSummary, CaseDetail, Artifact, ArtifactPack, 
    NextAction, RiskItem, GroundingReference
)


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
    
    # =========================================================================
    # ARTIFACT OPERATIONS
    # =========================================================================
    
    def save_artifact_pack(self, case_id: str, pack: ArtifactPack) -> bool:
        """
        Save an artifact pack and its artifacts to the database.
        
        Args:
            case_id: The case ID
            pack: The ArtifactPack to save
            
        Returns:
            True if successful
        """
        session = get_db_session()
        
        try:
            artifact_ids = []
            
            # Save individual artifacts
            for artifact in pack.artifacts:
                artifact_model = ArtifactModel(
                    artifact_id=artifact.artifact_id,
                    case_id=case_id,
                    type=artifact.type,
                    title=artifact.title,
                    content_json=json.dumps(artifact.content) if artifact.content else None,
                    content_text=artifact.content_text,
                    grounded_in_json=json.dumps([
                        {"ref_id": g.ref_id, "ref_type": g.ref_type, 
                         "source_name": g.source_name, "excerpt": g.excerpt}
                        for g in artifact.grounded_in
                    ]),
                    created_by_agent=artifact.created_by_agent,
                    created_by_task=artifact.created_by_task,
                    verification_status=artifact.verification_status,
                    created_at=artifact.created_at
                )
                session.add(artifact_model)
                artifact_ids.append(artifact.artifact_id)
            
            # Save the pack
            pack_model = ArtifactPackModel(
                pack_id=pack.pack_id,
                case_id=case_id,
                agent_name=pack.agent_name,
                tasks_executed=json.dumps(pack.tasks_executed),
                artifact_ids=json.dumps(artifact_ids),
                next_actions_json=json.dumps([
                    {"action_id": a.action_id, "label": a.label, "why": a.why,
                     "owner": a.owner, "depends_on": a.depends_on,
                     "recommended_by_agent": a.recommended_by_agent,
                     "recommended_by_task": a.recommended_by_task}
                    for a in pack.next_actions
                ]),
                risks_json=json.dumps([
                    {"severity": r.severity, "description": r.description, "mitigation": r.mitigation}
                    for r in pack.risks
                ]),
                notes_json=json.dumps(pack.notes),
                created_at=pack.created_at
            )
            session.add(pack_model)
            
            # Update case state with latest pack info
            case = session.exec(
                select(CaseState).where(CaseState.case_id == case_id)
            ).first()
            
            if case:
                case.latest_artifact_pack_id = pack.pack_id
                
                # Update artifact index
                artifact_index = json.loads(case.artifact_index) if case.artifact_index else {}
                for artifact in pack.artifacts:
                    if artifact.type not in artifact_index:
                        artifact_index[artifact.type] = []
                    artifact_index[artifact.type].append(artifact.artifact_id)
                case.artifact_index = json.dumps(artifact_index)
                
                # Cache next actions
                case.next_actions_cache = json.dumps([
                    {"action_id": a.action_id, "label": a.label, "why": a.why}
                    for a in pack.next_actions
                ])
                
                case.updated_at = datetime.now().isoformat()
                session.add(case)
            
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            print(f"Error saving artifact pack: {e}")
            return False
        finally:
            session.close()
    
    def list_artifacts(
        self, 
        case_id: str, 
        artifact_type: Optional[str] = None
    ) -> List[Artifact]:
        """
        List artifacts for a case, optionally filtered by type.
        """
        session = get_db_session()
        
        query = select(ArtifactModel).where(ArtifactModel.case_id == case_id)
        if artifact_type:
            query = query.where(ArtifactModel.type == artifact_type)
        
        query = query.order_by(ArtifactModel.created_at.desc())
        
        results = session.exec(query).all()
        session.close()
        
        return [self._model_to_artifact(r) for r in results]
    
    def get_artifact(self, case_id: str, artifact_id: str) -> Optional[Artifact]:
        """Get a specific artifact."""
        session = get_db_session()
        
        result = session.exec(
            select(ArtifactModel).where(
                ArtifactModel.case_id == case_id,
                ArtifactModel.artifact_id == artifact_id
            )
        ).first()
        
        session.close()
        
        return self._model_to_artifact(result) if result else None
    
    def get_latest_artifact_pack(self, case_id: str) -> Optional[ArtifactPack]:
        """Get the latest artifact pack for a case."""
        session = get_db_session()
        
        # Get case to find latest pack ID
        case = session.exec(
            select(CaseState).where(CaseState.case_id == case_id)
        ).first()
        
        if not case or not case.latest_artifact_pack_id:
            session.close()
            return None
        
        pack = session.exec(
            select(ArtifactPackModel).where(
                ArtifactPackModel.pack_id == case.latest_artifact_pack_id
            )
        ).first()
        
        session.close()
        
        return self._model_to_pack(pack, case_id) if pack else None
    
    def get_next_actions(self, case_id: str) -> List[NextAction]:
        """Get cached next actions for a case."""
        session = get_db_session()
        
        case = session.exec(
            select(CaseState).where(CaseState.case_id == case_id)
        ).first()
        
        session.close()
        
        if not case or not case.next_actions_cache:
            return []
        
        try:
            actions_data = json.loads(case.next_actions_cache)
            return [
                NextAction(
                    action_id=a.get("action_id", ""),
                    label=a.get("label", ""),
                    why=a.get("why", ""),
                    owner=a.get("owner", "user"),
                    depends_on=a.get("depends_on", []),
                    recommended_by_agent=a.get("recommended_by_agent", ""),
                    recommended_by_task=a.get("recommended_by_task", "")
                )
                for a in actions_data
            ]
        except json.JSONDecodeError:
            return []
    
    def _model_to_artifact(self, model: ArtifactModel) -> Artifact:
        """Convert database model to Artifact schema."""
        grounded_in = []
        if model.grounded_in_json:
            try:
                grounding_data = json.loads(model.grounded_in_json)
                grounded_in = [
                    GroundingReference(
                        ref_id=g.get("ref_id", ""),
                        ref_type=g.get("ref_type", ""),
                        source_name=g.get("source_name", ""),
                        excerpt=g.get("excerpt")
                    )
                    for g in grounding_data
                ]
            except json.JSONDecodeError:
                pass
        
        return Artifact(
            artifact_id=model.artifact_id,
            type=model.type,
            title=model.title,
            content=json.loads(model.content_json) if model.content_json else {},
            content_text=model.content_text,
            grounded_in=grounded_in,
            created_at=model.created_at,
            created_by_agent=model.created_by_agent,
            created_by_task=model.created_by_task,
            verification_status=model.verification_status
        )
    
    def _model_to_pack(self, model: ArtifactPackModel, case_id: str) -> ArtifactPack:
        """Convert database model to ArtifactPack schema."""
        # Load artifacts
        artifact_ids = json.loads(model.artifact_ids) if model.artifact_ids else []
        artifacts = []
        for aid in artifact_ids:
            artifact = self.get_artifact(case_id, aid)
            if artifact:
                artifacts.append(artifact)
        
        # Load next actions
        next_actions = []
        if model.next_actions_json:
            try:
                actions_data = json.loads(model.next_actions_json)
                next_actions = [
                    NextAction(**a) for a in actions_data
                ]
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Load risks
        risks = []
        if model.risks_json:
            try:
                risks_data = json.loads(model.risks_json)
                risks = [RiskItem(**r) for r in risks_data]
            except (json.JSONDecodeError, TypeError):
                pass
        
        return ArtifactPack(
            pack_id=model.pack_id,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks,
            notes=json.loads(model.notes_json) if model.notes_json else [],
            grounded_in=[],  # Aggregated from artifacts
            agent_name=model.agent_name,
            tasks_executed=json.loads(model.tasks_executed) if model.tasks_executed else [],
            created_at=model.created_at
        )


# Singleton
_case_service = None


def get_case_service() -> CaseService:
    global _case_service
    if _case_service is None:
        _case_service = CaseService()
    return _case_service





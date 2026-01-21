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
    NextAction, RiskItem, GroundingReference,
    ExecutionMetadata, TaskExecutionDetail
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
        
        # Get latest artifact pack ID if available
        latest_artifact_pack_id = case.latest_artifact_pack_id if hasattr(case, 'latest_artifact_pack_id') else None
        
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
            human_decision=json.loads(case.human_decision) if case.human_decision else None,
            chat_history=case.chat_history  # Pass through as-is (JSON string or None)
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
                    # JSON fields - handle Pydantic models
                    if value is not None:
                        # Convert Pydantic models to dict before serialization
                        if hasattr(value, "model_dump"):
                            value = value.model_dump()
                        elif hasattr(value, "dict"):
                            value = value.dict()
                        # Handle lists of Pydantic models
                        elif isinstance(value, list):
                            value = [
                                (item.model_dump() if hasattr(item, "model_dump") 
                                 else item.dict() if hasattr(item, "dict") 
                                 else item)
                                for item in value
                            ]
                    setattr(case, key, json.dumps(value) if value else None)
                else:
                    setattr(case, key, value)
        
        case.updated_at = datetime.now().isoformat()
        
        session.add(case)
        session.commit()
        session.close()
        
        return True
    
    def _rehydrate_agent_output(self, output_dict: dict, agent_name: str):
        """
        ISSUE #2 FIX: Convert dict back to proper Pydantic model for isinstance checks.
        
        When loading from DB, agent output is a dict (from JSON parsing).
        Supervisor routing uses isinstance() checks which fail for dicts.
        This rehydrates the dict back to the proper Pydantic model.
        """
        if not output_dict or not agent_name:
            return output_dict
        
        # Import inside method to avoid circular imports
        from utils.schemas import (
            StrategyRecommendation, SupplierShortlist, NegotiationPlan,
            RFxDraft, ContractExtraction, ImplementationPlan, ClarificationRequest
        )
        
        MODEL_MAP = {
            "Strategy": StrategyRecommendation,
            "SupplierEvaluation": SupplierShortlist,
            "NegotiationSupport": NegotiationPlan,
            "RFxDraft": RFxDraft,
            "ContractSupport": ContractExtraction,
            "Implementation": ImplementationPlan,
            "CaseClarifier": ClarificationRequest,
            # Support enum-style names too
            "SOURCING_SIGNAL": StrategyRecommendation,
            "SUPPLIER_SCORING": SupplierShortlist,
            "NEGOTIATION_SUPPORT": NegotiationPlan,
            "RFX_DRAFT": RFxDraft,
            "CONTRACT_SUPPORT": ContractExtraction,
            "IMPLEMENTATION": ImplementationPlan,
        }
        
        model_class = MODEL_MAP.get(agent_name)
        if model_class:
            try:
                return model_class(**output_dict)
            except Exception as e:
                # Log but don't fail - fallback to dict
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to rehydrate {agent_name} output: {e}"
                )
                return output_dict
        return output_dict
    
    def get_case_state(self, case_id: str) -> Optional[SupervisorState]:
        """Get case state for Supervisor."""
        case = self.get_case(case_id)
        if not case:
            return None
        
        # Get latest artifact pack ID if available
        latest_artifact_pack_id = case.latest_artifact_pack_id if hasattr(case, 'latest_artifact_pack_id') else None
        
        # ISSUE #2 FIX: Rehydrate agent output from dict to Pydantic model
        latest_agent_output = case.latest_agent_output
        latest_agent_name = case.latest_agent_name
        
        if isinstance(latest_agent_output, dict) and latest_agent_name:
            latest_agent_output = self._rehydrate_agent_output(
                latest_agent_output, latest_agent_name
            )
        
        state = SupervisorState(
            case_id=case.case_id,
            name=case.name,
            summary_text=case.summary_text,
            key_findings=json.loads(case.key_findings) if case.key_findings else [],
            dtp_stage=case.dtp_stage,
            category_id=case.category_id,
            contract_id=case.contract_id,
            supplier_id=case.supplier_id,
            trigger_source=case.trigger_source,
            status=case.status,
            user_intent="",
            intent_classification="UNKNOWN",
            latest_agent_output=latest_agent_output,  # Now Pydantic object, not dict
            latest_agent_name=latest_agent_name,
            activity_log=case.activity_log or [],
            human_decision=case.human_decision,
            waiting_for_human=case.status == "Waiting for Human Decision",
            retrieval_context=None,
            documents_retrieved=[],
            allowed_actions=StateManager.ALLOWED_TRANSITIONS.get(case.dtp_stage, []),
            blocked_reason=None,
            error_state=None
        )
        
        # Add latest_artifact_pack_id to state (as additional field, not in TypedDict)
        if latest_artifact_pack_id:
            state["latest_artifact_pack_id"] = latest_artifact_pack_id
        
        return state
    
    def save_case_state(self, state: SupervisorState) -> bool:
        """Save Supervisor state back to case."""
        updates = {
            "dtp_stage": state["dtp_stage"],
            "status": state["status"],
            "latest_agent_output": state.get("latest_agent_output"),
            "latest_agent_name": state.get("latest_agent_name"),
            "activity_log": state.get("activity_log"),
            "human_decision": state.get("human_decision")
        }
        # Include latest_artifact_pack_id if present in state
        if "latest_artifact_pack_id" in state:
            updates["latest_artifact_pack_id"] = state["latest_artifact_pack_id"]
        return self.update_case(state["case_id"], updates)
    
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
            
            # Serialize execution metadata if present
            execution_metadata_json = None
            if pack.execution_metadata:
                exec_meta = pack.execution_metadata
                execution_metadata_json = json.dumps({
                    "agent_name": exec_meta.agent_name,
                    "dtp_stage": exec_meta.dtp_stage,
                    "execution_timestamp": exec_meta.execution_timestamp,
                    "total_tokens_used": exec_meta.total_tokens_used,
                    "estimated_cost_usd": exec_meta.estimated_cost_usd,
                    "documents_retrieved": exec_meta.documents_retrieved,
                    "retrieval_sources": exec_meta.retrieval_sources,
                    "task_details": [
                        {
                            "task_name": t.task_name,
                            "execution_order": t.execution_order,
                            "status": t.status,
                            "started_at": t.started_at,
                            "completed_at": t.completed_at,
                            "tokens_used": t.tokens_used,
                            "output_summary": t.output_summary,
                            "grounding_sources": t.grounding_sources,
                            "error_message": t.error_message
                        }
                        for t in exec_meta.task_details
                    ],
                    "user_message": exec_meta.user_message,
                    "intent_classified": exec_meta.intent_classified,
                    "cache_hits": exec_meta.cache_hits,
                    "total_tasks": exec_meta.total_tasks,
                    "completed_tasks": exec_meta.completed_tasks,
                    "model_used": exec_meta.model_used
                })
            
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
                execution_metadata_json=execution_metadata_json,
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
    
    def get_artifact_pack(self, pack_id: str) -> Optional[ArtifactPack]:
        """
        Get artifact pack by ID.
        """
        session = get_db_session()
        
        pack = session.exec(
            select(ArtifactPackModel).where(ArtifactPackModel.pack_id == pack_id)
        ).first()
        
        session.close()
        
        if not pack:
            return None
        
        return self._model_to_pack(pack, pack.case_id)
    
    def get_all_artifact_packs(self, case_id: str) -> List[ArtifactPack]:
        """
        Get all artifact packs for a case, ordered by creation time.
        Includes full execution metadata for audit trail.
        """
        session = get_db_session()
        
        packs = session.exec(
            select(ArtifactPackModel)
            .where(ArtifactPackModel.case_id == case_id)
            .order_by(ArtifactPackModel.created_at)
        ).all()
        
        session.close()
        
        return [self._model_to_pack(p, case_id) for p in packs]
    
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
        
        # Load execution metadata (for audit trail)
        execution_metadata = None
        if model.execution_metadata_json:
            try:
                exec_data = json.loads(model.execution_metadata_json)
                # Reconstruct TaskExecutionDetail objects
                task_details = []
                for td in exec_data.get("task_details", []):
                    task_details.append(TaskExecutionDetail(
                        task_name=td.get("task_name", ""),
                        execution_order=td.get("execution_order", 0),
                        status=td.get("status", "completed"),
                        started_at=td.get("started_at"),
                        completed_at=td.get("completed_at"),
                        tokens_used=td.get("tokens_used", 0),
                        output_summary=td.get("output_summary", ""),
                        grounding_sources=td.get("grounding_sources", []),
                        error_message=td.get("error_message")
                    ))
                
                execution_metadata = ExecutionMetadata(
                    agent_name=exec_data.get("agent_name", ""),
                    dtp_stage=exec_data.get("dtp_stage", ""),
                    execution_timestamp=exec_data.get("execution_timestamp", ""),
                    total_tokens_used=exec_data.get("total_tokens_used", 0),
                    estimated_cost_usd=exec_data.get("estimated_cost_usd", 0.0),
                    documents_retrieved=exec_data.get("documents_retrieved", []),
                    retrieval_sources=exec_data.get("retrieval_sources", []),
                    task_details=task_details,
                    user_message=exec_data.get("user_message", ""),
                    intent_classified=exec_data.get("intent_classified", ""),
                    cache_hits=exec_data.get("cache_hits", 0),
                    total_tasks=exec_data.get("total_tasks", 0),
                    completed_tasks=exec_data.get("completed_tasks", 0),
                    model_used=exec_data.get("model_used", "")
                )
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"Warning: Could not parse execution metadata: {e}")
        
        return ArtifactPack(
            pack_id=model.pack_id,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks,
            notes=json.loads(model.notes_json) if model.notes_json else [],
            grounded_in=[],  # Aggregated from artifacts
            agent_name=model.agent_name,
            tasks_executed=json.loads(model.tasks_executed) if model.tasks_executed else [],
            created_at=model.created_at,
            execution_metadata=execution_metadata
        )


# Singleton
_case_service = None


def get_case_service() -> CaseService:
    global _case_service
    if _case_service is None:
        _case_service = CaseService()
    return _case_service





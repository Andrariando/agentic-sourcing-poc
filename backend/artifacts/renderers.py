"""
Artifact renderers - Format artifacts for UI display.
"""
from typing import Dict, Any, List
from shared.schemas import Artifact, ArtifactPack, NextAction, RiskItem
from shared.constants import ArtifactType


class ArtifactRenderer:
    """
    Render artifacts for different UI contexts.
    """
    
    @staticmethod
    def render_artifact_card(artifact: Artifact) -> Dict[str, Any]:
        """Render artifact as a card for the workbench."""
        return {
            "id": artifact.artifact_id,
            "type": artifact.type,
            "title": artifact.title,
            "preview": artifact.content_text[:200] if artifact.content_text else "",
            "created_at": artifact.created_at,
            "agent": artifact.created_by_agent,
            "task": artifact.created_by_task,
            "verification": artifact.verification_status,
            "grounding_count": len(artifact.grounded_in),
            "has_content": bool(artifact.content or artifact.content_text),
        }
    
    @staticmethod
    def render_artifact_detail(artifact: Artifact) -> Dict[str, Any]:
        """Render full artifact detail view."""
        return {
            "id": artifact.artifact_id,
            "type": artifact.type,
            "title": artifact.title,
            "content": artifact.content,
            "content_text": artifact.content_text,
            "created_at": artifact.created_at,
            "created_by": {
                "agent": artifact.created_by_agent,
                "task": artifact.created_by_task,
            },
            "verification_status": artifact.verification_status,
            "grounded_in": [
                {
                    "ref_id": g.ref_id,
                    "type": g.ref_type,
                    "source": g.source_name,
                    "excerpt": g.excerpt,
                }
                for g in artifact.grounded_in
            ],
        }
    
    @staticmethod
    def render_next_actions(actions: List[NextAction]) -> List[Dict[str, Any]]:
        """Render next actions for the action panel."""
        return [
            {
                "id": a.action_id,
                "label": a.label,
                "why": a.why,
                "owner": a.owner,
                "depends_on": a.depends_on,
                "recommended_by": a.recommended_by_agent,
            }
            for a in actions
        ]
    
    @staticmethod
    def render_risks(risks: List[RiskItem]) -> List[Dict[str, Any]]:
        """Render risks for the risk panel."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_risks = sorted(risks, key=lambda r: severity_order.get(r.severity, 4))
        
        return [
            {
                "severity": r.severity,
                "description": r.description,
                "mitigation": r.mitigation,
                "badge_color": {
                    "critical": "#A31F34",
                    "high": "#D9534F",
                    "medium": "#F0AD4E",
                    "low": "#5CB85C",
                }.get(r.severity, "#6C757D"),
            }
            for r in sorted_risks
        ]
    
    @staticmethod
    def render_pack_summary(pack: ArtifactPack) -> Dict[str, Any]:
        """Render artifact pack summary for overview."""
        # Group artifacts by type
        by_type = {}
        for a in pack.artifacts:
            if a.type not in by_type:
                by_type[a.type] = []
            by_type[a.type].append(a.title)
        
        return {
            "pack_id": pack.pack_id,
            "agent": pack.agent_name,
            "artifact_count": len(pack.artifacts),
            "action_count": len(pack.next_actions),
            "risk_count": len(pack.risks),
            "artifacts_by_type": by_type,
            "created_at": pack.created_at,
            "tasks_executed": pack.tasks_executed,
        }
    
    @staticmethod
    def get_artifact_tab(artifact_type: str) -> str:
        """Map artifact type to UI tab."""
        tab_mapping = {
            # Signal artifacts
            ArtifactType.SIGNAL_REPORT.value: "Signals",
            ArtifactType.SIGNAL_SUMMARY.value: "Signals",
            ArtifactType.AUTOPREP_BUNDLE.value: "Signals",
            
            # Scoring artifacts
            ArtifactType.EVALUATION_SCORECARD.value: "Supplier Scoring",
            ArtifactType.SUPPLIER_SCORECARD.value: "Supplier Scoring",
            ArtifactType.SUPPLIER_SHORTLIST.value: "Supplier Scoring",
            
            # RFx artifacts
            ArtifactType.RFX_PATH.value: "RFx Drafts",
            ArtifactType.RFX_DRAFT_PACK.value: "RFx Drafts",
            ArtifactType.RFX_QA_TRACKER.value: "RFx Drafts",
            
            # Negotiation artifacts
            ArtifactType.NEGOTIATION_PLAN.value: "Negotiation",
            ArtifactType.LEVERAGE_SUMMARY.value: "Negotiation",
            ArtifactType.TARGET_TERMS.value: "Negotiation",
            
            # Contract artifacts
            ArtifactType.KEY_TERMS_EXTRACT.value: "Contract Terms",
            ArtifactType.TERM_VALIDATION_REPORT.value: "Contract Terms",
            ArtifactType.CONTRACT_HANDOFF_PACKET.value: "Contract Terms",
            
            # Implementation artifacts
            ArtifactType.IMPLEMENTATION_CHECKLIST.value: "Implementation",
            ArtifactType.EARLY_INDICATORS_REPORT.value: "Implementation",
            ArtifactType.VALUE_CAPTURE_TEMPLATE.value: "Implementation",
            
            # Status artifacts
            ArtifactType.STATUS_SUMMARY.value: "History",
            ArtifactType.NEXT_BEST_ACTIONS.value: "History",
        }
        
        return tab_mapping.get(artifact_type, "History")


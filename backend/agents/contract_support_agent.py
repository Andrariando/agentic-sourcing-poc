"""
Contract Support Agent - Extracts terms and prepares handoff.

Purpose: Extract key award terms and prepare structured inputs for
contracting and implementation.
"""
from typing import Dict, Any, List

from backend.agents.base import BaseAgent
from backend.tasks.registry import get_task_registry
from backend.tasks.planners import AgentPlaybook
from backend.artifacts.builders import (
    ArtifactBuilder, build_artifact_pack, build_next_action, build_risk_item
)
from shared.constants import AgentName, ArtifactType, UserGoal
from shared.schemas import ArtifactPack


class ContractSupportAgent(BaseAgent):
    """
    Contract Support Agent - Term extraction and handoff preparation.
    
    Sub-tasks:
    - extract_key_terms
    - term_validation
    - term_alignment_summary
    - implementation_handoff_packet
    """
    
    def __init__(self, tier: int = 1):
        super().__init__(name="ContractSupport", tier=tier)
        self.registry = get_task_registry()
        self.playbook = AgentPlaybook()
    
    def execute(
        self, 
        case_context: Dict[str, Any], 
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute contract support workflow.
        
        Returns ArtifactPack with key terms, validation report, and handoff packet.
        """
        # Initialize execution metadata tracking
        exec_metadata = self.create_execution_metadata(
            dtp_stage=case_context.get("dtp_stage", "DTP-05"),
            user_message=user_intent,
            intent_classified="CREATE"
        )
        
        # Get tasks to execute
        tasks = self.playbook.get_tasks_for_agent(
            AgentName.CONTRACT_SUPPORT,
            UserGoal.CREATE,
            None,
            case_context.get("dtp_stage", "DTP-05")
        )
        
        # Execute tasks
        context = dict(case_context)
        all_grounded_in = []
        total_tokens = 0
        tasks_executed = []
        
        for task_name in tasks:
            task = self.registry.get_task(task_name)
            if task:
                result = task.execute(context)
                context.update(result.data)
                all_grounded_in.extend(result.grounded_in)
                total_tokens += result.tokens_used
                tasks_executed.append(task_name)
                
                # Track task execution for audit trail
                grounding_ids = [g.ref_id for g in result.grounded_in] if result.grounded_in else []
                self.track_task_execution(
                    exec_metadata,
                    task_name=task_name,
                    status="completed",
                    tokens_used=result.tokens_used,
                    output_summary=str(result.data)[:200] if result.data else "",
                    grounding_sources=grounding_ids
                )
                if grounding_ids:
                    self.track_document_retrieval(exec_metadata, grounding_ids)
        
        # Build artifacts
        artifacts = []
        
        # Key Terms Extract artifact
        key_terms = context.get("key_terms", {})
        
        key_terms_artifact = (
            ArtifactBuilder(ArtifactType.KEY_TERMS_EXTRACT, AgentName.CONTRACT_SUPPORT)
            .with_title("Key Contract Terms")
            .with_content(key_terms)
            .with_content_text(
                f"Contract value: ${key_terms.get('pricing', {}).get('annual_value', 0):,}. "
                f"Term: {key_terms.get('term', {}).get('duration_months', 0)} months. "
                f"SLA: {key_terms.get('sla', {}).get('response_time', 'N/A')} response."
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(key_terms_artifact)
        
        # Term Validation Report artifact
        validation_results = context.get("validation_results", [])
        issues = context.get("issues", [])
        is_compliant = context.get("is_compliant", True)
        
        validation_report = (
            ArtifactBuilder(ArtifactType.TERM_VALIDATION_REPORT, AgentName.CONTRACT_SUPPORT)
            .with_title("Term Validation Report")
            .with_content({
                "validation_results": validation_results,
                "issues": issues,
                "is_compliant": is_compliant,
            })
            .with_content_text(
                f"Validation {'passed' if is_compliant else 'found issues'}. "
                f"{len(issues)} issues identified." if issues else "All terms compliant."
            )
            .with_grounding(all_grounded_in[:3])
            .build()
        )
        artifacts.append(validation_report)
        
        # Contract Handoff Packet artifact
        handoff_packet = context.get("handoff_packet", {})
        alignment_summary = context.get("alignment_summary", "")
        
        handoff_artifact = (
            ArtifactBuilder(ArtifactType.CONTRACT_HANDOFF_PACKET, AgentName.CONTRACT_SUPPORT)
            .with_title("Implementation Handoff Packet")
            .with_content(handoff_packet)
            .with_content_text(alignment_summary or "Handoff packet ready for implementation team.")
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(handoff_artifact)
        
        # Build next actions
        next_actions = []
        
        if not is_compliant:
            for issue in issues[:2]:
                next_actions.append(build_next_action(
                    label=f"Resolve: {issue.get('field', 'term issue')}",
                    why=issue.get("issue", "Compliance issue needs resolution"),
                    agent_name=AgentName.CONTRACT_SUPPORT
                ))
        else:
            next_actions.append(build_next_action(
                label="Approve contract terms",
                why="All terms validated and compliant",
                agent_name=AgentName.CONTRACT_SUPPORT
            ))
        
        next_actions.append(build_next_action(
            label="Schedule contract signing",
            why="Coordinate with legal and supplier",
            agent_name=AgentName.CONTRACT_SUPPORT
        ))
        
        next_actions.append(build_next_action(
            label="Initiate implementation planning",
            why="Prepare for rollout after contract execution",
            agent_name=AgentName.CONTRACT_SUPPORT
        ))
        
        # Build risks
        risks = []
        for issue in issues:
            risks.append(build_risk_item(
                severity=issue.get("severity", "medium"),
                description=issue.get("issue", "Term validation issue"),
                mitigation="Negotiate correction before contract execution"
            ))
        
        # Finalize execution metadata
        final_exec_metadata = self.finalize_execution_metadata(exec_metadata)
        
        # Build artifact pack with execution metadata
        pack = build_artifact_pack(
            agent_name=AgentName.CONTRACT_SUPPORT,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks,
            tasks_executed=tasks_executed,
            execution_metadata=final_exec_metadata
        )
        
        return {
            "success": True,
            "agent_name": AgentName.CONTRACT_SUPPORT.value,
            "artifact_pack": pack,
            "tokens_used": total_tokens,
            "output": {
                "key_terms": key_terms,
                "is_compliant": is_compliant,
                "handoff_packet": handoff_packet,
            }
        }



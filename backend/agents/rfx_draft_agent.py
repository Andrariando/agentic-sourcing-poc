"""
RFx Draft Agent - Assembles RFx documents.

Purpose: Assemble RFx drafts using templates, past examples, and structured
generation based on sourcing manager inputs.
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


class RfxDraftAgent(BaseAgent):
    """
    RFx Draft Agent - Document assembly and generation.
    
    Sub-tasks:
    - determine_rfx_path
    - retrieve_templates_and_past_examples
    - assemble_rfx_sections
    - completeness_checks
    - draft_questions_and_requirements
    - create_qa_tracker
    """
    
    def __init__(self, tier: int = 1):
        super().__init__(name="RfxDraft", tier=tier)
        self.registry = get_task_registry()
        self.playbook = AgentPlaybook()
    
    def execute(
        self, 
        case_context: Dict[str, Any], 
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute RFx drafting workflow.
        
        Returns ArtifactPack with RFx draft, path determination, and Q&A tracker.
        """
        # Get tasks to execute
        tasks = self.playbook.get_tasks_for_agent(
            AgentName.RFX_DRAFT,
            UserGoal.CREATE,
            None,
            case_context.get("dtp_stage", "DTP-03")
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
        
        # Build artifacts
        artifacts = []
        
        # RFx Path artifact
        rfx_type = context.get("rfx_type", "RFP")
        path_rationale = context.get("rationale", [])
        
        rfx_path = (
            ArtifactBuilder(ArtifactType.RFX_PATH, AgentName.RFX_DRAFT)
            .with_title(f"RFx Path: {rfx_type}")
            .with_content({
                "rfx_type": rfx_type,
                "rationale": path_rationale,
                "missing_info": context.get("missing_info", []),
            })
            .with_content_text(
                f"Recommended path: {rfx_type}. " +
                (path_rationale[0] if path_rationale else "")
            )
            .with_grounding(all_grounded_in[:2])
            .build()
        )
        artifacts.append(rfx_path)
        
        # RFx Draft Pack artifact
        sections = context.get("sections", [])
        completeness_score = context.get("completeness_score", 0)
        
        rfx_draft = (
            ArtifactBuilder(ArtifactType.RFX_DRAFT_PACK, AgentName.RFX_DRAFT)
            .with_title(f"{rfx_type} Draft Document")
            .with_content({
                "rfx_type": rfx_type,
                "sections": sections,
                "completeness_score": completeness_score,
                "is_complete": context.get("is_complete", False),
                "missing_sections": context.get("missing_sections", []),
                "incomplete_sections": context.get("incomplete_sections", []),
            })
            .with_content_text(
                f"{rfx_type} draft with {len(sections)} sections. "
                f"Completeness: {completeness_score}%"
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(rfx_draft)
        
        # Q&A Tracker artifact
        qa_tracker = context.get("qa_tracker", [])
        draft_questions = context.get("draft_questions", [])
        
        qa_artifact = (
            ArtifactBuilder(ArtifactType.RFX_QA_TRACKER, AgentName.RFX_DRAFT)
            .with_title("RFx Q&A Tracker")
            .with_content({
                "tracker": qa_tracker,
                "questions": draft_questions,
                "total_questions": len(qa_tracker),
            })
            .with_content_text(
                f"Q&A tracker with {len(qa_tracker)} questions ready for supplier responses."
            )
            .build()
        )
        artifacts.append(qa_artifact)
        
        # Build next actions
        next_actions = []
        
        if not context.get("is_complete", False):
            missing = context.get("missing_sections", [])
            next_actions.append(build_next_action(
                label=f"Complete {missing[0]}" if missing else "Complete draft sections",
                why="Required sections need content before distribution",
                agent_name=AgentName.RFX_DRAFT
            ))
        else:
            next_actions.append(build_next_action(
                label="Review and approve draft",
                why="Draft is complete and ready for review",
                agent_name=AgentName.RFX_DRAFT
            ))
        
        next_actions.append(build_next_action(
            label="Add evaluation criteria",
            why="Define scoring methodology for responses",
            agent_name=AgentName.RFX_DRAFT
        ))
        
        next_actions.append(build_next_action(
            label="Set submission deadline",
            why="Establish timeline for supplier responses",
            agent_name=AgentName.RFX_DRAFT
        ))
        
        # Build risks
        risks = []
        if completeness_score < 70:
            risks.append(build_risk_item(
                severity="medium",
                description=f"RFx only {completeness_score}% complete",
                mitigation="Complete remaining sections before distribution"
            ))
        
        # Build artifact pack
        pack = build_artifact_pack(
            agent_name=AgentName.RFX_DRAFT,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks,
            tasks_executed=tasks_executed
        )
        
        return {
            "success": True,
            "agent_name": AgentName.RFX_DRAFT.value,
            "artifact_pack": pack,
            "tokens_used": total_tokens,
            "output": {
                "rfx_type": rfx_type,
                "sections": sections,
                "completeness_score": completeness_score,
            }
        }



"""
Implementation Agent - Produces rollout and value capture artifacts.

Purpose: Produce rollout steps and early post-award indicators
(savings + service impacts).
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


class ImplementationAgent(BaseAgent):
    """
    Implementation Agent - Rollout and value capture planning.
    
    Sub-tasks:
    - build_rollout_checklist
    - compute_expected_savings
    - define_early_indicators
    - reporting_templates
    """
    
    def __init__(self, tier: int = 1):
        super().__init__(name="Implementation", tier=tier)
        self.registry = get_task_registry()
        self.playbook = AgentPlaybook()
    
    def execute(
        self, 
        case_context: Dict[str, Any], 
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute implementation planning workflow.
        
        Returns ArtifactPack with checklist, indicators, and value capture templates.
        """
        # Get tasks to execute
        tasks = self.playbook.get_tasks_for_agent(
            AgentName.IMPLEMENTATION,
            UserGoal.CREATE,
            None,
            case_context.get("dtp_stage", "DTP-06")
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
        
        # Implementation Checklist artifact
        checklist = context.get("checklist", [])
        total_items = context.get("total_items", 0)
        
        checklist_artifact = (
            ArtifactBuilder(ArtifactType.IMPLEMENTATION_CHECKLIST, AgentName.IMPLEMENTATION)
            .with_title("Implementation Checklist")
            .with_content({
                "checklist": checklist,
                "total_items": total_items,
                "estimated_duration_days": context.get("estimated_duration_days", 90),
            })
            .with_content_text(
                f"Rollout checklist with {total_items} items across {len(checklist)} phases. "
                f"Estimated duration: {context.get('estimated_duration_days', 90)} days."
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(checklist_artifact)
        
        # Early Indicators Report artifact
        early_indicators = context.get("early_indicators", [])
        risk_triggers = context.get("risk_triggers", [])
        
        indicators_artifact = (
            ArtifactBuilder(ArtifactType.EARLY_INDICATORS_REPORT, AgentName.IMPLEMENTATION)
            .with_title("Early Success Indicators")
            .with_content({
                "indicators": early_indicators,
                "risk_triggers": risk_triggers,
            })
            .with_content_text(
                f"{len(early_indicators)} KPIs defined for early monitoring. "
                f"{len(risk_triggers)} risk triggers configured."
            )
            .build()
        )
        artifacts.append(indicators_artifact)
        
        # Value Capture Template artifact
        savings = context.get("savings_breakdown", {})
        templates = context.get("reporting_templates", {})
        
        value_artifact = (
            ArtifactBuilder(ArtifactType.VALUE_CAPTURE_TEMPLATE, AgentName.IMPLEMENTATION)
            .with_title("Value Capture Template")
            .with_content({
                "annual_savings": context.get("annual_savings", 0),
                "total_savings": context.get("total_savings", 0),
                "savings_percentage": context.get("savings_percentage", 0),
                "savings_breakdown": savings,
                "reporting_templates": templates,
            })
            .with_content_text(
                f"Projected annual savings: ${context.get('annual_savings', 0):,.0f} "
                f"({context.get('savings_percentage', 0):.1f}%). "
                f"Total over term: ${context.get('total_savings', 0):,.0f}"
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(value_artifact)
        
        # Build next actions
        next_actions = []
        
        if checklist:
            first_phase = checklist[0] if checklist else {}
            first_item = first_phase.get("items", [{}])[0] if first_phase.get("items") else {}
            next_actions.append(build_next_action(
                label=first_item.get("task", "Begin implementation"),
                why=f"First step in {first_phase.get('phase', 'Preparation')} phase",
                agent_name=AgentName.IMPLEMENTATION,
                owner=first_item.get("owner", "Project Manager")
            ))
        
        next_actions.append(build_next_action(
            label="Schedule kick-off meeting",
            why="Align stakeholders and confirm timeline",
            agent_name=AgentName.IMPLEMENTATION
        ))
        
        next_actions.append(build_next_action(
            label="Set up dashboards",
            why="Enable KPI tracking from day one",
            agent_name=AgentName.IMPLEMENTATION
        ))
        
        # Build risks from triggers
        risks = []
        for trigger in risk_triggers[:3]:
            risks.append(build_risk_item(
                severity="medium",
                description=f"{trigger.get('indicator', 'KPI')}: {trigger.get('threshold', '')}",
                mitigation=trigger.get("action", "Monitor and escalate")
            ))
        
        # Build artifact pack
        pack = build_artifact_pack(
            agent_name=AgentName.IMPLEMENTATION,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks,
            tasks_executed=tasks_executed
        )
        
        return {
            "success": True,
            "agent_name": AgentName.IMPLEMENTATION.value,
            "artifact_pack": pack,
            "tokens_used": total_tokens,
            "output": {
                "checklist": checklist,
                "annual_savings": context.get("annual_savings", 0),
                "total_savings": context.get("total_savings", 0),
                "early_indicators": early_indicators,
            }
        }


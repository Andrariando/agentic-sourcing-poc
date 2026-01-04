"""
Negotiation Support Agent - Provides negotiation insights.

Purpose: Highlight bid differences, identify negotiation levers, provide
structured insights WITHOUT making award decisions.
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


class NegotiationSupportAgent(BaseAgent):
    """
    Negotiation Support Agent - Strategic negotiation insights.
    
    IMPORTANT: This agent provides INSIGHTS only, NOT award decisions.
    
    Sub-tasks:
    - compare_bids
    - leverage_point_extraction
    - benchmark_retrieval
    - price_anomaly_detection
    - propose_targets_and_fallbacks
    - negotiation_playbook
    """
    
    def __init__(self, tier: int = 1):
        super().__init__(name="NegotiationSupport", tier=tier)
        self.registry = get_task_registry()
        self.playbook = AgentPlaybook()
    
    def execute(
        self, 
        case_context: Dict[str, Any], 
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute negotiation support workflow.
        
        Returns ArtifactPack with negotiation plan, leverage points, and targets.
        """
        # Get tasks to execute
        tasks = self.playbook.get_tasks_for_agent(
            AgentName.NEGOTIATION_SUPPORT,
            UserGoal.CREATE,
            None,
            case_context.get("dtp_stage", "DTP-04")
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
        
        # Negotiation Plan artifact
        targets = context.get("targets", {})
        fallbacks = context.get("fallbacks", {})
        playbook = context.get("playbook", {})
        
        negotiation_plan = (
            ArtifactBuilder(ArtifactType.NEGOTIATION_PLAN, AgentName.NEGOTIATION_SUPPORT)
            .with_title("Negotiation Plan")
            .with_content({
                "targets": targets,
                "fallbacks": fallbacks,
                "playbook": playbook,
            })
            .with_content_text(
                f"Target price: ${targets.get('price_target', 0):,.0f}. " +
                playbook.get("summary", "")[:200]
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(negotiation_plan)
        
        # Leverage Summary artifact
        leverage_points = context.get("leverage_points", [])
        
        leverage_summary = (
            ArtifactBuilder(ArtifactType.LEVERAGE_SUMMARY, AgentName.NEGOTIATION_SUPPORT)
            .with_title("Leverage Points")
            .with_content({
                "leverage_points": leverage_points,
            })
            .with_content_text(
                f"{len(leverage_points)} leverage points identified. " +
                (f"Strongest: {leverage_points[0].get('description', '')}" if leverage_points else "")
            )
            .build()
        )
        artifacts.append(leverage_summary)
        
        # Target Terms artifact
        comparison = context.get("comparison", {})
        
        target_terms = (
            ArtifactBuilder(ArtifactType.TARGET_TERMS, AgentName.NEGOTIATION_SUPPORT)
            .with_title("Target Terms & Fallbacks")
            .with_content({
                "targets": targets,
                "fallbacks": fallbacks,
                "bid_comparison": comparison,
                "price_spread_pct": comparison.get("price_spread_pct", 0),
            })
            .with_content_text(
                f"Price target: ${targets.get('price_target', 0):,.0f}. "
                f"Fallback: ${fallbacks.get('price_fallback', 0):,.0f}. "
                f"Walk-away: ${fallbacks.get('walkaway_price', 0):,.0f}"
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(target_terms)
        
        # Build next actions
        next_actions = []
        
        next_actions.append(build_next_action(
            label="Schedule negotiation",
            why="Plan in place - ready to engage supplier",
            agent_name=AgentName.NEGOTIATION_SUPPORT
        ))
        
        if leverage_points:
            next_actions.append(build_next_action(
                label="Validate benchmarks",
                why="Confirm market rate data before negotiation",
                agent_name=AgentName.NEGOTIATION_SUPPORT
            ))
        
        next_actions.append(build_next_action(
            label="Prepare alternatives",
            why="Have backup suppliers ready to strengthen position",
            agent_name=AgentName.NEGOTIATION_SUPPORT
        ))
        
        # Build risks
        risks = []
        
        anomalies = context.get("price_anomalies", [])
        for anomaly in anomalies:
            risks.append(build_risk_item(
                severity="medium",
                description=f"{anomaly.get('supplier', '')}: {anomaly.get('concern', '')}",
                mitigation="Verify scope alignment before proceeding"
            ))
        
        if comparison.get("price_spread_pct", 0) > 30:
            risks.append(build_risk_item(
                severity="high",
                description=f"Large price spread ({comparison.get('price_spread_pct', 0):.0f}%) may indicate scope differences",
                mitigation="Ensure all bidders understood requirements consistently"
            ))
        
        # Build artifact pack
        pack = build_artifact_pack(
            agent_name=AgentName.NEGOTIATION_SUPPORT,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks,
            notes=["This analysis provides insights only - award decision requires human approval."],
            tasks_executed=tasks_executed
        )
        
        return {
            "success": True,
            "agent_name": AgentName.NEGOTIATION_SUPPORT.value,
            "artifact_pack": pack,
            "tokens_used": total_tokens,
            "output": {
                "negotiation_objectives": targets.get("additional_asks", []),
                "target_terms": targets,
                "leverage_points": leverage_points,
            }
        }



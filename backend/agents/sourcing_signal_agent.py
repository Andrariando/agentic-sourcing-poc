"""
Sourcing Signal Agent - Monitors and detects sourcing opportunities.

Purpose: Monitor contract metadata, spend patterns, supplier performance,
and approved external signals to proactively identify sourcing cases.
"""
from typing import Dict, Any, List

from backend.agents.base import BaseAgent
from backend.tasks.registry import get_task_registry
from backend.tasks.planners import AgentPlaybook
from backend.artifacts.builders import (
    ArtifactBuilder, build_artifact_pack, build_next_action, build_risk_item
)
from shared.constants import AgentName, ArtifactType, UserGoal
from shared.schemas import ArtifactPack, NextAction


class SourcingSignalAgent(BaseAgent):
    """
    Sourcing Signal Agent - Proactive opportunity detection.
    
    Sub-tasks:
    - detect_contract_expiry_signals
    - detect_performance_degradation_signals
    - detect_spend_anomalies
    - apply_relevance_filters
    - semantic_grounded_summary
    - produce_autoprep_recommendations
    """
    
    def __init__(self, tier: int = 1):
        super().__init__(name="SourcingSignal", tier=tier)
        self.registry = get_task_registry()
        self.playbook = AgentPlaybook()
    
    def execute(
        self, 
        case_context: Dict[str, Any], 
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute signal detection workflow.
        
        Returns ArtifactPack with signals, summary, and recommendations.
        """
        # Initialize execution metadata tracking
        exec_metadata = self.create_execution_metadata(
            dtp_stage=case_context.get("dtp_stage", "DTP-01"),
            user_message=user_intent,
            intent_classified="TRACK"
        )
        
        # Get tasks to execute
        tasks = self.playbook.get_tasks_for_agent(
            AgentName.SOURCING_SIGNAL,
            UserGoal.TRACK,
            None,
            case_context.get("dtp_stage", "DTP-01")
        )
        
        # Execute tasks and accumulate results
        context = dict(case_context)
        all_grounded_in = []
        total_tokens = 0
        tasks_executed = []
        
        for task_name in tasks:
            task = self.registry.get_task(task_name)
            if task:
                result = task.execute(context)
                # Merge result data into context for next task
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
                
                # Track document retrieval
                if grounding_ids:
                    self.track_document_retrieval(exec_metadata, grounding_ids)
        
        # Build artifacts
        artifacts = []
        
        # Signal Report artifact
        signals = context.get("filtered_signals", [])
        urgency_score = context.get("urgency_score", 5)
        
        signal_report = (
            ArtifactBuilder(ArtifactType.SIGNAL_REPORT, AgentName.SOURCING_SIGNAL)
            .with_title("Sourcing Signal Report")
            .with_content({
                "signals": signals,
                "urgency_score": urgency_score,
                "total_signals": len(signals),
                "high_severity_count": len([s for s in signals if s.get("severity") in ["high", "critical"]]),
            })
            .with_content_text(context.get("summary", "Signal scan complete."))
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(signal_report)
        
        # Autoprep Bundle artifact
        recommendations = context.get("recommendations", [])
        required_inputs = context.get("required_inputs", [])
        
        if recommendations:
            autoprep = (
                ArtifactBuilder(ArtifactType.AUTOPREP_BUNDLE, AgentName.SOURCING_SIGNAL)
                .with_title("Autoprep Recommendations")
                .with_content({
                    "recommendations": recommendations,
                    "required_inputs": required_inputs,
                })
                .with_content_text(
                    f"Identified {len(recommendations)} recommended actions. "
                    f"Required inputs: {', '.join(required_inputs) if required_inputs else 'None'}"
                )
                .build()
            )
            artifacts.append(autoprep)
        
        # Build next actions
        next_actions = []
        for rec in recommendations[:3]:
            next_actions.append(build_next_action(
                label=rec.get("action", "Review signal"),
                why=rec.get("reason", ""),
                agent_name=AgentName.SOURCING_SIGNAL,
                task_name="produce_autoprep_recommendations"
            ))
        
        # Add default actions based on signals
        if urgency_score >= 7:
            next_actions.append(build_next_action(
                label="Score suppliers",
                why="High urgency signals detected - evaluate alternatives",
                agent_name=AgentName.SOURCING_SIGNAL
            ))
        
        # Build risks
        risks = []
        expiry_signals = [s for s in signals if s.get("signal_type") == "contract_expiry"]
        if expiry_signals:
            days = expiry_signals[0].get("days_until_expiry", 0)
            if days < 30:
                risks.append(build_risk_item(
                    severity="high",
                    description=f"Contract expires in {days} days",
                    mitigation="Initiate renewal or sourcing process immediately"
                ))
        
        # Finalize execution metadata
        final_exec_metadata = self.finalize_execution_metadata(exec_metadata)
        
        # Build artifact pack with execution metadata
        pack = build_artifact_pack(
            agent_name=AgentName.SOURCING_SIGNAL,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks,
            tasks_executed=tasks_executed,
            execution_metadata=final_exec_metadata
        )
        
        return {
            "success": True,
            "agent_name": AgentName.SOURCING_SIGNAL.value,
            "artifact_pack": pack,
            "tokens_used": total_tokens,
            "output": {
                "signals": signals,
                "urgency_score": urgency_score,
                "summary": context.get("summary", ""),
            }
        }



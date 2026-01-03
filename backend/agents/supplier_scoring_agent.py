"""
Supplier Scoring Agent - Evaluates and ranks suppliers.

Purpose: Convert human-defined evaluation criteria into structured score inputs;
process historical performance and risk data.
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


class SupplierScoringAgent(BaseAgent):
    """
    Supplier Scoring Agent - Supplier evaluation and ranking.
    
    Sub-tasks:
    - build_evaluation_criteria
    - pull_supplier_performance
    - pull_risk_indicators
    - normalize_metrics
    - compute_scores_and_rank
    - eligibility_checks
    - generate_explanations
    """
    
    def __init__(self, tier: int = 1):
        super().__init__(name="SupplierScoring", tier=tier)
        self.registry = get_task_registry()
        self.playbook = AgentPlaybook()
    
    def execute(
        self, 
        case_context: Dict[str, Any], 
        user_intent: str
    ) -> Dict[str, Any]:
        """
        Execute supplier scoring workflow.
        
        Returns ArtifactPack with scorecard, shortlist, and explanations.
        """
        # Get tasks to execute
        tasks = self.playbook.get_tasks_for_agent(
            AgentName.SUPPLIER_SCORING,
            UserGoal.CREATE,
            None,
            case_context.get("dtp_stage", "DTP-02")
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
        
        # Evaluation Scorecard artifact
        criteria = context.get("criteria", [])
        evaluation_scorecard = (
            ArtifactBuilder(ArtifactType.EVALUATION_SCORECARD, AgentName.SUPPLIER_SCORING)
            .with_title("Evaluation Criteria")
            .with_content({
                "criteria": criteria,
            })
            .with_content_text(
                f"Evaluation based on {len(criteria)} criteria: " +
                ", ".join([c.get("name", "") for c in criteria])
            )
            .with_grounding(all_grounded_in[:2])
            .build()
        )
        artifacts.append(evaluation_scorecard)
        
        # Supplier Scorecard artifact
        eligible = context.get("eligible_suppliers", [])
        ineligible = context.get("ineligible_suppliers", [])
        all_suppliers = eligible + ineligible
        
        supplier_scorecard = (
            ArtifactBuilder(ArtifactType.SUPPLIER_SCORECARD, AgentName.SUPPLIER_SCORING)
            .with_title("Supplier Scorecard")
            .with_content({
                "suppliers": all_suppliers,
                "eligible_count": len(eligible),
                "ineligible_count": len(ineligible),
            })
            .with_content_text(
                f"Evaluated {len(all_suppliers)} suppliers. "
                f"{len(eligible)} eligible, {len(ineligible)} ineligible."
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(supplier_scorecard)
        
        # Supplier Shortlist artifact
        explanations = context.get("explanations", {})
        shortlist_data = []
        for s in eligible[:3]:
            shortlist_data.append({
                **s,
                "explanation": explanations.get(s["supplier_id"], "")
            })
        
        supplier_shortlist = (
            ArtifactBuilder(ArtifactType.SUPPLIER_SHORTLIST, AgentName.SUPPLIER_SCORING)
            .with_title("Recommended Shortlist")
            .with_content({
                "shortlist": shortlist_data,
                "top_choice": shortlist_data[0] if shortlist_data else None,
            })
            .with_content_text(
                f"Top {len(shortlist_data)} suppliers recommended. " +
                (f"Leader: {shortlist_data[0]['supplier_name']} ({shortlist_data[0]['total_score']:.1f}/10)"
                 if shortlist_data else "No eligible suppliers found.")
            )
            .with_grounding(all_grounded_in)
            .build()
        )
        artifacts.append(supplier_shortlist)
        
        # Build next actions
        next_actions = []
        if eligible:
            next_actions.append(build_next_action(
                label="Proceed to RFx",
                why=f"Shortlist of {len(eligible)} suppliers ready for sourcing",
                agent_name=AgentName.SUPPLIER_SCORING
            ))
            next_actions.append(build_next_action(
                label="Request additional data",
                why="Gather more information for higher confidence scoring",
                agent_name=AgentName.SUPPLIER_SCORING
            ))
        else:
            next_actions.append(build_next_action(
                label="Expand supplier search",
                why="No eligible suppliers found - broaden criteria",
                agent_name=AgentName.SUPPLIER_SCORING
            ))
        
        # Build risks
        risks = []
        for s in ineligible:
            issues = s.get("eligibility_issues", [])
            if issues:
                risks.append(build_risk_item(
                    severity="medium",
                    description=f"{s['supplier_name']}: {issues[0]}",
                    mitigation="Address eligibility issues or remove from consideration"
                ))
        
        # Build artifact pack
        pack = build_artifact_pack(
            agent_name=AgentName.SUPPLIER_SCORING,
            artifacts=artifacts,
            next_actions=next_actions,
            risks=risks[:3],
            tasks_executed=tasks_executed
        )
        
        return {
            "success": True,
            "agent_name": AgentName.SUPPLIER_SCORING.value,
            "artifact_pack": pack,
            "tokens_used": total_tokens,
            "output": {
                "shortlisted_suppliers": shortlist_data,
                "evaluation_criteria": criteria,
                "recommendation": supplier_shortlist.content_text,
            }
        }


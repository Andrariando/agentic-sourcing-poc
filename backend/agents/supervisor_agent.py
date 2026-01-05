"""
Supervisor Agent - Orchestrates workflow, validates inputs, routes to agents.

GOVERNANCE: This is the ONLY component allowed to write canonical case state.
All other agents return outputs only.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from backend.agents.base import BaseAgent
from backend.tasks.planners import AgentPlaybook
from backend.tasks.registry import get_task_registry
from backend.artifacts.builders import (
    ArtifactBuilder, build_artifact_pack, build_next_action
)
from shared.constants import AgentName, ArtifactType, UserGoal, WorkType, DTP_STAGES
from shared.schemas import ArtifactPack, ActionPlan, IntentResult, NextAction


class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent - Workflow orchestrator and state manager.
    
    Responsibilities:
    - Classify user intent (two-level)
    - Validate stage transitions
    - Select sourcing pathway
    - Route to appropriate agent + tasks
    - Enforce human checkpoints
    - Update state (ONLY Supervisor can do this)
    """
    
    def __init__(self, tier: int = 1):
        super().__init__(name="Supervisor", tier=tier)
        self.playbook = AgentPlaybook()
    
    def execute(self, case_context: Dict[str, Any], user_intent: str) -> Dict[str, Any]:
        """
        Execute supervisor workflow.
        
        Returns action plan without running downstream agents.
        Downstream agent execution is handled by ChatService.
        """
        # Classify intent
        intent_result = self.classify_intent_two_level(user_intent, case_context)
        
        # Validate stage transition if needed
        if intent_result.user_goal == UserGoal.DECIDE.value:
            valid, reason = self.validate_stage_transition(case_context)
            if not valid:
                return {
                    "success": False,
                    "blocked": True,
                    "reason": reason,
                    "intent": intent_result,
                }
        
        # Validate required inputs
        missing_inputs = self.validate_required_inputs(case_context, intent_result)
        
        # Select sourcing pathway and route
        action_plan = self.route_agent_and_tasks(intent_result, case_context)
        
        return {
            "success": True,
            "intent": intent_result,
            "action_plan": action_plan,
            "missing_inputs": missing_inputs,
            "requires_human": action_plan.approval_required,
        }
    
    def classify_intent_two_level(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> IntentResult:
        """
        Classify user intent into (user_goal, work_type).
        
        Uses deterministic rules first, then context.
        """
        message_lower = user_message.lower()
        
        # Determine user goal
        user_goal = UserGoal.UNDERSTAND  # Default
        
        # TRACK patterns
        if any(kw in message_lower for kw in ['status', 'progress', 'where are we', 'update me', 'current']):
            user_goal = UserGoal.TRACK
        
        # CREATE patterns
        elif any(kw in message_lower for kw in ['create', 'draft', 'generate', 'build', 'make', 'prepare']):
            user_goal = UserGoal.CREATE
        
        # CHECK patterns
        elif any(kw in message_lower for kw in ['check', 'validate', 'verify', 'compliant', 'review']):
            user_goal = UserGoal.CHECK
        
        # DECIDE patterns
        elif any(kw in message_lower for kw in ['decide', 'approve', 'select', 'choose', 'finalize', 'award']):
            user_goal = UserGoal.DECIDE
        
        # UNDERSTAND patterns
        elif any(kw in message_lower for kw in ['explain', 'why', 'how', 'what', 'understand', 'tell me']):
            user_goal = UserGoal.UNDERSTAND
        
        # Scan signals pattern
        elif any(kw in message_lower for kw in ['scan', 'signal', 'monitor', 'detect']):
            user_goal = UserGoal.TRACK
        
        # Score/evaluate pattern
        elif any(kw in message_lower for kw in ['score', 'evaluate', 'rank', 'compare supplier']):
            user_goal = UserGoal.CREATE
        
        # Negotiate pattern
        elif any(kw in message_lower for kw in ['negotiat', 'bid', 'leverage']):
            user_goal = UserGoal.CREATE
        
        # Contract/terms pattern
        elif any(kw in message_lower for kw in ['contract', 'terms', 'extract']):
            user_goal = UserGoal.CREATE
        
        # Implementation pattern
        elif any(kw in message_lower for kw in ['implement', 'rollout', 'checklist', 'savings']):
            user_goal = UserGoal.CREATE
        
        # Determine work type
        work_type = WorkType.DATA  # Default
        
        if any(kw in message_lower for kw in ['draft', 'document', 'template', 'report', 'plan']):
            work_type = WorkType.ARTIFACT
        elif any(kw in message_lower for kw in ['approve', 'decide', 'select']):
            work_type = WorkType.APPROVAL
        elif any(kw in message_lower for kw in ['compliant', 'policy', 'rule', 'valid']):
            work_type = WorkType.COMPLIANCE
        elif any(kw in message_lower for kw in ['saving', 'value', 'cost', 'roi']):
            work_type = WorkType.VALUE
        
        return IntentResult(
            user_goal=user_goal.value,
            work_type=work_type.value,
            confidence=0.85,
            rationale=f"Classified from message patterns"
        )
    
    def validate_stage_transition(
        self, 
        context: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate if current stage allows the requested action."""
        dtp_stage = context.get("dtp_stage", "DTP-01")
        
        # Terminal stage check
        if dtp_stage == "DTP-06":
            return False, "Case is in execution phase. No further stage transitions available."
        
        return True, None
    
    def validate_required_inputs(
        self, 
        context: Dict[str, Any],
        intent: IntentResult
    ) -> List[str]:
        """Check for missing required inputs."""
        missing = []
        
        # Check for category
        if not context.get("category_id"):
            missing.append("Category must be specified")
        
        # Stage-specific requirements
        dtp_stage = context.get("dtp_stage", "DTP-01")
        
        if dtp_stage in ["DTP-03", "DTP-04"]:
            if not context.get("supplier_id") and intent.user_goal in ["CREATE", "DECIDE"]:
                missing.append("Supplier must be identified for this stage")
        
        if dtp_stage == "DTP-05":
            if not context.get("contract_id"):
                missing.append("Contract reference required for contracting stage")
        
        return missing
    
    def select_sourcing_pathway(
        self, 
        context: Dict[str, Any]
    ) -> str:
        """Select sourcing pathway based on rules."""
        # Simple rule-based pathway selection
        estimated_value = context.get("estimated_value", 0)
        is_strategic = context.get("is_strategic", False)
        
        if is_strategic or estimated_value > 500000:
            return "strategic_sourcing"
        elif estimated_value > 50000:
            return "competitive_bid"
        else:
            return "simplified"
    
    def route_agent_and_tasks(
        self, 
        intent: IntentResult,
        context: Dict[str, Any]
    ) -> ActionPlan:
        """
        Determine which agent and tasks to execute.
        
        Returns deterministic ActionPlan based on intent and stage.
        """
        dtp_stage = context.get("dtp_stage", "DTP-01")
        user_goal = UserGoal(intent.user_goal)
        work_type = WorkType(intent.work_type)
        
        # Get appropriate agent
        agent_name = self.playbook.get_agent_for_intent(user_goal, work_type, dtp_stage)
        
        if not agent_name:
            # Default based on stage
            stage_defaults = {
                "DTP-01": AgentName.SOURCING_SIGNAL,
                "DTP-02": AgentName.SUPPLIER_SCORING,
                "DTP-03": AgentName.RFX_DRAFT,
                "DTP-04": AgentName.NEGOTIATION_SUPPORT,
                "DTP-05": AgentName.CONTRACT_SUPPORT,
                "DTP-06": AgentName.IMPLEMENTATION,
            }
            agent_name = stage_defaults.get(dtp_stage, AgentName.SOURCING_SIGNAL)
        
        # Get tasks for agent
        tasks = self.playbook.get_tasks_for_agent(agent_name, user_goal, work_type, dtp_stage)
        
        # Determine if approval required
        approval_required = (
            user_goal == UserGoal.DECIDE or
            work_type == WorkType.APPROVAL or
            dtp_stage in ["DTP-04", "DTP-05"]  # High-stakes stages
        )
        
        # Determine UI mode
        ui_mode_map = {
            AgentName.SOURCING_SIGNAL: "signals",
            AgentName.SUPPLIER_SCORING: "scoring",
            AgentName.RFX_DRAFT: "rfx",
            AgentName.NEGOTIATION_SUPPORT: "negotiation",
            AgentName.CONTRACT_SUPPORT: "contract",
            AgentName.IMPLEMENTATION: "implementation",
        }
        ui_mode = ui_mode_map.get(agent_name, "default")
        
        return ActionPlan(
            agent_name=agent_name.value,
            tasks=tasks,
            approval_required=approval_required,
            ui_mode=ui_mode
        )
    
    def enforce_human_checkpoints(
        self, 
        context: Dict[str, Any],
        action_plan: ActionPlan
    ) -> bool:
        """Check if human approval checkpoint is required."""
        return action_plan.approval_required
    
    def build_status_summary(self, context: Dict[str, Any]) -> ArtifactPack:
        """Build a status summary artifact pack."""
        dtp_stage = context.get("dtp_stage", "DTP-01")
        status = context.get("status", "In Progress")
        
        # Build status artifact
        status_artifact = (
            ArtifactBuilder(ArtifactType.STATUS_SUMMARY, AgentName.SUPERVISOR)
            .with_title("Case Status Summary")
            .with_content({
                "dtp_stage": dtp_stage,
                "status": status,
                "category": context.get("category_id"),
                "supplier": context.get("supplier_id"),
                "contract": context.get("contract_id"),
            })
            .with_content_text(f"Case is at {dtp_stage} stage with status: {status}")
            .build()
        )
        
        # Build next actions based on stage
        next_actions = self._get_stage_next_actions(dtp_stage, context)
        
        return build_artifact_pack(
            agent_name=AgentName.SUPERVISOR,
            artifacts=[status_artifact],
            next_actions=next_actions,
            tasks_executed=["build_status_summary"]
        )
    
    def _get_stage_next_actions(
        self, 
        dtp_stage: str, 
        context: Dict[str, Any]
    ) -> List[NextAction]:
        """Get recommended next actions for stage."""
        actions = []
        
        if dtp_stage == "DTP-01":
            actions.append(build_next_action(
                "Scan signals", 
                "Identify sourcing opportunities and risks",
                AgentName.SUPERVISOR
            ))
            actions.append(build_next_action(
                "Score suppliers", 
                "Evaluate potential suppliers",
                AgentName.SUPERVISOR
            ))
        
        elif dtp_stage == "DTP-02":
            actions.append(build_next_action(
                "Draft RFx", 
                "Create request for proposal/quote",
                AgentName.SUPERVISOR
            ))
        
        elif dtp_stage == "DTP-03":
            actions.append(build_next_action(
                "Evaluate responses", 
                "Score and rank supplier responses",
                AgentName.SUPERVISOR
            ))
        
        elif dtp_stage == "DTP-04":
            actions.append(build_next_action(
                "Support negotiation", 
                "Get negotiation insights and targets",
                AgentName.SUPERVISOR
            ))
        
        elif dtp_stage == "DTP-05":
            actions.append(build_next_action(
                "Extract key terms", 
                "Review and validate contract terms",
                AgentName.SUPERVISOR
            ))
        
        elif dtp_stage == "DTP-06":
            actions.append(build_next_action(
                "Generate implementation plan", 
                "Create rollout checklist and KPIs",
                AgentName.SUPERVISOR
            ))
        
        return actions




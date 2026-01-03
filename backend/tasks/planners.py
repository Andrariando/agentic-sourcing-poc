"""
Deterministic playbooks mapping intent to task sequences.

Each agent has a playbook that determines which tasks to run
based on user intent, DTP stage, and available data.
"""
from typing import List, Dict, Any, Optional
from shared.constants import AgentName, UserGoal, WorkType


class AgentPlaybook:
    """
    Deterministic task planning for agents.
    
    Maps (user_goal, work_type, dtp_stage) -> ordered list of tasks.
    """
    
    # Sourcing Signal Agent playbooks
    SOURCING_SIGNAL_PLAYBOOKS = {
        # Default signal scan
        "default": [
            "detect_contract_expiry_signals",
            "detect_performance_degradation_signals",
            "detect_spend_anomalies",
            "apply_relevance_filters",
            "semantic_grounded_summary",
            "produce_autoprep_recommendations",
        ],
        # Quick status check
        "track": [
            "detect_contract_expiry_signals",
            "apply_relevance_filters",
        ],
        # Full analysis
        "understand": [
            "detect_contract_expiry_signals",
            "detect_performance_degradation_signals",
            "detect_spend_anomalies",
            "apply_relevance_filters",
            "semantic_grounded_summary",
        ],
    }
    
    # Supplier Scoring Agent playbooks
    SUPPLIER_SCORING_PLAYBOOKS = {
        "default": [
            "build_evaluation_criteria",
            "pull_supplier_performance",
            "pull_risk_indicators",
            "normalize_metrics",
            "compute_scores_and_rank",
            "eligibility_checks",
            "generate_explanations",
        ],
        "track": [
            "pull_supplier_performance",
            "compute_scores_and_rank",
        ],
        "check": [
            "pull_supplier_performance",
            "pull_risk_indicators",
            "eligibility_checks",
        ],
    }
    
    # RFx Draft Agent playbooks
    RFX_DRAFT_PLAYBOOKS = {
        "default": [
            "determine_rfx_path",
            "retrieve_templates_and_past_examples",
            "assemble_rfx_sections",
            "completeness_checks",
            "draft_questions_and_requirements",
            "create_qa_tracker",
        ],
        "create": [
            "determine_rfx_path",
            "retrieve_templates_and_past_examples",
            "assemble_rfx_sections",
            "draft_questions_and_requirements",
            "create_qa_tracker",
        ],
        "check": [
            "completeness_checks",
        ],
    }
    
    # Negotiation Support Agent playbooks
    NEGOTIATION_SUPPORT_PLAYBOOKS = {
        "default": [
            "compare_bids",
            "leverage_point_extraction",
            "benchmark_retrieval",
            "price_anomaly_detection",
            "propose_targets_and_fallbacks",
            "negotiation_playbook",
        ],
        "understand": [
            "compare_bids",
            "benchmark_retrieval",
        ],
        "create": [
            "compare_bids",
            "leverage_point_extraction",
            "propose_targets_and_fallbacks",
            "negotiation_playbook",
        ],
    }
    
    # Contract Support Agent playbooks
    CONTRACT_SUPPORT_PLAYBOOKS = {
        "default": [
            "extract_key_terms",
            "term_validation",
            "term_alignment_summary",
            "implementation_handoff_packet",
        ],
        "check": [
            "extract_key_terms",
            "term_validation",
        ],
        "create": [
            "extract_key_terms",
            "term_alignment_summary",
            "implementation_handoff_packet",
        ],
    }
    
    # Implementation Agent playbooks
    IMPLEMENTATION_PLAYBOOKS = {
        "default": [
            "build_rollout_checklist",
            "compute_expected_savings",
            "define_early_indicators",
            "reporting_templates",
        ],
        "create": [
            "build_rollout_checklist",
            "define_early_indicators",
            "reporting_templates",
        ],
        "track": [
            "compute_expected_savings",
            "define_early_indicators",
        ],
    }
    
    # Map agent names to their playbooks
    AGENT_PLAYBOOKS = {
        AgentName.SOURCING_SIGNAL: SOURCING_SIGNAL_PLAYBOOKS,
        AgentName.SUPPLIER_SCORING: SUPPLIER_SCORING_PLAYBOOKS,
        AgentName.RFX_DRAFT: RFX_DRAFT_PLAYBOOKS,
        AgentName.NEGOTIATION_SUPPORT: NEGOTIATION_SUPPORT_PLAYBOOKS,
        AgentName.CONTRACT_SUPPORT: CONTRACT_SUPPORT_PLAYBOOKS,
        AgentName.IMPLEMENTATION: IMPLEMENTATION_PLAYBOOKS,
    }
    
    @classmethod
    def get_tasks_for_agent(
        cls,
        agent_name: AgentName,
        user_goal: Optional[UserGoal] = None,
        work_type: Optional[WorkType] = None,
        dtp_stage: Optional[str] = None
    ) -> List[str]:
        """
        Get ordered list of tasks for an agent based on intent.
        
        Args:
            agent_name: The agent to get tasks for
            user_goal: Primary user goal (TRACK, UNDERSTAND, CREATE, CHECK, DECIDE)
            work_type: Secondary work type
            dtp_stage: Current DTP stage
            
        Returns:
            Ordered list of task names
        """
        playbooks = cls.AGENT_PLAYBOOKS.get(agent_name, {})
        
        if not playbooks:
            return []
        
        # Try to match user goal first
        if user_goal:
            goal_key = user_goal.value.lower()
            if goal_key in playbooks:
                return playbooks[goal_key]
        
        # Fall back to default
        return playbooks.get("default", [])
    
    @classmethod
    def get_agent_for_intent(
        cls,
        user_goal: UserGoal,
        work_type: WorkType,
        dtp_stage: str
    ) -> Optional[AgentName]:
        """
        Determine which agent should handle the request.
        
        Rules-based routing:
        - TRACK/UNDERSTAND often need status or existing data
        - CREATE routes to appropriate drafting agent
        - CHECK routes to validation agents
        - DECIDE routes based on DTP stage
        """
        # Stage-based routing for DECIDE
        if user_goal == UserGoal.DECIDE:
            stage_agents = {
                "DTP-01": AgentName.SOURCING_SIGNAL,
                "DTP-02": AgentName.SUPPLIER_SCORING,
                "DTP-03": AgentName.RFX_DRAFT,
                "DTP-04": AgentName.NEGOTIATION_SUPPORT,
                "DTP-05": AgentName.CONTRACT_SUPPORT,
                "DTP-06": AgentName.IMPLEMENTATION,
            }
            return stage_agents.get(dtp_stage)
        
        # CREATE routes based on work_type and stage
        if user_goal == UserGoal.CREATE:
            if work_type == WorkType.ARTIFACT:
                if dtp_stage in ["DTP-01", "DTP-02"]:
                    return AgentName.RFX_DRAFT
                elif dtp_stage == "DTP-03":
                    return AgentName.RFX_DRAFT
                elif dtp_stage == "DTP-04":
                    return AgentName.NEGOTIATION_SUPPORT
                elif dtp_stage == "DTP-05":
                    return AgentName.CONTRACT_SUPPORT
                elif dtp_stage == "DTP-06":
                    return AgentName.IMPLEMENTATION
        
        # CHECK routes to validation agents
        if user_goal == UserGoal.CHECK:
            if work_type == WorkType.COMPLIANCE:
                if dtp_stage in ["DTP-05", "DTP-06"]:
                    return AgentName.CONTRACT_SUPPORT
            return AgentName.SUPPLIER_SCORING
        
        # TRACK/UNDERSTAND - often can use cached data or summary
        if user_goal in [UserGoal.TRACK, UserGoal.UNDERSTAND]:
            if dtp_stage == "DTP-01":
                return AgentName.SOURCING_SIGNAL
            elif dtp_stage in ["DTP-02", "DTP-03"]:
                return AgentName.SUPPLIER_SCORING
            elif dtp_stage == "DTP-04":
                return AgentName.NEGOTIATION_SUPPORT
            elif dtp_stage == "DTP-05":
                return AgentName.CONTRACT_SUPPORT
            elif dtp_stage == "DTP-06":
                return AgentName.IMPLEMENTATION
        
        return None


def get_playbook() -> AgentPlaybook:
    """Get the playbook instance."""
    return AgentPlaybook()


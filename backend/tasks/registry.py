"""
Task Registry - Maps task names to callable task classes.

Provides centralized task lookup for agents.
"""
from typing import Dict, Type, Optional, List
from dataclasses import dataclass

from backend.tasks.base_task import BaseTask


@dataclass
class TaskMetadata:
    """Metadata about a registered task."""
    task_name: str
    task_class: Type[BaseTask]
    agent_name: str
    description: str = ""
    requires_llm: bool = False
    requires_retrieval: bool = True


class TaskRegistry:
    """
    Central registry for all task types.
    
    Tasks are registered by name and can be looked up by agents.
    """
    
    _instance = None
    _tasks: Dict[str, TaskMetadata] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._tasks = {}
        return cls._instance
    
    def register(
        self,
        task_name: str,
        task_class: Type[BaseTask],
        agent_name: str,
        description: str = "",
        requires_llm: bool = False,
        requires_retrieval: bool = True
    ):
        """Register a task."""
        self._tasks[task_name] = TaskMetadata(
            task_name=task_name,
            task_class=task_class,
            agent_name=agent_name,
            description=description,
            requires_llm=requires_llm,
            requires_retrieval=requires_retrieval
        )
    
    def get_task(self, task_name: str) -> Optional[BaseTask]:
        """Get a task instance by name."""
        meta = self._tasks.get(task_name)
        if meta:
            return meta.task_class(name=task_name)
        return None
    
    def get_tasks_for_agent(self, agent_name: str) -> List[str]:
        """Get all task names for an agent."""
        return [
            name for name, meta in self._tasks.items()
            if meta.agent_name == agent_name
        ]
    
    def list_tasks(self) -> List[TaskMetadata]:
        """List all registered tasks."""
        return list(self._tasks.values())


# Singleton accessor
_registry = None


def get_task_registry() -> TaskRegistry:
    """Get the global task registry."""
    global _registry
    if _registry is None:
        _registry = TaskRegistry()
        # Auto-register all tasks
        _register_all_tasks(_registry)
    return _registry


def _register_all_tasks(registry: TaskRegistry):
    """Register all task implementations."""
    # Import and register signal tasks
    from backend.tasks.signal_tasks import (
        DetectContractExpiryTask,
        DetectPerformanceDegradationTask,
        DetectSpendAnomaliesTask,
        ApplyRelevanceFiltersTask,
        SemanticGroundedSummaryTask,
        ProduceAutoprepRecommendationsTask,
    )
    
    registry.register("detect_contract_expiry_signals", DetectContractExpiryTask, "SOURCING_SIGNAL",
                      "Detect contracts expiring soon")
    registry.register("detect_performance_degradation_signals", DetectPerformanceDegradationTask, "SOURCING_SIGNAL",
                      "Detect supplier performance issues")
    registry.register("detect_spend_anomalies", DetectSpendAnomaliesTask, "SOURCING_SIGNAL",
                      "Detect spend pattern anomalies")
    registry.register("apply_relevance_filters", ApplyRelevanceFiltersTask, "SOURCING_SIGNAL",
                      "Filter signals by relevance")
    registry.register("semantic_grounded_summary", SemanticGroundedSummaryTask, "SOURCING_SIGNAL",
                      "Generate grounded signal summary", requires_llm=True)
    registry.register("produce_autoprep_recommendations", ProduceAutoprepRecommendationsTask, "SOURCING_SIGNAL",
                      "Generate autoprep recommendations")
    
    # Import and register scoring tasks
    from backend.tasks.scoring_tasks import (
        BuildEvaluationCriteriaTask,
        PullSupplierPerformanceTask,
        PullRiskIndicatorsTask,
        NormalizeMetricsTask,
        ComputeScoresAndRankTask,
        EligibilityChecksTask,
        GenerateExplanationsTask,
    )
    
    registry.register("build_evaluation_criteria", BuildEvaluationCriteriaTask, "SUPPLIER_SCORING",
                      "Build evaluation criteria from inputs")
    registry.register("pull_supplier_performance", PullSupplierPerformanceTask, "SUPPLIER_SCORING",
                      "Pull supplier performance data")
    registry.register("pull_risk_indicators", PullRiskIndicatorsTask, "SUPPLIER_SCORING",
                      "Pull risk indicator data")
    registry.register("normalize_metrics", NormalizeMetricsTask, "SUPPLIER_SCORING",
                      "Normalize metrics for comparison")
    registry.register("compute_scores_and_rank", ComputeScoresAndRankTask, "SUPPLIER_SCORING",
                      "Compute final scores and ranking")
    registry.register("eligibility_checks", EligibilityChecksTask, "SUPPLIER_SCORING",
                      "Check supplier eligibility rules")
    registry.register("generate_explanations", GenerateExplanationsTask, "SUPPLIER_SCORING",
                      "Generate score explanations", requires_llm=True)
    
    # Import and register RFx tasks
    from backend.tasks.rfx_tasks import (
        DetermineRfxPathTask,
        RetrieveTemplatesTask,
        AssembleRfxSectionsTask,
        CompletenessChecksTask,
        DraftQuestionsTask,
        CreateQaTrackerTask,
    )
    
    registry.register("determine_rfx_path", DetermineRfxPathTask, "RFX_DRAFT",
                      "Determine RFI/RFP/RFQ path")
    registry.register("retrieve_templates_and_past_examples", RetrieveTemplatesTask, "RFX_DRAFT",
                      "Retrieve RFx templates and examples")
    registry.register("assemble_rfx_sections", AssembleRfxSectionsTask, "RFX_DRAFT",
                      "Assemble RFx document sections")
    registry.register("completeness_checks", CompletenessChecksTask, "RFX_DRAFT",
                      "Check RFx completeness")
    registry.register("draft_questions_and_requirements", DraftQuestionsTask, "RFX_DRAFT",
                      "Draft questions and requirements", requires_llm=True)
    registry.register("create_qa_tracker", CreateQaTrackerTask, "RFX_DRAFT",
                      "Create Q&A tracking table")
    
    # Import and register negotiation tasks
    from backend.tasks.negotiation_tasks import (
        CompareBidsTask,
        LeveragePointExtractionTask,
        BenchmarkRetrievalTask,
        PriceAnomalyDetectionTask,
        ProposeTargetsAndFallbacksTask,
        NegotiationPlaybookTask,
    )
    
    registry.register("compare_bids", CompareBidsTask, "NEGOTIATION_SUPPORT",
                      "Compare supplier bids")
    registry.register("leverage_point_extraction", LeveragePointExtractionTask, "NEGOTIATION_SUPPORT",
                      "Extract negotiation leverage points")
    registry.register("benchmark_retrieval", BenchmarkRetrievalTask, "NEGOTIATION_SUPPORT",
                      "Retrieve market benchmarks")
    registry.register("price_anomaly_detection", PriceAnomalyDetectionTask, "NEGOTIATION_SUPPORT",
                      "Detect pricing anomalies")
    registry.register("propose_targets_and_fallbacks", ProposeTargetsAndFallbacksTask, "NEGOTIATION_SUPPORT",
                      "Propose target terms and fallbacks")
    registry.register("negotiation_playbook", NegotiationPlaybookTask, "NEGOTIATION_SUPPORT",
                      "Generate negotiation playbook", requires_llm=True)
    
    # Import and register contract tasks
    from backend.tasks.contract_tasks import (
        ExtractKeyTermsTask,
        TermValidationTask,
        TermAlignmentSummaryTask,
        ImplementationHandoffPacketTask,
    )
    
    registry.register("extract_key_terms", ExtractKeyTermsTask, "CONTRACT_SUPPORT",
                      "Extract key contract terms")
    registry.register("term_validation", TermValidationTask, "CONTRACT_SUPPORT",
                      "Validate contract terms")
    registry.register("term_alignment_summary", TermAlignmentSummaryTask, "CONTRACT_SUPPORT",
                      "Summarize term alignment", requires_llm=True)
    registry.register("implementation_handoff_packet", ImplementationHandoffPacketTask, "CONTRACT_SUPPORT",
                      "Create implementation handoff packet")
    
    # Import and register implementation tasks
    from backend.tasks.implementation_tasks import (
        BuildRolloutChecklistTask,
        ComputeExpectedSavingsTask,
        DefineEarlyIndicatorsTask,
        ReportingTemplatesTask,
    )
    
    registry.register("build_rollout_checklist", BuildRolloutChecklistTask, "IMPLEMENTATION",
                      "Build rollout checklist")
    registry.register("compute_expected_savings", ComputeExpectedSavingsTask, "IMPLEMENTATION",
                      "Compute expected savings")
    registry.register("define_early_indicators", DefineEarlyIndicatorsTask, "IMPLEMENTATION",
                      "Define early success indicators")
    registry.register("reporting_templates", ReportingTemplatesTask, "IMPLEMENTATION",
                      "Generate reporting templates")




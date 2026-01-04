"""
Artifact builders - Compose task outputs into ArtifactPack.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from shared.schemas import (
    Artifact, ArtifactPack, NextAction, RiskItem, GroundingReference,
    ExecutionMetadata
)
from shared.constants import ArtifactType, AgentName
from backend.artifacts.utils import (
    generate_artifact_id, generate_pack_id, merge_grounding, 
    determine_verification_status
)
from backend.tasks.base_task import TaskResult


class ArtifactBuilder:
    """
    Builder for creating artifacts from task results.
    
    Provides fluent API for constructing artifacts with proper
    grounding and verification status.
    """
    
    def __init__(self, artifact_type: ArtifactType, agent_name: AgentName):
        self.artifact_type = artifact_type
        self.agent_name = agent_name
        self._title = ""
        self._content = {}
        self._content_text = ""
        self._grounded_in: List[GroundingReference] = []
        self._task_name = ""
    
    def with_title(self, title: str) -> "ArtifactBuilder":
        self._title = title
        return self
    
    def with_content(self, content: Dict[str, Any]) -> "ArtifactBuilder":
        self._content = content
        return self
    
    def with_content_text(self, text: str) -> "ArtifactBuilder":
        self._content_text = text
        return self
    
    def with_grounding(self, refs: List[GroundingReference]) -> "ArtifactBuilder":
        self._grounded_in.extend(refs)
        return self
    
    def from_task_result(self, result: TaskResult) -> "ArtifactBuilder":
        self._task_name = result.task_name
        self._grounded_in.extend(result.grounded_in)
        return self
    
    def build(self) -> Artifact:
        """Build the artifact."""
        return Artifact(
            artifact_id=generate_artifact_id(self.artifact_type.value),
            type=self.artifact_type.value,
            title=self._title,
            content=self._content,
            content_text=self._content_text,
            grounded_in=self._grounded_in,
            created_at=datetime.now().isoformat(),
            created_by_agent=self.agent_name.value,
            created_by_task=self._task_name,
            verification_status=determine_verification_status(self._grounded_in)
        )


def build_artifact_pack(
    agent_name: AgentName,
    artifacts: List[Artifact],
    next_actions: Optional[List[NextAction]] = None,
    risks: Optional[List[RiskItem]] = None,
    notes: Optional[List[str]] = None,
    tasks_executed: Optional[List[str]] = None,
    execution_metadata: Optional[ExecutionMetadata] = None
) -> ArtifactPack:
    """
    Build a complete artifact pack from agent execution.
    
    Args:
        agent_name: The agent that produced this pack
        artifacts: List of artifacts produced
        next_actions: Recommended next actions
        risks: Identified risks
        notes: Additional notes
        tasks_executed: List of task names that were executed
        execution_metadata: Detailed execution metadata for audit trail
        
    Returns:
        Complete ArtifactPack
    """
    # Merge grounding from all artifacts
    all_grounding = [a.grounded_in for a in artifacts]
    merged_grounding = merge_grounding(all_grounding)
    
    return ArtifactPack(
        pack_id=generate_pack_id(),
        artifacts=artifacts,
        next_actions=next_actions or [],
        risks=risks or [],
        notes=notes or [],
        grounded_in=merged_grounding,
        agent_name=agent_name.value,
        tasks_executed=tasks_executed or [],
        created_at=datetime.now().isoformat(),
        execution_metadata=execution_metadata
    )


def build_next_action(
    label: str,
    why: str,
    agent_name: AgentName,
    task_name: str = "",
    owner: str = "user",
    depends_on: Optional[List[str]] = None
) -> NextAction:
    """Build a next action recommendation."""
    from uuid import uuid4
    
    return NextAction(
        action_id=f"ACT-{uuid4().hex[:8]}",
        label=label,
        why=why,
        owner=owner,
        depends_on=depends_on or [],
        recommended_by_agent=agent_name.value,
        recommended_by_task=task_name
    )


def build_risk_item(
    severity: str,
    description: str,
    mitigation: str = ""
) -> RiskItem:
    """Build a risk item."""
    return RiskItem(
        severity=severity,
        description=description,
        mitigation=mitigation
    )



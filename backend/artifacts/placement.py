"""
Artifact placement map - single source of truth for UI section routing.

This module defines where each artifact type should appear in the UI
(Decision Console, Risk Panel, Supplier Compare, etc.).
"""
from enum import Enum
from typing import Dict, Optional
import logging

from shared.constants import ArtifactType

logger = logging.getLogger(__name__)


class ArtifactPlacement(str, Enum):
    """UI sections where artifacts can be placed."""
    DECISION_CONSOLE = "decision_console"
    RISK_PANEL = "risk_panel"
    SUPPLIER_COMPARE = "supplier_compare"
    CASE_SUMMARY = "case_summary"
    TIMELINE = "timeline"
    ACTIVITY_LOG = "activity_log"


# Single source of truth: artifact type -> placement section
ARTIFACT_PLACEMENT_MAP: Dict[ArtifactType, ArtifactPlacement] = {
    # Sourcing Signal Agent outputs -> Decision Console (strategic signals)
    ArtifactType.SIGNAL_REPORT: ArtifactPlacement.DECISION_CONSOLE,
    ArtifactType.SIGNAL_SUMMARY: ArtifactPlacement.CASE_SUMMARY,
    ArtifactType.AUTOPREP_BUNDLE: ArtifactPlacement.DECISION_CONSOLE,
    
    # Supplier Scoring Agent outputs -> Supplier Compare
    ArtifactType.EVALUATION_SCORECARD: ArtifactPlacement.SUPPLIER_COMPARE,
    ArtifactType.SUPPLIER_SCORECARD: ArtifactPlacement.SUPPLIER_COMPARE,
    ArtifactType.SUPPLIER_SHORTLIST: ArtifactPlacement.SUPPLIER_COMPARE,
    
    # RFx Draft Agent outputs -> Decision Console
    ArtifactType.RFX_PATH: ArtifactPlacement.DECISION_CONSOLE,
    ArtifactType.RFX_DRAFT_PACK: ArtifactPlacement.DECISION_CONSOLE,
    ArtifactType.RFX_QA_TRACKER: ArtifactPlacement.ACTIVITY_LOG,
    
    # Negotiation Support Agent outputs -> Decision Console
    ArtifactType.NEGOTIATION_PLAN: ArtifactPlacement.DECISION_CONSOLE,
    ArtifactType.LEVERAGE_SUMMARY: ArtifactPlacement.DECISION_CONSOLE,
    ArtifactType.TARGET_TERMS: ArtifactPlacement.DECISION_CONSOLE,
    
    # Contract Support Agent outputs -> Risk Panel (compliance focus)
    ArtifactType.KEY_TERMS_EXTRACT: ArtifactPlacement.RISK_PANEL,
    ArtifactType.TERM_VALIDATION_REPORT: ArtifactPlacement.RISK_PANEL,
    ArtifactType.CONTRACT_HANDOFF_PACKET: ArtifactPlacement.DECISION_CONSOLE,
    
    # Implementation Agent outputs -> Timeline
    ArtifactType.IMPLEMENTATION_CHECKLIST: ArtifactPlacement.TIMELINE,
    ArtifactType.EARLY_INDICATORS_REPORT: ArtifactPlacement.RISK_PANEL,
    ArtifactType.VALUE_CAPTURE_TEMPLATE: ArtifactPlacement.DECISION_CONSOLE,
    
    # Supervisor outputs
    ArtifactType.STATUS_SUMMARY: ArtifactPlacement.CASE_SUMMARY,
    ArtifactType.NEXT_BEST_ACTIONS: ArtifactPlacement.DECISION_CONSOLE,
}


def get_artifact_placement(artifact_type: str) -> ArtifactPlacement:
    """
    Get the UI placement section for an artifact type.
    
    Args:
        artifact_type: The artifact type string (e.g., "SIGNAL_REPORT")
        
    Returns:
        ArtifactPlacement enum indicating where to display the artifact.
        Defaults to ACTIVITY_LOG with a warning if type is unknown.
    """
    try:
        # Convert string to enum if needed
        if isinstance(artifact_type, str):
            artifact_type_enum = ArtifactType(artifact_type)
        else:
            artifact_type_enum = artifact_type
            
        placement = ARTIFACT_PLACEMENT_MAP.get(artifact_type_enum)
        
        if placement is None:
            logger.warning(
                f"Unknown artifact type '{artifact_type}' - defaulting to activity_log. "
                f"Add this type to ARTIFACT_PLACEMENT_MAP in placement.py"
            )
            return ArtifactPlacement.ACTIVITY_LOG
            
        return placement
        
    except ValueError:
        logger.warning(
            f"Invalid artifact type '{artifact_type}' - defaulting to activity_log"
        )
        return ArtifactPlacement.ACTIVITY_LOG


def get_artifacts_by_placement(
    artifacts: list,
    placement: ArtifactPlacement
) -> list:
    """
    Filter artifacts to only those that belong in a specific UI section.
    
    Args:
        artifacts: List of artifact dicts or Artifact objects
        placement: The target placement section
        
    Returns:
        List of artifacts that should appear in the specified section.
    """
    result = []
    for artifact in artifacts:
        # Get type from dict or object
        if isinstance(artifact, dict):
            artifact_type = artifact.get("type", "")
        else:
            artifact_type = getattr(artifact, "type", "")
            
        if get_artifact_placement(artifact_type) == placement:
            result.append(artifact)
            
    return result


def validate_artifact_placement(artifact) -> tuple[bool, Optional[str]]:
    """
    Validate that an artifact has a valid placement.
    
    Returns:
        (is_valid, warning_message)
    """
    if isinstance(artifact, dict):
        artifact_type = artifact.get("type", "")
    else:
        artifact_type = getattr(artifact, "type", "")
        
    if not artifact_type:
        return False, "Artifact missing 'type' field"
        
    try:
        ArtifactType(artifact_type)
        if artifact_type not in [t.value for t in ARTIFACT_PLACEMENT_MAP.keys()]:
            return True, f"Artifact type '{artifact_type}' not in placement map - will use default"
        return True, None
    except ValueError:
        return False, f"Unknown artifact type: {artifact_type}"

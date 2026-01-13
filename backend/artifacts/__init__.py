"""
Artifacts module - Build and render DTP-aligned work products.

Artifacts are the tangible outputs of agent tasks:
- Scorecards, reports, checklists
- Drafts and templates
- Next best actions
"""
from backend.artifacts.builders import ArtifactBuilder, build_artifact_pack
from backend.artifacts.utils import merge_grounding, generate_artifact_id

__all__ = [
    "ArtifactBuilder",
    "build_artifact_pack",
    "merge_grounding",
    "generate_artifact_id",
]





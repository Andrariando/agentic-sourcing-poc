"""
Artifact utilities - grounding merge, stable IDs, etc.
"""
from typing import List, Dict, Any
from uuid import uuid4
from datetime import datetime

from shared.schemas import GroundingReference


def generate_artifact_id(artifact_type: str) -> str:
    """Generate a stable, unique artifact ID."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid4().hex[:8]
    return f"ART-{artifact_type[:4].upper()}-{timestamp}-{short_uuid}"


def generate_pack_id() -> str:
    """Generate a unique artifact pack ID."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid4().hex[:8]
    return f"PACK-{timestamp}-{short_uuid}"


def merge_grounding(sources: List[List[GroundingReference]]) -> List[GroundingReference]:
    """
    Merge grounding references from multiple sources, deduplicating by ref_id.
    
    Args:
        sources: List of grounding reference lists
        
    Returns:
        Deduplicated, merged list of grounding references
    """
    seen_ids = set()
    merged = []
    
    for source in sources:
        for ref in source:
            if ref.ref_id not in seen_ids:
                seen_ids.add(ref.ref_id)
                merged.append(ref)
    
    return merged


def determine_verification_status(grounded_in: List[GroundingReference]) -> str:
    """
    Determine verification status based on grounding.
    
    Rules:
    - VERIFIED: Has at least 2 grounding references
    - PARTIAL: Has 1 grounding reference
    - UNVERIFIED: No grounding references
    """
    if len(grounded_in) >= 2:
        return "VERIFIED"
    elif len(grounded_in) == 1:
        return "PARTIAL"
    else:
        return "UNVERIFIED"


def format_grounding_for_display(grounded_in: List[GroundingReference]) -> List[Dict[str, str]]:
    """Format grounding references for UI display."""
    return [
        {
            "id": ref.ref_id,
            "type": ref.ref_type,
            "source": ref.source_name,
            "excerpt": ref.excerpt[:100] + "..." if ref.excerpt and len(ref.excerpt) > 100 else (ref.excerpt or ""),
        }
        for ref in grounded_in
    ]




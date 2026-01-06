"""
Tests for artifact placement - ensure artifacts route to correct UI sections.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from backend.artifacts.placement import (
    get_artifact_placement,
    get_artifacts_by_placement,
    validate_artifact_placement,
    ArtifactPlacement,
    ARTIFACT_PLACEMENT_MAP
)
from shared.constants import ArtifactType


class TestArtifactPlacement:
    """Test artifact type to UI section routing."""
    
    def test_signal_report_goes_to_decision_console(self):
        """Signal reports should appear in decision console."""
        placement = get_artifact_placement(ArtifactType.SIGNAL_REPORT.value)
        assert placement == ArtifactPlacement.DECISION_CONSOLE
    
    def test_supplier_shortlist_goes_to_supplier_compare(self):
        """Supplier shortlist should appear in supplier compare section."""
        placement = get_artifact_placement(ArtifactType.SUPPLIER_SHORTLIST.value)
        assert placement == ArtifactPlacement.SUPPLIER_COMPARE
    
    def test_key_terms_extract_goes_to_risk_panel(self):
        """Contract terms should appear in risk panel for compliance review."""
        placement = get_artifact_placement(ArtifactType.KEY_TERMS_EXTRACT.value)
        assert placement == ArtifactPlacement.RISK_PANEL
    
    def test_implementation_checklist_goes_to_timeline(self):
        """Implementation checklist should appear in timeline."""
        placement = get_artifact_placement(ArtifactType.IMPLEMENTATION_CHECKLIST.value)
        assert placement == ArtifactPlacement.TIMELINE
    
    def test_unknown_type_defaults_to_activity_log(self):
        """Unknown artifact types should default to activity log with warning."""
        placement = get_artifact_placement("UNKNOWN_TYPE")
        assert placement == ArtifactPlacement.ACTIVITY_LOG
    
    def test_all_artifact_types_have_placement(self):
        """All defined ArtifactType values should have a placement mapping."""
        unmapped = []
        for artifact_type in ArtifactType:
            if artifact_type not in ARTIFACT_PLACEMENT_MAP:
                unmapped.append(artifact_type.value)
        
        assert len(unmapped) == 0, f"These artifact types lack placement mapping: {unmapped}"


class TestArtifactFiltering:
    """Test filtering artifacts by placement."""
    
    def test_filter_artifacts_by_decision_console(self):
        """Should correctly filter artifacts for decision console."""
        artifacts = [
            {"type": "SIGNAL_REPORT", "title": "Signals"},
            {"type": "SUPPLIER_SHORTLIST", "title": "Suppliers"},
            {"type": "NEGOTIATION_PLAN", "title": "Negotiation"},
        ]
        
        decision_artifacts = get_artifacts_by_placement(
            artifacts, ArtifactPlacement.DECISION_CONSOLE
        )
        
        # SIGNAL_REPORT and NEGOTIATION_PLAN go to decision console
        assert len(decision_artifacts) == 2
        titles = [a["title"] for a in decision_artifacts]
        assert "Signals" in titles
        assert "Negotiation" in titles
        assert "Suppliers" not in titles
    
    def test_filter_artifacts_by_supplier_compare(self):
        """Should correctly filter artifacts for supplier compare."""
        artifacts = [
            {"type": "SIGNAL_REPORT", "title": "Signals"},
            {"type": "SUPPLIER_SHORTLIST", "title": "Suppliers"},
            {"type": "SUPPLIER_SCORECARD", "title": "Scorecard"},
        ]
        
        supplier_artifacts = get_artifacts_by_placement(
            artifacts, ArtifactPlacement.SUPPLIER_COMPARE
        )
        
        assert len(supplier_artifacts) == 2
        titles = [a["title"] for a in supplier_artifacts]
        assert "Suppliers" in titles
        assert "Scorecard" in titles


class TestArtifactValidation:
    """Test artifact validation."""
    
    def test_valid_artifact_passes(self):
        """Valid artifact should pass validation."""
        artifact = {"type": "SIGNAL_REPORT", "title": "Test"}
        is_valid, warning = validate_artifact_placement(artifact)
        
        assert is_valid
        assert warning is None
    
    def test_missing_type_fails(self):
        """Artifact without type should fail validation."""
        artifact = {"title": "Test"}
        is_valid, warning = validate_artifact_placement(artifact)
        
        assert not is_valid
        assert "missing 'type'" in warning.lower()
    
    def test_unknown_type_returns_warning(self):
        """Unknown type should pass but return warning."""
        artifact = {"type": "CUSTOM_TYPE_XYZ", "title": "Test"}
        is_valid, warning = validate_artifact_placement(artifact)
        
        # Should be invalid due to unknown enum value
        assert not is_valid or warning is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

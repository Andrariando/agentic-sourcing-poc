"""Unit tests for artifact Word/PDF export."""
from shared.schemas import Artifact
from shared.constants import ArtifactType


def test_iter_export_sections_rfx_draft_pack():
    from backend.services.artifact_document_export import iter_export_sections

    a = Artifact(
        artifact_id="a1",
        type=ArtifactType.RFX_DRAFT_PACK.value,
        title="RFP Draft Document",
        content={
            "rfx_type": "RFP",
            "completeness_score": 80,
            "is_complete": False,
            "sections": [
                {"section": "Executive Summary", "content": "Intro text", "status": "draft"},
            ],
        },
        content_text="summary",
        created_at="2026-01-01T00:00:00",
        created_by_agent="RFxDraft",
    )
    blocks = iter_export_sections(a)
    titles = [b[0] for b in blocks]
    assert "Overview" in titles
    assert "Executive Summary" in titles


def test_build_docx_is_zip():
    from backend.services.artifact_document_export import build_artifact_docx_bytes

    a = Artifact(
        artifact_id="a1",
        type=ArtifactType.STRATEGY_RECOMMENDATION.value,
        title="Strategy",
        content={"recommendation": "Run RFx"},
        content_text="We recommend competitive bidding.",
        created_at="2026-01-01T00:00:00",
        created_by_agent="Strategy",
    )
    raw = build_artifact_docx_bytes(a, "CASE-001", "Demo Case")
    assert raw[:2] == b"PK"


def test_build_pdf_bytes():
    from backend.services.artifact_document_export import build_artifact_pdf_bytes

    a = Artifact(
        artifact_id="a2",
        type=ArtifactType.NEGOTIATION_PLAN.value,
        title="Plan",
        content={},
        content_text="Opening position: start with target discount range.",
        created_at="2026-01-01T00:00:00",
        created_by_agent="Negotiation",
    )
    raw = build_artifact_pdf_bytes(a, "CASE-002", "Case")
    assert raw.startswith(b"%PDF")

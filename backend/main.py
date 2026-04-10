"""
FastAPI backend for Agentic Sourcing System.

This is the ONLY entry point for the frontend.
All business logic, agents, and data access go through this API.
"""
import os
import json
import base64
from io import BytesIO
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import services
from backend.services.case_service import get_case_service
from backend.services.artifact_document_export import (
    build_artifact_docx_bytes,
    build_artifact_pdf_bytes,
    build_artifact_pack_docx_bytes,
    build_artifact_pack_markdown_bytes,
    build_artifact_pack_pdf_bytes,
    build_plain_text_docx_bytes,
    export_filename,
    export_pack_filename,
    export_working_doc_filename,
)
from backend.services.docx_text import extract_text_from_docx_bytes
from backend.services.working_document_revision import revise_working_document_text
from backend.services.chat_service import get_chat_service
from backend.services.ingestion_service import get_ingestion_service
from backend.persistence.models import CaseState, S2CProcuraBotFeedback, DocumentRecord, ArtifactPack
from backend.infrastructure.storage_providers import initialize_storage_backends, get_app_db
from sqlmodel import select, func

# Import shared schemas
from shared.schemas import (
    CaseListResponse, CaseDetail, CreateCaseRequest, CreateCaseResponse,
    ChatRequest, ChatResponse,
    DecisionRequest, DecisionResponse,
    DocumentIngestResponse, DocumentListResponse,
    DataIngestResponse, DataPreviewResponse,
    HealthCheckResponse,
    SupplierPoolResponse,
    WorkingDocumentReviseRequest,
    WorkingDocumentReviseResponse,
)
from backend.services.supplier_pool import get_category_supplier_pool
from shared.constants import DocumentType, DataType


def _infer_working_document_role(filename: str) -> str:
    """Best-effort role inference for uploaded .docx files."""
    name = (filename or "").lower()
    if any(k in name for k in ("contract", "msa", "sow", "agreement")):
        return "contract"
    if any(k in name for k in ("rfx", "rfp", "tender", "proposal")):
        return "rfx"
    return "rfx"


def _image_mime_from_ext(ext: str) -> Optional[str]:
    ext = (ext or "").lower()
    if ext == ".png":
        return "image/png"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return None


def _summarize_image_for_chat(
    *,
    filename: str,
    content: bytes,
    user_message: str,
) -> Optional[str]:
    """
    Use a vision-capable OpenAI model to extract useful context from an image.
    Returns a short textual summary or None when unavailable.
    """
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    ext = os.path.splitext(filename)[1].lower()
    mime = _image_mime_from_ext(ext)
    if not mime:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    b64 = base64.b64encode(content).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    prompt = (
        "You are extracting business-relevant details from an uploaded image for a sourcing copilot. "
        "Summarize key facts, numbers, entities, and risks in 4-7 bullet points. "
        "If text in the image is unclear, say so briefly."
    )
    if (user_message or "").strip():
        prompt += f"\n\nUser question/context: {user_message.strip()}"

    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.2,
            max_tokens=350,
        )
        txt = (resp.choices[0].message.content or "").strip()
        return txt or None
    except Exception:
        return None


# Initialize database on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    initialize_storage_backends()
    print("[OK] Storage backends initialized")
    yield
    # Shutdown
    print("[INFO] Shutting down")


from fastapi.middleware.gzip import GZipMiddleware

# Create FastAPI app
app = FastAPI(
    title="Agentic Sourcing API",
    description="Backend API for the Agentic Sourcing ProcuraBot",
    version="1.0.0",
    lifespan=lifespan
)

# Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.heatmap.heatmap_router import heatmap_router
app.include_router(heatmap_router, prefix="/api/heatmap", tags=["heatmap"])


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        components={
            "database": "ok",
            "vector_store": "ok",
            "agents": "ok"
        }
    )


# ============================================================
# CASE ENDPOINTS
# ============================================================

@app.get("/api/cases", response_model=CaseListResponse)
async def list_cases(
    status: Optional[str] = None,
    dtp_stage: Optional[str] = None,
    category_id: Optional[str] = None,
    limit: int = 50
):
    """Get list of cases."""
    service = get_case_service()
    cases = service.list_cases(
        status=status,
        dtp_stage=dtp_stage,
        category_id=category_id,
        limit=limit
    )
    
    return CaseListResponse(
        cases=cases,
        total_count=len(cases),
        filters_applied={
            "status": status,
            "dtp_stage": dtp_stage,
            "category_id": category_id
        }
    )


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
async def get_case(case_id: str):
    """Get case details."""
    service = get_case_service()
    case = service.get_case(case_id)
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return case


@app.get("/api/cases/{case_id}/documents/center")
async def get_case_documents_center(case_id: str):
    """
    Unified document center for case UI:
    - uploads: files uploaded directly for this case
    - internal_references: relevant internal docs by category/supplier
    - generated_outputs: artifact pack summaries for this case
    """
    case_service = get_case_service()
    case = case_service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    session = get_app_db().get_db_session()
    try:
        # 1) Files uploaded for this case
        case_docs = session.exec(
            select(DocumentRecord).where(DocumentRecord.case_id == case_id)
        ).all()
        uploads = [
            {
                "id": d.document_id,
                "filename": d.filename,
                "file_type": d.file_type,
                "document_type": d.document_type,
                "source": "You",
                "updated_at": d.ingested_at,
                "category_id": d.category_id,
                "supplier_id": d.supplier_id,
            }
            for d in case_docs
        ]

        # 2) Internal references relevant by category/supplier (excluding case uploads)
        internal: List[DocumentRecord] = []
        if case.category_id or case.supplier_id:
            if case.category_id and case.supplier_id:
                stmt = select(DocumentRecord).where(
                    DocumentRecord.case_id != case_id,
                    (DocumentRecord.category_id == case.category_id)
                    | (DocumentRecord.supplier_id == case.supplier_id),
                )
                internal = session.exec(stmt).all()
            elif case.category_id:
                stmt = select(DocumentRecord).where(
                    DocumentRecord.case_id != case_id,
                    DocumentRecord.category_id == case.category_id,
                )
                internal = session.exec(stmt).all()
            else:
                stmt = select(DocumentRecord).where(
                    DocumentRecord.case_id != case_id,
                    DocumentRecord.supplier_id == case.supplier_id,
                )
                internal = session.exec(stmt).all()

        internal_references = [
            {
                "id": d.document_id,
                "filename": d.filename,
                "file_type": d.file_type,
                "document_type": d.document_type,
                "source": "Internal",
                "updated_at": d.ingested_at,
                "category_id": d.category_id,
                "supplier_id": d.supplier_id,
            }
            for d in internal[:20]
        ]

        # 3) Generated outputs from artifact packs
        packs = session.exec(
            select(ArtifactPack).where(ArtifactPack.case_id == case_id)
        ).all()
        generated_outputs = []
        for p in packs:
            artifact_ids = []
            if p.artifact_ids:
                try:
                    artifact_ids = json.loads(p.artifact_ids)
                except Exception:
                    artifact_ids = []
            generated_outputs.append(
                {
                    "id": p.pack_id,
                    "filename": f"{(p.agent_name or 'ProcuraBot').strip()} output bundle",
                    "file_type": "bundle",
                    "document_type": "Generated Output",
                    "source": "ProcuraBot",
                    "updated_at": p.created_at,
                    "artifact_count": len(artifact_ids) if isinstance(artifact_ids, list) else 0,
                    "pack_id": p.pack_id,
                    "agent_name": p.agent_name,
                }
            )

        uploads.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        internal_references.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        generated_outputs.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

        return {
            "uploads": uploads,
            "internal_references": internal_references,
            "generated_outputs": generated_outputs,
        }
    finally:
        session.close()


@app.get("/api/suppliers", response_model=SupplierPoolResponse)
async def list_suppliers_for_category(category_id: str = Query(..., description="Category id, e.g. CLOUD, TELECOM")):
    """Enterprise supplier catalog slice for a category (same data as ``CaseDetail.category_supplier_pool``)."""
    cid = (category_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="category_id is required")
    rows = get_category_supplier_pool(cid)
    return SupplierPoolResponse(category_id=cid, suppliers=rows, total_count=len(rows))


class S2CProcuraBotFeedbackRequest(BaseModel):
    vote: str  # up | down
    assistant_message: str
    user_id: Optional[str] = "human-user"


@app.post("/api/cases/{case_id}/copilot/feedback")
async def submit_s2c_copilot_feedback(case_id: str, body: S2CProcuraBotFeedbackRequest):
    vote = (body.vote or "").strip().lower()
    if vote not in ("up", "down"):
        raise HTTPException(status_code=400, detail="vote must be 'up' or 'down'")
    msg = (body.assistant_message or "").strip()
    if len(msg) < 3:
        raise HTTPException(status_code=400, detail="assistant_message is required")
    session = get_app_db().get_db_session()
    try:
        case_exists = session.exec(
            select(CaseState.case_id).where(CaseState.case_id == case_id)
        ).first()
        if not case_exists:
            raise HTTPException(status_code=404, detail="Case not found")
        row = S2CProcuraBotFeedback(
            case_id=case_id,
            vote=vote,
            assistant_message=msg[:20000],
            user_id=(body.user_id or "human-user").strip() or "human-user",
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"success": True, "feedback_id": row.id}
    finally:
        session.close()


@app.get("/api/s2c/performance/metrics")
async def get_s2c_performance_metrics():
    """
    S2C performance metrics:
    - overall: avg AI reliability + signal attribution accuracy (thumbs up / total)
    - detailed: per-case reliability based on human change events
    """
    session = get_app_db().get_db_session()
    try:
        case_rows = session.exec(select(CaseState)).all()
        feedback_rows = session.exec(
            select(S2CProcuraBotFeedback.vote, func.count(S2CProcuraBotFeedback.id)).group_by(
                S2CProcuraBotFeedback.vote
            )
        ).all()
        thumbs = {str(v): int(n) for v, n in feedback_rows}
        thumbs_total = int(sum(thumbs.values()))
        thumbs_up = int(thumbs.get("up", 0))
        signal_acc = (thumbs_up / thumbs_total * 100.0) if thumbs_total else None

        detailed: List[dict] = []
        reliability_vals: List[float] = []
        for c in case_rows:
            try:
                act = json.loads(c.activity_log) if c.activity_log else []
            except json.JSONDecodeError:
                act = []
            human_changes = 0
            for e in act if isinstance(act, list) else []:
                if not isinstance(e, dict):
                    continue
                an = str(e.get("agent_name", "")).lower()
                tn = str(e.get("task_name", "")).lower()
                out = str(e.get("output_summary", "")).lower()
                if ("human" in an or "user" in an) and "decision" in tn:
                    human_changes += 1
                elif "reject" in out or "revision" in out:
                    human_changes += 1
            reliability = max(50.0, min(99.0, 100.0 - min(human_changes, 10) * 5.0))
            reliability_vals.append(reliability)
            detailed.append(
                {
                    "case_id": c.case_id,
                    "name": c.name,
                    "dtp_stage": c.dtp_stage,
                    "status": c.status,
                    "ai_reliability_pct": round(reliability, 1),
                    "human_change_count": int(human_changes),
                }
            )

        overall_reliability = (
            round(sum(reliability_vals) / len(reliability_vals), 1)
            if reliability_vals
            else None
        )

        return {
            "overall": {
                "ai_reliability_score_pct": overall_reliability,
                "signal_attribution_accuracy_pct": round(signal_acc, 2)
                if signal_acc is not None
                else None,
                "thumbs_up": thumbs_up,
                "thumbs_down": int(thumbs.get("down", 0)),
                "thumbs_total": thumbs_total,
            },
            "detailed": detailed,
        }
    finally:
        session.close()


@app.get("/api/cases/{case_id}/artifacts/{artifact_id}/export")
async def export_artifact_document(
    case_id: str,
    artifact_id: str,
    export_format: str = Query("docx", description="Export format: docx or pdf"),
):
    """
    Download a single artifact as Word (.docx) or PDF.

    Works for RFx packs (structured sections), other agent artifacts (summary + JSON),
    and any stored `Artifact` row.
    """
    fmt = (export_format or "docx").lower().strip()
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="export_format must be docx or pdf")

    service = get_case_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    artifact = service.get_artifact(case_id, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        if fmt == "docx":
            data = build_artifact_docx_bytes(artifact, case_id, case.name or case_id)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            fname = export_filename(artifact, "docx")
        else:
            data = build_artifact_pdf_bytes(artifact, case_id, case.name or case_id)
            media = "application/pdf"
            fname = export_filename(artifact, "pdf")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return StreamingResponse(
        BytesIO(data),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.get("/api/cases/{case_id}/artifact-packs/{pack_id}/export")
async def export_artifact_pack_document(
    case_id: str,
    pack_id: str,
    export_format: str = Query(
        "md",
        description="Export format: md (Markdown), docx, or pdf (full pack: all artifacts + next actions / risks)",
    ),
):
    """
    Download an entire artifact pack as Markdown, Word, or PDF.

    Bundles every artifact in the pack (RFx sections, strategy summaries, etc.) into one file.
    """
    fmt = (export_format or "md").lower().strip()
    if fmt not in ("md", "docx", "pdf", "markdown"):
        raise HTTPException(
            status_code=400,
            detail="export_format must be md, docx, or pdf",
        )
    if fmt == "markdown":
        fmt = "md"

    service = get_case_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pack = service.get_artifact_pack_for_case(case_id, pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Artifact pack not found for this case")

    try:
        if fmt == "md":
            data = build_artifact_pack_markdown_bytes(
                pack, case_id, case.name or case_id
            )
            media = "text/markdown; charset=utf-8"
            fname = export_pack_filename(pack, "md")
        elif fmt == "docx":
            data = build_artifact_pack_docx_bytes(
                pack, case_id, case.name or case_id
            )
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            fname = export_pack_filename(pack, "docx")
        else:
            data = build_artifact_pack_pdf_bytes(
                pack, case_id, case.name or case_id
            )
            media = "application/pdf"
            fname = export_pack_filename(pack, "pdf")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return StreamingResponse(
        BytesIO(data),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/api/cases/{case_id}/working-documents")
async def upload_working_document(
    case_id: str,
    role: str = Form(..., description="rfx or contract"),
    file: UploadFile = File(...),
):
    """
    Upload a .docx edited in Word; plain text is extracted and stored for copilot + export.
    """
    r = (role or "").lower().strip()
    if r not in ("rfx", "contract"):
        raise HTTPException(status_code=400, detail="role must be rfx or contract")
    fname = file.filename or "document.docx"
    if not fname.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported for this showcase")

    service = get_case_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    content = await file.read()
    try:
        plain = extract_text_from_docx_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read Word file: {e}") from e

    ok = service.upsert_working_document_slot(
        case_id, r, plain, fname, "user_upload"
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save working document")

    return {
        "success": True,
        "role": r,
        "chars": len(plain),
        "source_filename": fname,
        "message": "Draft stored. ProcuraBot can now reference it; download Word anytime.",
    }


@app.post("/api/cases/{case_id}/working-documents/revise", response_model=WorkingDocumentReviseResponse)
async def revise_working_document_endpoint(
    case_id: str,
    body: WorkingDocumentReviseRequest,
):
    """
    Apply a full-document ProcuraBot rewrite (LLM) to the stored RFX or contract plain text.
    """
    r = (body.role or "").lower().strip()
    if r not in ("rfx", "contract"):
        raise HTTPException(status_code=400, detail="role must be rfx or contract")

    service = get_case_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    wd = case.working_documents
    slot = None
    if wd:
        slot = wd.rfx if r == "rfx" else wd.contract
    current = (slot.plain_text if slot else "") or ""
    if not current.strip():
        raise HTTPException(
            status_code=400,
            detail="No draft text for this slot. Upload a .docx first or paste content via API.",
        )

    revised = revise_working_document_text(
        role=r,
        current_text=current,
        instruction=body.instruction,
        case_name=case.name or case_id,
        category_id=case.category_id,
        dtp_stage=case.dtp_stage,
    )
    if not revised:
        raise HTTPException(
            status_code=503,
            detail="Revision unavailable (check OPENAI_API_KEY or try again).",
        )

    ok = service.upsert_working_document_slot(
        case_id, r, revised, slot.source_filename if slot else None, "copilot"
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save revised draft")

    return WorkingDocumentReviseResponse(
        success=True,
        role=r,
        message="Draft updated. Download Word or keep chatting.",
        chars=len(revised),
    )


@app.get("/api/cases/{case_id}/working-documents/{role}/export")
async def export_working_document_word(
    case_id: str,
    role: str,
):
    """Download the stored plain-text draft as a .docx (open/edit again in Word)."""
    r = (role or "").lower().strip()
    if r not in ("rfx", "contract"):
        raise HTTPException(status_code=400, detail="role must be rfx or contract")

    service = get_case_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    wd = case.working_documents
    slot = wd.rfx if r == "rfx" else (wd.contract if wd else None)
    if not slot or not (slot.plain_text or "").strip():
        raise HTTPException(status_code=404, detail="No saved draft for this slot")

    title = "RFx draft (working copy)" if r == "rfx" else "Contract draft (working copy)"
    data = build_plain_text_docx_bytes(
        title, slot.plain_text, case_id, case.name or case_id
    )
    fname = export_working_doc_filename(r, "docx")
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/api/cases", response_model=CreateCaseResponse)
async def create_case(request: CreateCaseRequest):
    """Create a new case."""
    service = get_case_service()
    
    case_id = service.create_case(
        category_id=request.category_id,
        trigger_source=request.trigger_source,
        contract_id=request.contract_id,
        supplier_id=request.supplier_id,
        name=request.name
    )
    
    return CreateCaseResponse(
        case_id=case_id,
        success=True,
        message=f"Case {case_id} created successfully"
    )


# ============================================================
# CHAT / COPILOT ENDPOINTS
# ============================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process chat message with Supervisor governance.
    
    This is the main copilot endpoint.
    All messages go through the Supervisor for:
    - Intent classification
    - Action validation
    - Agent routing
    - Human approval enforcement
    """
    service = get_chat_service()
    
    response = service.process_message(
        case_id=request.case_id,
        user_message=request.user_message,
        use_tier_2=request.use_tier_2
    )
    
    return response


@app.post("/api/chat/with-attachments", response_model=ChatResponse)
async def chat_with_attachments(
    case_id: str = Form(...),
    user_message: str = Form(""),
    use_tier_2: bool = Form(True),
    files: List[UploadFile] = File(default_factory=list),
):
    """
    Chat endpoint that accepts files in the same submit action (multipart/form-data).

    Behavior:
    - .docx: saved as working document slot (role inferred from filename)
    - .pdf/.txt/.csv/.xlsx/.xls: ingested for retrieval context
    - images (.png/.jpg/.jpeg/.webp/.gif): summarized with vision model when available
    - unsupported types are skipped (chat still proceeds)
    """
    msg = (user_message or "").strip()
    if not msg and not files:
        raise HTTPException(status_code=400, detail="Provide a message or at least one file.")

    case_service = get_case_service()
    case = case_service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    ingestion_service = get_ingestion_service()
    uploaded_names: List[str] = []
    skipped_names: List[str] = []
    image_notes: List[str] = []

    for f in files:
        filename = (f.filename or "").strip()
        if not filename:
            continue
        ext = os.path.splitext(filename)[1].lower()
        content = await f.read()
        if not content:
            continue

        if ext == ".docx":
            try:
                role = _infer_working_document_role(filename)
                plain = extract_text_from_docx_bytes(content)
                ok = case_service.upsert_working_document_slot(
                    case_id, role, plain, filename, "chat_upload"
                )
                if ok:
                    uploaded_names.append(filename)
                else:
                    skipped_names.append(filename)
            except Exception:
                skipped_names.append(filename)
            continue

        if ext in (".pdf", ".txt", ".csv", ".xlsx", ".xls"):
            try:
                r = ingestion_service.ingest_document(
                    file_content=content,
                    filename=filename,
                    document_type=DocumentType.OTHER.value,
                    case_id=case_id,
                    description="Uploaded in chat composer",
                )
                if r.success:
                    uploaded_names.append(filename)
                else:
                    skipped_names.append(filename)
            except Exception:
                skipped_names.append(filename)
            continue

        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            note = _summarize_image_for_chat(
                filename=filename,
                content=content,
                user_message=msg,
            )
            if note:
                uploaded_names.append(filename)
                image_notes.append(f"Image summary for {filename}:\n{note}")
            else:
                skipped_names.append(filename)
            continue

        skipped_names.append(filename)

    augmented_msg = msg
    if uploaded_names:
        upload_summary = ", ".join(uploaded_names[:8])
        summary_line = f"I uploaded these files for context: {upload_summary}."
        augmented_msg = f"{augmented_msg}\n\n{summary_line}" if augmented_msg else summary_line
    if skipped_names:
        skipped_summary = ", ".join(skipped_names[:6])
        skip_line = (
            f"Note: some files were skipped because their type is not supported yet: {skipped_summary}."
        )
        augmented_msg = f"{augmented_msg}\n\n{skip_line}" if augmented_msg else skip_line
    if image_notes:
        img_line = "\n\n".join(image_notes[:3])
        augmented_msg = f"{augmented_msg}\n\n{img_line}" if augmented_msg else img_line

    service = get_chat_service()
    response = service.process_message(
        case_id=case_id,
        user_message=augmented_msg,
        use_tier_2=use_tier_2,
    )
    return response


# ============================================================
# DECISION ENDPOINTS
# ============================================================

@app.post("/api/decisions/approve", response_model=DecisionResponse)
async def approve_decision(request: DecisionRequest):
    """Approve a pending decision."""
    service = get_chat_service()
    
    result = service.process_decision(
        case_id=request.case_id,
        decision="Approve",
        reason=request.reason,
        edited_fields=request.edited_fields,
        decision_data=request.decision_data
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return DecisionResponse(
        case_id=request.case_id,
        decision="Approve",
        success=True,
        new_dtp_stage=result.get("new_dtp_stage"),
        message=result["message"]
    )


@app.post("/api/decisions/reject", response_model=DecisionResponse)
async def reject_decision(request: DecisionRequest):
    """Reject a pending decision."""
    service = get_chat_service()
    
    result = service.process_decision(
        case_id=request.case_id,
        decision="Reject",
        reason=request.reason
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return DecisionResponse(
        case_id=request.case_id,
        decision="Reject",
        success=True,
        new_dtp_stage=result.get("new_dtp_stage"),
        message=result["message"]
    )


# ============================================================
# DOCUMENT INGESTION ENDPOINTS
# ============================================================

@app.post("/api/ingest/document", response_model=DocumentIngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    supplier_id: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    region: Optional[str] = Form(None),
    dtp_relevance: Optional[str] = Form(None),  # JSON string
    case_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Ingest a document for RAG.
    
    Accepts: PDF, DOCX, TXT
    """
    # Validate file type
    allowed_types = [".pdf", ".docx", ".txt"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {allowed_types}"
        )
    
    # Parse DTP relevance
    dtp_list = []
    if dtp_relevance:
        try:
            import json
            dtp_list = json.loads(dtp_relevance)
        except:
            dtp_list = [dtp_relevance]
    
    # Read file content
    content = await file.read()
    
    # Ingest
    service = get_ingestion_service()
    result = service.ingest_document(
        file_content=content,
        filename=file.filename,
        document_type=document_type,
        supplier_id=supplier_id,
        category_id=category_id,
        region=region,
        dtp_relevance=dtp_list,
        case_id=case_id,
        description=description
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return result


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    supplier_id: Optional[str] = None,
    category_id: Optional[str] = None,
    document_type: Optional[str] = None
):
    """List ingested documents."""
    service = get_ingestion_service()
    return service.list_documents(
        supplier_id=supplier_id,
        category_id=category_id,
        document_type=document_type
    )


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document."""
    service = get_ingestion_service()
    success = service.delete_document(document_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"success": True, "message": f"Document {document_id} deleted"}


# ============================================================
# STRUCTURED DATA INGESTION ENDPOINTS
# ============================================================

@app.post("/api/ingest/data/preview", response_model=DataPreviewResponse)
async def preview_data(
    file: UploadFile = File(...),
    data_type: str = Form(...)
):
    """Preview data before ingestion."""
    allowed_types = [".csv", ".xls", ".xlsx"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {allowed_types}"
        )
    
    content = await file.read()
    
    service = get_ingestion_service()
    return service.preview_data(
        file_content=content,
        filename=file.filename,
        data_type=data_type
    )


@app.post("/api/ingest/data", response_model=DataIngestResponse)
async def ingest_data(
    file: UploadFile = File(...),
    data_type: str = Form(...),
    supplier_id: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    time_period: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """Ingest structured data (CSV/Excel)."""
    allowed_types = [".csv", ".xls", ".xlsx"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {allowed_types}"
        )
    
    content = await file.read()
    
    service = get_ingestion_service()
    result = service.ingest_data(
        file_content=content,
        filename=file.filename,
        data_type=data_type,
        supplier_id=supplier_id,
        category_id=category_id,
        time_period=time_period,
        description=description
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return result


@app.get("/api/ingest/history")
async def get_ingestion_history(
    data_type: Optional[str] = None,
    limit: int = 50
):
    """Get ingestion history."""
    service = get_ingestion_service()
    history = service.get_ingestion_history(data_type=data_type, limit=limit)
    return {"history": history, "count": len(history)}


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)








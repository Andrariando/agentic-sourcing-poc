"""
FastAPI backend for Agentic Sourcing System.

This is the ONLY entry point for the frontend.
All business logic, agents, and data access go through this API.
"""
import os
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
from backend.persistence.database import init_db

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


# Initialize database on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    init_db()
    print("[OK] Database initialized")
    yield
    # Shutdown
    print("[INFO] Shutting down")


from fastapi.middleware.gzip import GZipMiddleware

# Create FastAPI app
app = FastAPI(
    title="Agentic Sourcing API",
    description="Backend API for the Agentic Sourcing Copilot",
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


@app.get("/api/suppliers", response_model=SupplierPoolResponse)
async def list_suppliers_for_category(category_id: str = Query(..., description="Category id, e.g. CLOUD, TELECOM")):
    """Enterprise supplier catalog slice for a category (same data as ``CaseDetail.category_supplier_pool``)."""
    cid = (category_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="category_id is required")
    rows = get_category_supplier_pool(cid)
    return SupplierPoolResponse(category_id=cid, suppliers=rows, total_count=len(rows))


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
        "message": "Draft stored. Copilot can now reference it; download Word anytime.",
    }


@app.post("/api/cases/{case_id}/working-documents/revise", response_model=WorkingDocumentReviseResponse)
async def revise_working_document_endpoint(
    case_id: str,
    body: WorkingDocumentReviseRequest,
):
    """
    Apply a full-document Copilot rewrite (LLM) to the stored RFX or contract plain text.
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








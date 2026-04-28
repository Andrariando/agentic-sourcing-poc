"""
FastAPI backend for Agentic Sourcing System.

This is the ONLY entry point for the frontend.
All business logic, agents, and data access go through this API.
"""
import os
import json
import base64
import io
import re
from io import BytesIO
from typing import Optional, List, Dict, Any, Literal, Tuple
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from uuid import uuid4
import threading

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from backend.services.llm_provider import get_openai_client, resolve_chat_model, using_azure_openai, has_llm_credentials

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
from backend.infrastructure.storage_providers import initialize_storage_backends, get_app_db, get_heatmap_db
from sqlmodel import select, func, delete

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
    client = get_openai_client()
    if not client:
        return None
    ext = os.path.splitext(filename)[1].lower()
    mime = _image_mime_from_ext(ext)
    if not mime:
        return None

    b64 = base64.b64encode(content).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    default_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    model = resolve_chat_model(default_model, deployment_env="AZURE_OPENAI_VISION_DEPLOYMENT")
    prompt = (
        "You are extracting business-relevant details from an uploaded image for a sourcing copilot. "
        "Summarize key facts, numbers, entities, and risks in 4-7 bullet points. "
        "If text in the image is unclear, say so briefly."
    )
    if (user_message or "").strip():
        prompt += f"\n\nUser question/context: {user_message.strip()}"

    try:
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

from backend.heatmap.heatmap_router import heatmap_router, _start_heatmap_pipeline_background
from backend.heatmap.persistence.heatmap_models import Opportunity, ReviewFeedback, AuditLog
from backend.heatmap.services.system1_scoring_orchestrator import (
    enrich_rows_for_preview,
    summarize_preview_completeness,
)
from backend.heatmap.services.system1_flexible_ingestion import (
    ErpJsonAdapter,
    StructuredFileAdapter,
)
from backend.heatmap.services.system1_ingestion_graph import get_system1_ingestion_graph
app.include_router(heatmap_router, prefix="/api/heatmap", tags=["heatmap"])


ALLOWED_SYSTEM1_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xls", ".xlsx"}
_system1_upload_jobs: Dict[str, Dict[str, Any]] = {}
_system1_upload_lock = threading.Lock()
_SYSTEM1_UPLOAD_FILES_DIR = os.path.join(os.path.dirname(__file__), "data", "system1_uploads")
os.makedirs(_SYSTEM1_UPLOAD_FILES_DIR, exist_ok=True)


def _sanitize_uploaded_filename(filename: str) -> str:
    base = os.path.basename((filename or "").strip()) or "upload.bin"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return cleaned or "upload.bin"


def _persist_system1_uploaded_file(raw: bytes, filename: str) -> Dict[str, Any]:
    safe_name = _sanitize_uploaded_filename(filename)
    stored_name = f"{uuid4().hex}_{safe_name}"
    abs_path = os.path.join(_SYSTEM1_UPLOAD_FILES_DIR, stored_name)
    with open(abs_path, "wb") as f:
        f.write(raw)
    return {
        "stored_name": stored_name,
        "original_filename": filename,
        "size_bytes": len(raw),
        "download_url": f"/api/system1/upload/files/{stored_name}",
    }
_SYSTEM1_TEMPLATES: Dict[str, str] = {
    "renewals_template.csv": (
        "row_type,category,subcategory,supplier_name,contract_id,contract_end_date,months_to_expiry,"
        "estimated_spend_usd,preferred_supplier_status,rss_score,scs_score,sas_score\n"
        "renewal,IT Infrastructure,Cloud Hosting,TechGlobal Inc,CNT-2026-100,2026-12-31,8,2500000,allowed,,,\n"
    ),
    "new_business_template.csv": (
        "row_type,category,subcategory,supplier_name,request_title,estimated_spend_usd,"
        "implementation_timeline_months,preferred_supplier_status\n"
        "new_business,Software,SaaS,WidgetCo,Enterprise SSO rollout,500000,5,preferred\n"
    ),
    "complete_dataset_template.csv": (
        "row_type,category,subcategory,supplier_name,contract_id,request_title,contract_end_date,months_to_expiry,"
        "estimated_spend_usd,implementation_timeline_months,preferred_supplier_status,rss_score,scs_score,sas_score\n"
        "renewal,IT Infrastructure,Cloud Hosting,TechGlobal Inc,CNT-2026-100,,2026-12-31,8,2500000,,allowed,6.4,7.8,8.5\n"
        "new_business,IT Infrastructure,Network Security,CyberShield LLC,,REQ-SEC-2026-12,,"
        "1200000,5,preferred,4.2,6.5,9.0\n"
    ),
}


class System1UploadPreviewRow(BaseModel):
    row_id: str
    row_type: Literal["renewal", "new_business"]
    source_filename: str
    source_kind: Literal["structured", "document"]
    confidence: float = 0.7
    category: str
    subcategory: Optional[str] = None
    supplier_name: Optional[str] = None
    contract_id: Optional[str] = None
    request_title: Optional[str] = None
    contract_end_date: Optional[datetime] = None
    estimated_spend_usd: float = 0.0
    implementation_timeline_months: Optional[float] = None
    months_to_expiry: Optional[float] = None
    preferred_supplier_status: Optional[str] = None
    rss_score: Optional[float] = None
    scs_score: Optional[float] = None
    sas_score: Optional[float] = None
    score_components: Dict[str, Any] = Field(default_factory=dict)
    weights_used: Dict[str, float] = Field(default_factory=dict)
    computed_total_score: Optional[float] = None
    computed_tier: Optional[str] = None
    computed_confidence: Optional[float] = None
    readiness_status: str = "ready"
    readiness_warnings: List[str] = Field(default_factory=list)
    recommended_action_window: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    valid_for_approval: bool = True
    completeness_score: float = 0.0
    defaulted_components: List[str] = Field(default_factory=list)
    low_confidence_components: List[str] = Field(default_factory=list)
    missing_critical_fields: List[str] = Field(default_factory=list)
    suggested_actions: List[Dict[str, str]] = Field(default_factory=list)


class System1UploadPreviewResponse(BaseModel):
    job_id: str
    status: str
    total_candidates: int
    valid_candidates: int
    candidates: List[System1UploadPreviewRow]
    parsing_notes: List[str] = Field(default_factory=list)
    analysis: Dict[str, Any] = Field(default_factory=dict)


class System1UploadRowOverride(BaseModel):
    """Optional human edits applied at approve time (merged onto preview rows)."""

    row_type: Optional[Literal["renewal", "new_business"]] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    supplier_name: Optional[str] = None
    contract_id: Optional[str] = None
    request_title: Optional[str] = None
    contract_end_date: Optional[str] = None
    estimated_spend_usd: Optional[float] = None
    implementation_timeline_months: Optional[float] = None
    months_to_expiry: Optional[float] = None
    preferred_supplier_status: Optional[str] = None
    rss_score: Optional[float] = None
    scs_score: Optional[float] = None
    sas_score: Optional[float] = None


class System1UploadApproveRequest(BaseModel):
    job_id: str
    approved_row_ids: List[str]
    approver_id: str = "human-user"
    row_overrides: Optional[Dict[str, System1UploadRowOverride]] = None
    acknowledge_warning_row_ids: List[str] = Field(default_factory=list)


class System1UploadApproveResponse(BaseModel):
    success: bool
    job_id: str
    approved_count: int
    created_opportunity_ids: List[int]
    run_triggered: bool
    message: str


class System1UploadJobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    total_candidates: int = 0
    approved_count: int = 0
    created_opportunity_ids: List[int] = Field(default_factory=list)
    run_triggered: bool = False
    parsing_notes: List[str] = Field(default_factory=list)
    warning_rows_count: int = 0


class System1UploadJobDeleteResponse(BaseModel):
    success: bool
    job_id: str
    removed: bool


class System1ActivePreviewSummaryResponse(BaseModel):
    job_id: Optional[str] = None
    status: str = "none"
    total_rows: int = 0
    covered_rows: int = 0
    ready_rows: int = 0
    ready_with_warnings_rows: int = 0
    needs_review_rows: int = 0


class System1ErpPreviewRequest(BaseModel):
    source_system: str = "erp"
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    mapping_profile: Optional[str] = "erp_generic"
    column_mapping: Optional[Dict[str, str]] = None
    top_n: Optional[int] = None
    rank_by: Optional[str] = "completeness"


def _safe_float(raw: Any, default: float = 0.0) -> float:
    try:
        if raw is None:
            return default
        txt = str(raw).strip().replace(",", "")
        for sym in ("$", "€", "£"):
            txt = txt.replace(sym, "")
        txt = txt.strip()
        if not txt:
            return default
        return float(txt)
    except Exception:
        return default


def _safe_opt_float(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    txt = str(raw).strip().replace(",", "")
    for sym in ("$", "€", "£"):
        txt = txt.replace(sym, "")
    txt = txt.strip()
    if not txt:
        return None
    try:
        return float(txt)
    except Exception:
        return None


def _safe_opt_datetime(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    txt = str(raw).strip()
    if not txt:
        return None
    # Accept common date forms from CSV/docs/UI overrides.
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(txt, fmt)
        except Exception:
            pass
    try:
        # ISO variants, incl trailing Z.
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(tz=None).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _months_to_expiry_from_contract_end(contract_end_date: Optional[datetime]) -> Optional[float]:
    if contract_end_date is None:
        return None
    now = datetime.utcnow()
    delta_days = (contract_end_date - now).total_seconds() / 86400.0
    return round(max(0.0, delta_days / 30.4375), 2)


def _normalize_type(raw: Any, contract_id: Optional[str]) -> str:
    txt = (str(raw or "")).strip().lower()
    # If source data explicitly declares row type, trust it.
    if txt in {"renewal", "new_business"}:
        return txt
    if contract_id:
        return "renewal"
    if "renew" in txt or txt in {"contract", "existing"}:
        return "renewal"
    return "new_business"


def _finalize_upload_preview_row(row: System1UploadPreviewRow) -> System1UploadPreviewRow:
    warnings: List[str] = []
    if row.estimated_spend_usd <= 0:
        warnings.append("Missing or non-positive spend")
    if row.row_type == "renewal" and row.months_to_expiry is None and row.contract_end_date is None:
        warnings.append("Renewal row missing months_to_expiry/contract_end_date (will default conservatively)")
    if row.row_type == "new_business" and row.implementation_timeline_months is None:
        warnings.append("New business row missing implementation_timeline_months (will default to 6)")
    if not (row.supplier_name or "").strip():
        warnings.append("Supplier name missing")
    valid = row.estimated_spend_usd > 0
    return row.model_copy(update={"warnings": warnings, "valid_for_approval": valid})


def _merge_system1_upload_row(
    base: System1UploadPreviewRow,
    override: Optional[System1UploadRowOverride],
) -> System1UploadPreviewRow:
    if not override:
        return _finalize_upload_preview_row(base)
    d = base.model_dump()
    for k, v in override.model_dump(exclude_none=True).items():
        d[k] = v
    d["category"] = _normalize_category(d.get("category"))
    cid = (str(d.get("contract_id") or "")).strip() or None
    d["contract_id"] = cid
    d["row_type"] = _normalize_type(d.get("row_type"), cid)
    d["estimated_spend_usd"] = round(_safe_float(d.get("estimated_spend_usd"), 0.0), 2)
    d["implementation_timeline_months"] = _safe_opt_float(d.get("implementation_timeline_months"))
    d["months_to_expiry"] = _safe_opt_float(d.get("months_to_expiry"))
    d["contract_end_date"] = _safe_opt_datetime(d.get("contract_end_date"))
    if d["months_to_expiry"] is None:
        d["months_to_expiry"] = _months_to_expiry_from_contract_end(d["contract_end_date"])
    for key in ("rss_score", "scs_score", "sas_score"):
        if d.get(key) is not None:
            d[key] = _safe_opt_float(d.get(key))
    if d.get("subcategory") is not None:
        d["subcategory"] = (str(d.get("subcategory") or "")).strip() or None
    if d.get("supplier_name") is not None:
        d["supplier_name"] = (str(d.get("supplier_name") or "")).strip() or None
    if d.get("request_title") is not None:
        d["request_title"] = (str(d.get("request_title") or "")).strip() or None
    if d.get("preferred_supplier_status") is not None:
        d["preferred_supplier_status"] = (str(d.get("preferred_supplier_status") or "")).strip() or None
    row = System1UploadPreviewRow(**d)
    return _finalize_upload_preview_row(row)


def _normalize_category(raw: Any) -> str:
    out = (str(raw or "")).strip()
    return out or "Uncategorized"


def _normalize_rank_by(raw: Optional[str]) -> str:
    v = str(raw or "completeness").strip().lower()
    if v in {"completeness", "score", "hybrid"}:
        return v
    return "completeness"


def _rank_candidates(candidates: List[Any], rank_by: str) -> List[Any]:
    rb = _normalize_rank_by(rank_by)
    if rb == "score":
        key_fn = lambda c: (
            float(getattr(c, "computed_total_score", None) or 0.0),
            float(getattr(c, "completeness_score", None) or 0.0),
            float(getattr(c, "computed_confidence", None) or 0.0),
            float(getattr(c, "estimated_spend_usd", None) or 0.0),
        )
    elif rb == "hybrid":
        key_fn = lambda c: (
            (0.6 * float(getattr(c, "completeness_score", None) or 0.0))
            + (0.3 * (10.0 * float(getattr(c, "computed_confidence", None) or 0.0)))
            + (0.1 * float(getattr(c, "computed_total_score", None) or 0.0)),
            float(getattr(c, "computed_total_score", None) or 0.0),
            float(getattr(c, "estimated_spend_usd", None) or 0.0),
        )
    else:
        key_fn = lambda c: (
            float(getattr(c, "completeness_score", None) or 0.0),
            float(getattr(c, "computed_confidence", None) or 0.0),
            float(getattr(c, "computed_total_score", None) or 0.0),
            float(getattr(c, "estimated_spend_usd", None) or 0.0),
        )
    return sorted(candidates, key=key_fn, reverse=True)


def _extract_text_for_upload(content: bytes, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in {".txt", ".csv"}:
        return content.decode("utf-8", errors="ignore")
    if ext == ".docx":
        try:
            return extract_text_from_docx_bytes(content)
        except Exception:
            return ""
    if ext == ".pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            pages = [p.extract_text() or "" for p in reader.pages]
            return "\n\n".join(pages).strip()
        except Exception:
            return ""
    return ""


def _extract_rows_from_text_with_llm(text: str, filename: str) -> List[Dict[str, Any]]:
    client = get_openai_client()
    if not client or not text.strip():
        return []
    try:
        default_model = os.getenv("SYSTEM1_UPLOAD_EXTRACT_MODEL", "gpt-4o-mini")
        model = resolve_chat_model(default_model, deployment_env="AZURE_OPENAI_SYSTEM1_EXTRACT_DEPLOYMENT")
        prompt = f"""
Extract sourcing opportunities from the uploaded text.
Return JSON object with key "rows", where each row may contain:
- row_type: "renewal" or "new_business"
- category, subcategory, supplier_name
- contract_id (for renewals), request_title (for new)
- estimated_spend_usd
- implementation_timeline_months (for new)
- months_to_expiry (for renewals)
- preferred_supplier_status
- rss_score, scs_score, sas_score (optional numeric 0-10)

Use only information in the text. Skip uncertain rows.
Text source: {filename}
"""
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract structured procurement opportunities."},
                {"role": "user", "content": f"{prompt}\n\nTEXT:\n{text[:120000]}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2200,
        )
        payload = json.loads((resp.choices[0].message.content or "{}").strip() or "{}")
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        return []
    except Exception:
        return []


def _build_preview_row(raw: Dict[str, Any], filename: str, source_kind: str, row_index: int) -> System1UploadPreviewRow:
    category = _normalize_category(raw.get("category"))
    contract_id = (str(raw.get("contract_id") or "")).strip() or None
    row_type = _normalize_type(raw.get("row_type") or raw.get("type"), contract_id)
    spend = _safe_float(
        raw.get("estimated_spend_usd")
        or raw.get("estimated_spend")
        or raw.get("spend")
        or raw.get("contract_value")
        or raw.get("annual_spend"),
        0.0,
    )
    months_to_expiry = _safe_opt_float(raw.get("months_to_expiry") or raw.get("expiry_months"))
    contract_end_date = _safe_opt_datetime(
        raw.get("contract_end_date")
        or raw.get("expiry_date")
        or raw.get("end_date")
        or raw.get("contract_expiry_date")
    )
    if months_to_expiry is None:
        months_to_expiry = _months_to_expiry_from_contract_end(contract_end_date)
    impl_months = _safe_opt_float(
        raw.get("implementation_timeline_months")
        or raw.get("implementation_months")
        or raw.get("timeline_months")
    )
    supplier_name = (str(raw.get("supplier_name") or raw.get("supplier") or "")).strip() or None
    row_id = f"{os.path.basename(filename)}::{row_index}"
    row = System1UploadPreviewRow(
        row_id=row_id,
        row_type=row_type,  # type: ignore[arg-type]
        source_filename=filename,
        source_kind=source_kind,  # type: ignore[arg-type]
        confidence=0.75 if source_kind == "structured" else 0.6,
        category=category,
        subcategory=(str(raw.get("subcategory") or "")).strip() or None,
        supplier_name=supplier_name,
        contract_id=contract_id,
        request_title=(str(raw.get("request_title") or raw.get("title") or "")).strip() or None,
        contract_end_date=contract_end_date,
        estimated_spend_usd=round(spend, 2),
        implementation_timeline_months=impl_months,
        months_to_expiry=months_to_expiry,
        preferred_supplier_status=(str(raw.get("preferred_supplier_status") or "")).strip() or None,
        rss_score=_safe_opt_float(raw.get("rss_score")),
        scs_score=_safe_opt_float(raw.get("scs_score")),
        sas_score=_safe_opt_float(raw.get("sas_score")),
        warnings=[],
        valid_for_approval=True,
    )
    return _finalize_upload_preview_row(row)


# ============================================================
# HEALTH CHECK
# ============================================================

def _llm_runtime_status() -> Dict[str, Any]:
    azure_mode = using_azure_openai()
    azure_key_present = bool((os.getenv("AZURE_OPENAI_API_KEY") or "").strip())
    openai_key_present = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    if azure_mode:
        key_source = "azure_openai_api_key" if azure_key_present else ("openai_api_key_fallback" if openai_key_present else "missing")
        provider = "azure_openai"
    else:
        key_source = "openai_api_key" if openai_key_present else "missing"
        provider = "openai"
    return {
        "provider": provider,
        "configured": bool(has_llm_credentials()),
        "azure_mode": azure_mode,
        "key_source": key_source,
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    llm = _llm_runtime_status()
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        components={
            "database": "ok",
            "vector_store": "ok",
            "agents": "ok",
            "llm_provider": llm["provider"],
        }
    )


@app.get("/api/llm/provider")
async def get_llm_provider_status():
    """Runtime LLM provider status (safe, no secrets)."""
    return _llm_runtime_status()


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


class CancelCaseRequest(BaseModel):
    reason_code: str = Field(min_length=2, max_length=100)
    reason_text: Optional[str] = Field(default=None, max_length=2000)
    cancelled_by: str = Field(default="human-manager", min_length=1, max_length=80)


class StageIntakeUpsertRequest(BaseModel):
    stage: str
    values: Dict[str, str] = Field(default_factory=dict)
    source: str = "human_form"
    updated_by: str = "human-manager"


class StageIntakeExtractRequest(BaseModel):
    stage: str
    free_text: str
    existing_values: Dict[str, str] = Field(default_factory=dict)


class StageGenerationCheckRequest(BaseModel):
    stage: str
    values: Dict[str, str] = Field(default_factory=dict)


def _required_generation_keys(stage: str) -> List[str]:
    s = (stage or "").strip().upper()
    if s == "DTP-01":
        return ["request_title", "business_unit", "scope_summary", "estimated_annual_value_usd"]
    if s == "DTP-02":
        return ["evaluation_criteria", "mandatory_requirements"]
    if s == "DTP-03":
        return ["rfx_title", "rfx_issue_date", "response_due_date"]
    if s == "DTP-04":
        return ["supplier_response_received", "supplier_evaluation_feedback", "award_recommendation"]
    if s == "DTP-05":
        return ["contract_signed", "legal_signoff", "contract_reference"]
    if s == "DTP-06":
        return ["execution_started", "implementation_milestones", "kpi_monitoring_status", "execution_confirmed_by_human"]
    return []


def _extract_stage_fields_heuristic(stage: str, free_text: str, existing: Dict[str, str]) -> Dict[str, str]:
    out = dict(existing or {})
    txt = (free_text or "").strip()
    if not txt:
        return out
    lower = txt.lower()
    # very lightweight deterministic extraction to support human confirmation UX.
    if stage == "DTP-01":
        m = re.search(r"(?:business unit|bu)\s*[:=-]\s*([^\n,;]+)", txt, flags=re.I)
        if m:
            out["business_unit"] = m.group(1).strip()
        m = re.search(r"(?:request title|title)\s*[:=-]\s*([^\n]+)", txt, flags=re.I)
        if m:
            out["request_title"] = m.group(1).strip()
        m = re.search(r"(?:estimated(?: annual)? value|budget|spend)\s*[:=-]\s*\$?([0-9][0-9,\.]*)", txt, flags=re.I)
        if m:
            out["estimated_annual_value_usd"] = m.group(1).replace(",", "").strip()
    if stage == "DTP-03":
        for key, label in [("rfx_issue_date", "issue"), ("response_due_date", "response due")]:
            m = re.search(rf"{label}[^\n:]*[:=-]\s*([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})", lower, flags=re.I)
            if m:
                out[key] = m.group(1)
    if stage == "DTP-05":
        if "contract signed" in lower and ("yes" in lower or "done" in lower or "completed" in lower):
            out["contract_signed"] = "yes"
    if stage == "DTP-06":
        if "execution started" in lower and ("yes" in lower or "started" in lower):
            out["execution_started"] = "yes"
    return out


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


@app.post("/api/cases/{case_id}/cancel")
async def cancel_case(case_id: str, body: CancelCaseRequest):
    """Cancel a case already in execution, with reason code and free-text reason."""
    service = get_case_service()
    ok = service.cancel_case(
        case_id=case_id,
        reason_code=body.reason_code,
        reason_text=body.reason_text,
        cancelled_by=body.cancelled_by,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"success": True, "case_id": case_id, "status": "Cancelled"}


@app.get("/api/cases/{case_id}/stage-intake")
async def get_stage_intake(case_id: str, stage: str = Query(...)):
    service = get_case_service()
    c = service.get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    values = service.get_stage_intake(case_id, stage)
    return {"case_id": case_id, "stage": stage, "values": values}


@app.put("/api/cases/{case_id}/stage-intake")
async def upsert_stage_intake(case_id: str, body: StageIntakeUpsertRequest):
    service = get_case_service()
    c = service.get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    ok = service.upsert_stage_intake(
        case_id,
        body.stage,
        body.values or {},
        source=body.source,
        updated_by=body.updated_by,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save stage intake")
    return {"success": True, "case_id": case_id, "stage": body.stage, "saved_fields": len(body.values or {})}


@app.post("/api/cases/{case_id}/stage-intake/extract")
async def extract_stage_intake(case_id: str, body: StageIntakeExtractRequest):
    service = get_case_service()
    c = service.get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    proposed = _extract_stage_fields_heuristic(body.stage, body.free_text, body.existing_values or {})
    return {
        "case_id": case_id,
        "stage": body.stage,
        "proposed_values": proposed,
        "note": "Heuristic extraction. Human confirmation required before saving.",
    }


@app.post("/api/cases/{case_id}/stage-intake/generation-check")
async def stage_generation_check(case_id: str, body: StageGenerationCheckRequest):
    service = get_case_service()
    c = service.get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    required = _required_generation_keys(body.stage)
    values = body.values or {}
    missing = [k for k in required if not str(values.get(k, "")).strip()]
    can_generate = len(missing) == 0
    return {
        "case_id": case_id,
        "stage": body.stage,
        "can_generate": can_generate,
        "required_fields": required,
        "missing_fields": missing,
    }


@app.get("/api/s2c/performance/metrics")
async def get_s2c_performance_metrics():
    """
    S2C high-level performance metrics:
    - AI reliability score (overall): average reliability derived from human edits
    - KLI Signal Attribution Accuracy: thumbs-up / total copilot explanation feedback
    - KPI Signal Coverage Rate: active cases with all required scoring inputs present
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

        # Signal Coverage Rate
        # Required inputs before scoring:
        # - contract_expiry (renewals: contract_id present; new requests: required_start_date intake present)
        # - spend (estimated_annual_value_usd intake)
        # - category strategy (category_id present)
        # - supplier risk (supplier_id present OR supplier_longlist intake provided)
        active_rows = [
            c for c in case_rows if str(getattr(c, "status", "") or "").strip().lower() not in {"cancelled", "closed"}
        ]
        covered_active = 0
        for c in active_rows:
            hd: Dict[str, Any] = {}
            try:
                hd = json.loads(c.human_decision) if c.human_decision else {}
            except json.JSONDecodeError:
                hd = {}
            dtp01_values: Dict[str, Any] = {}
            dtp02_values: Dict[str, Any] = {}
            try:
                dtp01_values = (
                    ((hd.get("DTP-01") or {}).get("_stage_intake") or {}).get("values") or {}
                    if isinstance(hd, dict)
                    else {}
                )
                dtp02_values = (
                    ((hd.get("DTP-02") or {}).get("_stage_intake") or {}).get("values") or {}
                    if isinstance(hd, dict)
                    else {}
                )
            except Exception:
                dtp01_values = {}
                dtp02_values = {}

            has_contract_expiry = bool(c.contract_id) or bool(str(dtp01_values.get("required_start_date") or "").strip())
            has_spend = bool(str(dtp01_values.get("estimated_annual_value_usd") or "").strip())
            has_category_strategy = bool(str(c.category_id or "").strip())
            has_supplier_risk = bool(str(c.supplier_id or "").strip()) or bool(
                str(dtp02_values.get("supplier_longlist") or "").strip()
            )
            if has_contract_expiry and has_spend and has_category_strategy and has_supplier_risk:
                covered_active += 1

        active_total = len(active_rows)
        signal_coverage_rate = (covered_active / active_total * 100.0) if active_total else None

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
                "signal_coverage_rate_pct": round(signal_coverage_rate, 2) if signal_coverage_rate is not None else None,
                "signal_coverage_cases_with_all_inputs": int(covered_active),
                "signal_coverage_active_cases_total": int(active_total),
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
# SYSTEM 1 STAGED UPLOAD ENDPOINTS
# ============================================================

@app.get("/api/system1/upload/templates")
async def system1_upload_templates():
    return {
        "templates": [
            {
                "name": name,
                "download_url": f"/api/system1/upload/templates/{name}",
            }
            for name in sorted(_SYSTEM1_TEMPLATES.keys())
        ]
    }


@app.get("/api/system1/upload/templates/{template_name}")
async def system1_upload_template_download(template_name: str):
    if template_name not in _SYSTEM1_TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found.")
    content = _SYSTEM1_TEMPLATES[template_name].encode("utf-8")
    return StreamingResponse(
        BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{template_name}"'},
    )


@app.get("/api/system1/upload/files/{stored_name}")
async def system1_upload_download_file(stored_name: str):
    safe_stored = os.path.basename(stored_name or "").strip()
    if not safe_stored:
        raise HTTPException(status_code=400, detail="Invalid file identifier.")
    abs_path = os.path.join(_SYSTEM1_UPLOAD_FILES_DIR, safe_stored)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="Uploaded file not found.")

    download_name = safe_stored
    with _system1_upload_lock:
        for job in _system1_upload_jobs.values():
            for file_meta in (job.get("uploaded_files") or []):
                if str(file_meta.get("stored_name") or "") == safe_stored:
                    download_name = str(file_meta.get("original_filename") or safe_stored)
                    break
            if download_name != safe_stored:
                break
    return FileResponse(abs_path, filename=download_name, media_type="application/octet-stream")


@app.post("/api/system1/admin/clear")
async def system1_admin_clear_uploaded_data():
    """
    Temporary admin utility: clear staged upload artifacts/jobs and upload-staged opportunities.
    Keep this low-visibility in UI; later wire to proper auth/role checks.
    """
    removed_files = 0
    for name in os.listdir(_SYSTEM1_UPLOAD_FILES_DIR):
        p = os.path.join(_SYSTEM1_UPLOAD_FILES_DIR, name)
        if os.path.isfile(p):
            try:
                os.remove(p)
                removed_files += 1
            except Exception:
                pass

    with _system1_upload_lock:
        cleared_jobs = len(_system1_upload_jobs)
        _system1_upload_jobs.clear()

    session = get_heatmap_db().get_db_session()
    try:
        upload_ids = [
            int(x)
            for x in session.exec(
                select(Opportunity.id).where(Opportunity.source == "upload_staged")
            ).all()
            if x is not None
        ]
        if upload_ids:
            session.exec(delete(ReviewFeedback).where(ReviewFeedback.opportunity_id.in_(upload_ids)))
            session.exec(
                delete(AuditLog).where(
                    AuditLog.event_type.in_(["SCORE_OVERRIDE", "OPPORTUNITY_DISPOSITION_UPDATED"]),
                    AuditLog.entity_id.in_([str(i) for i in upload_ids]),
                )
            )
            session.exec(delete(Opportunity).where(Opportunity.id.in_(upload_ids)))
            session.commit()
        removed_opps = len(upload_ids)
    finally:
        session.close()

    return {
        "success": True,
        "removed_files": removed_files,
        "cleared_jobs": cleared_jobs,
        "removed_opportunities": removed_opps,
    }


@app.post("/api/system1/upload/preview", response_model=System1UploadPreviewResponse)
async def system1_upload_preview(
    files: List[UploadFile] = File(...),
    column_mapping_json: Optional[str] = Form(None),
    ingestion_profile: Optional[str] = Form("default"),
    top_n: Optional[int] = Form(None),
    rank_by: Optional[str] = Form("completeness"),
):
    """
    Stage 1: Upload files and preview normalized opportunity rows.
    No scoring writes are performed in this step.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one file.")

    candidates: List[System1UploadPreviewRow] = []
    uploaded_files: List[Dict[str, Any]] = []
    parsing_notes: List[str] = []

    column_mapping: Optional[Dict[str, str]] = None
    if column_mapping_json:
        try:
            parsed = json.loads(column_mapping_json)
            if isinstance(parsed, dict):
                column_mapping = {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            raise HTTPException(status_code=400, detail="column_mapping_json must be valid JSON object.")

    structured_files: List[Tuple[str, bytes]] = []
    for f in files:
        filename = (f.filename or "").strip() or "upload.bin"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_SYSTEM1_UPLOAD_EXTENSIONS:
            parsing_notes.append(f"Skipped {filename}: unsupported type {ext}")
            continue
        content = await f.read()
        if not content:
            parsing_notes.append(f"Skipped {filename}: empty file")
            continue
        uploaded_files.append(_persist_system1_uploaded_file(content, filename))

        source_kind = "structured" if ext in {".csv", ".xls", ".xlsx"} else "document"
        if source_kind == "structured":
            structured_files.append((filename, content))
        else:
            text = _extract_text_for_upload(content, filename)
            if not text.strip():
                parsing_notes.append(f"No text extracted from {filename}")
                continue
            llm_rows = _extract_rows_from_text_with_llm(text, filename)
            if llm_rows:
                raw_rows = [{str(k).strip().lower(): v for k, v in r.items()} for r in llm_rows]
            else:
                parsing_notes.append(f"{filename}: LLM extraction unavailable; provide CSV/XLS for deterministic parsing.")
                raw_rows = []

            for idx, raw in enumerate(raw_rows, start=1):
                candidates.append(_build_preview_row(raw, filename, source_kind, idx))

    if structured_files:
        structured_result = StructuredFileAdapter(
            structured_files,
            profile=ingestion_profile or "default",
            explicit_mapping=column_mapping,
        ).ingest()
        parsing_notes.extend(structured_result.notes)
        for filename, rows in structured_result.rows_by_source.items():
            for idx, raw in enumerate(rows, start=1):
                candidates.append(_build_preview_row(raw, filename, "structured", idx))

    if not candidates:
        raise HTTPException(
            status_code=400,
            detail="No candidate opportunities extracted. Use CSV/XLS with mapped columns or richer document content.",
        )

    scored_rows = enrich_rows_for_preview([c.model_dump() for c in candidates])
    candidates = [System1UploadPreviewRow(**r) for r in scored_rows]
    for c in candidates:
        c.warnings = list(dict.fromkeys([*c.warnings, *c.readiness_warnings]))
        c.valid_for_approval = bool(c.valid_for_approval and c.readiness_status != "needs_review")
    rank_by_norm = _normalize_rank_by(rank_by)
    candidates = _rank_candidates(candidates, rank_by_norm)
    all_candidates = list(candidates)
    if top_n is not None and top_n > 0 and len(candidates) > top_n:
        candidates = candidates[:top_n]
        parsing_notes.append(
            f"Applied top_n={top_n} with rank_by={rank_by_norm}; returned {len(candidates)} rows."
        )

    job_id = f"up-{uuid4().hex[:12]}"
    valid_candidates = sum(1 for c in all_candidates if c.valid_for_approval)
    analysis = summarize_preview_completeness([c.model_dump() for c in all_candidates])
    analysis["returned_rows"] = len(candidates)
    analysis["top_n_applied"] = int(top_n) if top_n is not None and top_n > 0 else None
    analysis["rank_by_applied"] = rank_by_norm
    with _system1_upload_lock:
        _system1_upload_jobs[job_id] = {
            "job_id": job_id,
            "status": "preview_ready",
            "created_at": datetime.utcnow().isoformat(),
            "total_candidates": len(candidates),
            "approved_count": 0,
            "created_opportunity_ids": [],
            "run_triggered": False,
            "warning_rows_count": len([c for c in candidates if c.readiness_status == "ready_with_warnings"]),
            "parsing_notes": parsing_notes,
            "candidates": [c.model_dump() for c in candidates],
            "analysis": analysis,
            "uploaded_files": uploaded_files,
        }

    return System1UploadPreviewResponse(
        job_id=job_id,
        status="preview_ready",
        total_candidates=len(all_candidates),
        valid_candidates=valid_candidates,
        candidates=candidates,
        parsing_notes=parsing_notes,
        analysis=analysis,
    )


@app.post("/api/system1/upload/scan-bundle", response_model=System1UploadPreviewResponse)
async def system1_upload_scan_bundle(
    files: List[UploadFile] = File(...),
    column_mapping_json: Optional[str] = Form(None),
    ingestion_profile: Optional[str] = Form("default"),
    top_n: Optional[int] = Form(None),
    rank_by: Optional[str] = Form("completeness"),
):
    """
    Bundle scan mode:
    - Parse multiple structured files
    - Fuse contract/spend/metrics rows into deduplicated candidates
    - Return scored preview rows for human review
    """
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one file.")

    column_mapping: Optional[Dict[str, str]] = None
    if column_mapping_json:
        try:
            parsed = json.loads(column_mapping_json)
            if isinstance(parsed, dict):
                column_mapping = {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            raise HTTPException(status_code=400, detail="column_mapping_json must be valid JSON object.")

    rows_by_file: Dict[str, List[Dict[str, Any]]] = {}
    parsing_notes: List[str] = []
    skipped_non_structured: List[str] = []
    uploaded_files: List[Dict[str, Any]] = []
    structured_files: List[Tuple[str, bytes]] = []

    for f in files:
        filename = (f.filename or "").strip() or "upload.bin"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_SYSTEM1_UPLOAD_EXTENSIONS:
            parsing_notes.append(f"Skipped {filename}: unsupported type {ext}")
            continue
        content = await f.read()
        if not content:
            parsing_notes.append(f"Skipped {filename}: empty file")
            continue
        uploaded_files.append(_persist_system1_uploaded_file(content, filename))

        if ext not in {".csv", ".xls", ".xlsx"}:
            skipped_non_structured.append(filename)
            continue

        structured_files.append((filename, content))

    if skipped_non_structured:
        parsing_notes.append(
            "Bundle scan currently fuses structured files only; non-structured files were skipped: "
            + ", ".join(skipped_non_structured[:8])
            + ("..." if len(skipped_non_structured) > 8 else "")
        )

    if structured_files:
        structured_result = StructuredFileAdapter(
            structured_files,
            profile=ingestion_profile or "default",
            explicit_mapping=column_mapping,
        ).ingest()
        parsing_notes.extend(structured_result.notes)
        rows_by_file = structured_result.rows_by_source

    if not rows_by_file:
        raise HTTPException(
            status_code=400,
            detail="No structured candidate rows extracted. Upload CSV/XLS/XLSX files for bundle scan.",
        )

    graph = get_system1_ingestion_graph()
    graph_state = graph.invoke(
        {
            "rows_by_file": rows_by_file,
            "parsing_notes": parsing_notes,
            "top_n": top_n,
            "rank_by": _normalize_rank_by(rank_by),
            "row_builder": _build_preview_row,
            "execution_trace": [],
        },
        config={"recursion_limit": 50},
    )

    parsing_notes = list(graph_state.get("parsing_notes") or [])
    candidates_dicts = list(graph_state.get("candidates") or [])
    total_candidates = int(graph_state.get("total_candidates") or 0)
    valid_candidates = int(graph_state.get("valid_candidates") or 0)
    analysis = dict(graph_state.get("analysis") or {})

    if total_candidates <= 0 or not candidates_dicts:
        raise HTTPException(
            status_code=400,
            detail="Bundle scan produced no fused opportunities. Check supplier/category/spend coverage.",
        )

    candidates = [System1UploadPreviewRow(**r) for r in candidates_dicts]

    job_id = f"up-{uuid4().hex[:12]}"
    with _system1_upload_lock:
        _system1_upload_jobs[job_id] = {
            "job_id": job_id,
            "status": "preview_ready",
            "created_at": datetime.utcnow().isoformat(),
            "total_candidates": total_candidates,
            "approved_count": 0,
            "created_opportunity_ids": [],
            "run_triggered": False,
            "warning_rows_count": len([c for c in candidates if c.readiness_status == "ready_with_warnings"]),
            "parsing_notes": parsing_notes,
            "candidates": [c.model_dump() for c in candidates],
            "analysis": analysis,
            "uploaded_files": uploaded_files,
        }

    return System1UploadPreviewResponse(
        job_id=job_id,
        status="preview_ready",
        total_candidates=total_candidates,
        valid_candidates=valid_candidates,
        candidates=candidates,
        parsing_notes=parsing_notes,
        analysis=analysis,
    )


@app.post("/api/system1/upload/preview-erp", response_model=System1UploadPreviewResponse)
async def system1_upload_preview_erp(body: System1ErpPreviewRequest):
    """
    Stage 1 variant for API/ERP integrations.
    Accepts JSON rows, normalizes through ERP adapter, and returns the same preview contract as bulk upload.
    """
    if not body.rows:
        raise HTTPException(status_code=400, detail="rows is required.")

    result = ErpJsonAdapter(
        source_system=body.source_system,
        rows=body.rows,
        profile=body.mapping_profile or "erp_generic",
        explicit_mapping=body.column_mapping or {},
    ).ingest()

    candidates: List[System1UploadPreviewRow] = []
    for source_name, rows in result.rows_by_source.items():
        for idx, raw in enumerate(rows, start=1):
            candidates.append(_build_preview_row(raw, source_name, "structured", idx))

    if not candidates:
        raise HTTPException(status_code=400, detail="No candidate opportunities extracted from ERP payload.")

    scored_rows = enrich_rows_for_preview([c.model_dump() for c in candidates])
    candidates = [System1UploadPreviewRow(**r) for r in scored_rows]
    for c in candidates:
        c.warnings = list(dict.fromkeys([*c.warnings, *c.readiness_warnings]))
        c.valid_for_approval = bool(c.valid_for_approval and c.readiness_status != "needs_review")

    rank_by_norm = _normalize_rank_by(body.rank_by)
    candidates = _rank_candidates(candidates, rank_by_norm)
    all_candidates = list(candidates)
    if body.top_n is not None and body.top_n > 0 and len(candidates) > body.top_n:
        candidates = candidates[: body.top_n]
        result.notes.append(
            f"Applied top_n={body.top_n} with rank_by={rank_by_norm}; returned {len(candidates)} rows."
        )

    job_id = f"up-{uuid4().hex[:12]}"
    valid_candidates = sum(1 for c in all_candidates if c.valid_for_approval)
    analysis = summarize_preview_completeness([c.model_dump() for c in all_candidates])
    analysis["returned_rows"] = len(candidates)
    analysis["top_n_applied"] = int(body.top_n) if body.top_n is not None and body.top_n > 0 else None
    analysis["rank_by_applied"] = rank_by_norm
    analysis["ingestion_diagnostics"] = result.diagnostics

    with _system1_upload_lock:
        _system1_upload_jobs[job_id] = {
            "job_id": job_id,
            "status": "preview_ready",
            "created_at": datetime.utcnow().isoformat(),
            "total_candidates": len(candidates),
            "approved_count": 0,
            "created_opportunity_ids": [],
            "run_triggered": False,
            "warning_rows_count": len([c for c in candidates if c.readiness_status == "ready_with_warnings"]),
            "parsing_notes": result.notes,
            "candidates": [c.model_dump() for c in candidates],
            "analysis": analysis,
            "uploaded_files": [],
        }

    return System1UploadPreviewResponse(
        job_id=job_id,
        status="preview_ready",
        total_candidates=len(all_candidates),
        valid_candidates=valid_candidates,
        candidates=candidates,
        parsing_notes=result.notes,
        analysis=analysis,
    )


@app.post("/api/system1/upload/approve", response_model=System1UploadApproveResponse)
async def system1_upload_approve(body: System1UploadApproveRequest):
    """
    Stage 2: Approve selected preview rows, persist opportunities, then trigger a scoring refresh run.
    """
    with _system1_upload_lock:
        job = _system1_upload_jobs.get(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Preview job not found or expired.")

    candidates = [System1UploadPreviewRow(**r) for r in job.get("candidates", [])]
    approved_ids = set(body.approved_row_ids or [])
    overrides = body.row_overrides or {}
    uploaded_files = list(job.get("uploaded_files") or [])
    by_id = {r.row_id: r for r in candidates}
    merged: List[System1UploadPreviewRow] = []
    for rid in body.approved_row_ids or []:
        base = by_id.get(rid)
        if not base:
            continue
        merged.append(_merge_system1_upload_row(base, overrides.get(rid)))
    rescored = enrich_rows_for_preview([r.model_dump() for r in merged])
    rescored_rows = [System1UploadPreviewRow(**r) for r in rescored]
    selected = [r for r in rescored_rows if r.valid_for_approval and r.readiness_status != "needs_review"]
    if not selected:
        raise HTTPException(
            status_code=400,
            detail="No valid selected rows to approve after edits. Ensure spend is positive and required fields are set.",
        )
    warning_row_ids = {r.row_id for r in selected if r.readiness_status == "ready_with_warnings"}
    acknowledged = set(body.acknowledge_warning_row_ids or [])
    missing_ack = sorted(list(warning_row_ids - acknowledged))
    if missing_ack:
        raise HTTPException(
            status_code=400,
            detail=(
                "Some selected rows have warnings and require acknowledgment before approval: "
                + ", ".join(missing_ack[:10])
            ),
        )

    session = get_heatmap_db().get_db_session()
    created_ids: List[int] = []
    try:
        for row in selected:
            comp = row.score_components or {}
            ius = comp.get("ius_score", {}).get("value")
            es = comp.get("es_score", {}).get("value")
            csis = comp.get("csis_score", {}).get("value")
            eus = comp.get("eus_score", {}).get("value")
            fis = comp.get("fis_score", {}).get("value")
            rss = comp.get("rss_score", {}).get("value")
            scs = comp.get("scs_score", {}).get("value")
            sas = comp.get("sas_score", {}).get("value")
            is_new = row.row_type == "new_business"
            justification = (
                f"System1 staged scoring ({row.row_type}) by specialist orchestration. "
                f"Readiness={row.readiness_status}; confidence={row.computed_confidence}."
            )
            row_source_name = str(row.source_filename or "").strip()
            row_source_name_lc = row_source_name.lower()
            if row_source_name_lc in {"bundle_scan", "scan_bundle", "bundle-scan", "bundle scan"}:
                # Fused bundle rows are synthesized from multiple uploaded files.
                row_artifacts = list(uploaded_files)
            else:
                row_artifacts = [
                    f
                    for f in uploaded_files
                    if str(f.get("original_filename") or "").strip().lower() == row_source_name_lc
                ]
            months_to_expiry = row.months_to_expiry or _months_to_expiry_from_contract_end(row.contract_end_date)
            score_provenance = {
                "score_components": comp,
                "row_type": row.row_type,
                "source_kind": row.source_kind,
                "source_filename": row.source_filename,
                "supporting_artifacts": row_artifacts,
                "scoring_inputs": {
                    "contract_end_date": row.contract_end_date.isoformat() if row.contract_end_date else None,
                    "months_to_expiry": months_to_expiry,
                    "estimated_spend_usd": row.estimated_spend_usd,
                    "implementation_timeline_months": row.implementation_timeline_months,
                    "preferred_supplier_status": row.preferred_supplier_status,
                    "request_title": row.request_title,
                    "supplier_name": row.supplier_name,
                    "category": row.category,
                    "subcategory": row.subcategory,
                },
            }
            opp = Opportunity(
                contract_id=None if is_new else (row.contract_id or f"CNT-UP-{uuid4().hex[:10].upper()}"),
                request_id=(f"REQ-UP-{uuid4().hex[:10].upper()}" if is_new else None),
                supplier_name=row.supplier_name,
                category=row.category,
                subcategory=row.subcategory,
                eus_score=float(eus) if eus is not None else None,
                ius_score=float(ius) if ius is not None else None,
                fis_score=float(fis) if fis is not None else None,
                es_score=float(es) if es is not None else None,
                rss_score=float(rss) if rss is not None else None,
                scs_score=float(scs) if scs is not None else None,
                csis_score=float(csis) if csis is not None else None,
                sas_score=float(sas) if sas is not None else None,
                total_score=float(row.computed_total_score or 0.0),
                tier=str(row.computed_tier or "T4"),
                recommended_action_window=row.recommended_action_window,
                justification_summary=justification,
                status="Pending",
                disposition="new_request" if is_new else "renewal_candidate",
                not_pursue_reason_code=None,
                source="upload_staged",
                estimated_spend_usd=row.estimated_spend_usd,
                implementation_timeline_months=row.implementation_timeline_months if is_new else None,
                request_title=row.request_title,
                preferred_supplier_status=row.preferred_supplier_status,
                contract_end_date=row.contract_end_date
                or (datetime.utcnow() + timedelta(days=(30.4375 * float(row.months_to_expiry or 9.0)))),
                weights_used_json=json.dumps(row.weights_used or {}),
                score_provenance_json=json.dumps(score_provenance),
                system1_readiness_status=row.readiness_status,
                system1_warnings_json=json.dumps(row.readiness_warnings or []),
            )
            session.add(opp)
            session.commit()
            session.refresh(opp)
            created_ids.append(int(opp.id))

    finally:
        session.close()

    run_result = _start_heatmap_pipeline_background()
    run_triggered = bool(run_result.get("success"))
    with _system1_upload_lock:
        job["status"] = "approved"
        job["approved_count"] = len(selected)
        job["created_opportunity_ids"] = created_ids
        job["run_triggered"] = run_triggered
        job["warning_rows_count"] = len([r for r in selected if r.readiness_status == "ready_with_warnings"])
        approved_set = set(body.approved_row_ids or [])
        kept = [
            r for r in (job.get("candidates") or [])
            if str(r.get("row_id") or "") not in approved_set
        ]
        job["candidates"] = kept
        job["total_candidates"] = len(kept)
        job["valid_candidates"] = sum(1 for r in kept if bool(r.get("valid_for_approval")))
        _system1_upload_jobs[body.job_id] = job

    return System1UploadApproveResponse(
        success=True,
        job_id=body.job_id,
        approved_count=len(selected),
        created_opportunity_ids=created_ids,
        run_triggered=run_triggered,
        message="Approved rows persisted. Scoring refresh started in background.",
    )


@app.get("/api/system1/upload/jobs/{job_id}", response_model=System1UploadJobStatusResponse)
async def system1_upload_job_status(job_id: str):
    with _system1_upload_lock:
        job = _system1_upload_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return System1UploadJobStatusResponse(
        job_id=job["job_id"],
        status=job.get("status", "unknown"),
        created_at=job.get("created_at", ""),
        total_candidates=int(job.get("total_candidates", 0)),
        approved_count=int(job.get("approved_count", 0)),
        created_opportunity_ids=[int(x) for x in job.get("created_opportunity_ids", [])],
        run_triggered=bool(job.get("run_triggered", False)),
        parsing_notes=list(job.get("parsing_notes", [])),
        warning_rows_count=int(job.get("warning_rows_count", 0)),
    )


@app.get("/api/system1/upload/jobs/{job_id}/preview", response_model=System1UploadPreviewResponse)
async def system1_upload_job_preview(job_id: str):
    with _system1_upload_lock:
        job = _system1_upload_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Preview job not found or expired.")
    candidates = [System1UploadPreviewRow(**r) for r in (job.get("candidates") or [])]
    valid_candidates = sum(1 for c in candidates if c.valid_for_approval)
    return System1UploadPreviewResponse(
        job_id=job.get("job_id", job_id),
        status=job.get("status", "unknown"),
        total_candidates=len(candidates),
        valid_candidates=valid_candidates,
        candidates=candidates,
        parsing_notes=list(job.get("parsing_notes") or []),
        analysis=dict(job.get("analysis") or {}),
    )


@app.delete("/api/system1/upload/jobs/{job_id}", response_model=System1UploadJobDeleteResponse)
async def system1_upload_job_delete(job_id: str):
    with _system1_upload_lock:
        removed = _system1_upload_jobs.pop(job_id, None) is not None
    return System1UploadJobDeleteResponse(success=True, job_id=job_id, removed=removed)


@app.get("/api/system1/upload/active-preview-summary", response_model=System1ActivePreviewSummaryResponse)
async def system1_upload_active_preview_summary():
    with _system1_upload_lock:
        jobs = list(_system1_upload_jobs.values())
    if not jobs:
        return System1ActivePreviewSummaryResponse()

    def _created_key(j: Dict[str, Any]) -> str:
        return str(j.get("created_at") or "")

    latest = sorted(jobs, key=_created_key, reverse=True)[0]
    raw_rows = list(latest.get("candidates") or [])
    total_rows = len(raw_rows)
    ready_rows = 0
    ready_warn_rows = 0
    needs_review_rows = 0
    for r in raw_rows:
        st = str(r.get("readiness_status") or "ready")
        if st == "needs_review":
            needs_review_rows += 1
        elif st == "ready_with_warnings":
            ready_warn_rows += 1
        else:
            ready_rows += 1
    covered_rows = ready_rows + ready_warn_rows
    return System1ActivePreviewSummaryResponse(
        job_id=str(latest.get("job_id") or ""),
        status=str(latest.get("status") or "unknown"),
        total_rows=total_rows,
        covered_rows=covered_rows,
        ready_rows=ready_rows,
        ready_with_warnings_rows=ready_warn_rows,
        needs_review_rows=needs_review_rows,
    )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)








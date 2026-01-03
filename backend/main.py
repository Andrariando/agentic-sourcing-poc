"""
FastAPI backend for Agentic Sourcing System.

This is the ONLY entry point for the frontend.
All business logic, agents, and data access go through this API.
"""
import os
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import services
from backend.services.case_service import get_case_service
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
    HealthCheckResponse
)
from shared.constants import DocumentType, DataType


# Initialize database on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    init_db()
    print("✅ Database initialized")
    yield
    # Shutdown
    print("👋 Shutting down")


# Create FastAPI app
app = FastAPI(
    title="Agentic Sourcing API",
    description="Backend API for the Agentic Sourcing Copilot",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        edited_fields=request.edited_fields
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





"""
API Client for frontend-backend communication.

Supports two modes:
1. SEPARATED MODE: API calls to backend (local dev with separate processes)
2. INTEGRATED MODE: Direct imports (Streamlit Cloud single-process deployment)

The mode is auto-detected based on backend availability.
"""
import requests
from typing import Optional, List, Dict, Any
from io import BytesIO
import os

from shared.constants import API_BASE_URL
from shared.schemas import (
    CaseListResponse, CaseDetail, CreateCaseRequest, CreateCaseResponse,
    ChatRequest, ChatResponse,
    DecisionRequest, DecisionResponse,
    DocumentIngestResponse, DocumentListResponse, DocumentMetadata,
    DataIngestResponse, DataPreviewResponse, DataIngestMetadata
)


# Check if we should use integrated mode (direct imports instead of HTTP)
def _should_use_integrated_mode() -> bool:
    """Determine if we should use integrated mode (direct imports)."""
    # Check for explicit override to use API mode (local development)
    if os.environ.get("USE_API_MODE", "").lower() == "true":
        return False
    
    # Check for explicit override to use integrated mode
    if os.environ.get("USE_INTEGRATED_MODE", "").lower() == "true":
        return True
    
    # Check if running on Streamlit Cloud (multiple detection methods)
    cwd = os.getcwd()
    streamlit_cloud_indicators = [
        os.environ.get("STREAMLIT_SHARING_MODE"),
        os.environ.get("IS_STREAMLIT_CLOUD"),
        os.environ.get("HOSTNAME", "").endswith(".streamlit.app") if os.environ.get("HOSTNAME") else False,
        "/mount/src/" in cwd,  # Streamlit Cloud working directory pattern
        cwd.startswith("/mount/"),  # Another Streamlit Cloud pattern
    ]
    
    if any(streamlit_cloud_indicators):
        print(f"[APIClient] Detected Streamlit Cloud environment, using integrated mode")
        return True
    
    # Try to connect to backend - if fails, use integrated mode
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print(f"[APIClient] Backend available at {API_BASE_URL}, using API mode")
            return False
        else:
            print(f"[APIClient] Backend returned {response.status_code}, using integrated mode")
            return True
    except Exception as e:
        print(f"[APIClient] Cannot reach backend ({e}), using integrated mode")
        return True


class APIClient:
    """
    Client for communicating with the backend.
    
    Supports two modes:
    - HTTP mode: Calls FastAPI backend via REST API
    - Integrated mode: Direct imports for Streamlit Cloud deployment
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or API_BASE_URL
        self._integrated_mode = _should_use_integrated_mode()
        self._services_initialized = False
        
        # Lazy-loaded services for integrated mode
        self._case_service = None
        self._chat_service = None
        self._ingestion_service = None
    
    def _init_services(self):
        """Initialize backend services for integrated mode."""
        if self._services_initialized:
            return
        
        if self._integrated_mode:
            try:
                # Initialize database first
                from backend.persistence.database import init_db
                init_db()
                
                # Import and initialize services
                from backend.services.case_service import get_case_service
                from backend.services.chat_service import get_chat_service
                from backend.services.ingestion_service import get_ingestion_service
                
                self._case_service = get_case_service()
                self._chat_service = get_chat_service()
                self._ingestion_service = get_ingestion_service()
                self._services_initialized = True
            except ImportError as e:
                import traceback
                print(f"Import error initializing services: {e}")
                print(traceback.format_exc())
                raise Exception(f"Import error: {e}")
            except Exception as e:
                import traceback
                print(f"Failed to initialize services: {e}")
                print(traceback.format_exc())
                raise
    
    def _url(self, path: str) -> str:
        """Build full URL."""
        return f"{self.base_url}{path}"
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response."""
        if response.status_code >= 400:
            try:
                error = response.json()
                raise APIError(error.get("detail", "Unknown error"), response.status_code)
            except:
                raise APIError(response.text, response.status_code)
        
        return response.json()
    
    # ==================== HEALTH ====================
    
    def health_check(self) -> Dict[str, Any]:
        """Check backend health."""
        if self._integrated_mode:
            try:
                self._init_services()
                if self._services_initialized:
                    return {"status": "healthy", "mode": "integrated", "components": {"database": "ok"}}
                return {"status": "unhealthy", "error": "Failed to initialize services", "mode": "integrated"}
            except Exception as e:
                return {"status": "unhealthy", "error": f"Integrated mode error: {str(e)}", "mode": "integrated"}
        
        try:
            response = requests.get(self._url("/health"), timeout=5)
            result = self._handle_response(response)
            result["mode"] = "api"
            return result
        except requests.exceptions.ConnectionError:
            # Fallback to integrated mode
            self._integrated_mode = True
            return self.health_check()
        except Exception as e:
            # Fallback to integrated mode on any error
            self._integrated_mode = True
            return self.health_check()
    
    # ==================== CASES ====================
    
    def list_cases(
        self,
        status: Optional[str] = None,
        dtp_stage: Optional[str] = None,
        category_id: Optional[str] = None,
        limit: int = 50
    ) -> CaseListResponse:
        """Get list of cases."""
        if self._integrated_mode:
            self._init_services()
            cases = self._case_service.list_cases(
                status=status,
                dtp_stage=dtp_stage,
                category_id=category_id,
                limit=limit
            )
            return CaseListResponse(
                cases=cases,
                total_count=len(cases),
                filters_applied={"status": status, "dtp_stage": dtp_stage}
            )
        
        params = {"limit": limit}
        if status:
            params["status"] = status
        if dtp_stage:
            params["dtp_stage"] = dtp_stage
        if category_id:
            params["category_id"] = category_id
        
        response = requests.get(self._url("/api/cases"), params=params)
        data = self._handle_response(response)
        return CaseListResponse(**data)
    
    def get_case(self, case_id: str) -> CaseDetail:
        """Get case details."""
        if self._integrated_mode:
            self._init_services()
            case = self._case_service.get_case(case_id)
            if not case:
                raise APIError("Case not found", 404)
            return case
        
        response = requests.get(self._url(f"/api/cases/{case_id}"))
        data = self._handle_response(response)
        return CaseDetail(**data)
    
    def get_artifact_packs(self, case_id: str) -> List[Dict[str, Any]]:
        """Get all artifact packs for a case (for audit trail)."""
        if self._integrated_mode:
            self._init_services()
            packs = self._case_service.get_all_artifact_packs(case_id)
            # Convert to dicts for consistent handling
            result = []
            for pack in packs:
                # Convert execution metadata properly
                exec_meta_dict = None
                if pack.execution_metadata:
                    try:
                        # Try model_dump first (Pydantic v2)
                        if hasattr(pack.execution_metadata, 'model_dump'):
                            exec_meta_dict = pack.execution_metadata.model_dump()
                        # Try dict() method (Pydantic v1)
                        elif hasattr(pack.execution_metadata, 'dict'):
                            exec_meta_dict = pack.execution_metadata.dict()
                        # Fallback to __dict__
                        elif hasattr(pack.execution_metadata, '__dict__'):
                            exec_meta_dict = pack.execution_metadata.__dict__
                        else:
                            exec_meta_dict = pack.execution_metadata
                        
                        # Convert task_details list
                        if exec_meta_dict and "task_details" in exec_meta_dict:
                            task_details_list = exec_meta_dict["task_details"]
                            exec_meta_dict["task_details"] = [
                                (
                                    td.model_dump() if hasattr(td, 'model_dump') else
                                    (td.dict() if hasattr(td, 'dict') else
                                    (td.__dict__ if hasattr(td, '__dict__') else td))
                                )
                                for td in task_details_list
                            ]
                    except Exception as e:
                        print(f"Warning: Could not convert execution metadata: {e}")
                        exec_meta_dict = None
                
                pack_dict = {
                    "pack_id": pack.pack_id,
                    "agent_name": pack.agent_name,
                    "tasks_executed": pack.tasks_executed,
                    "artifacts": [
                        {
                            "artifact_id": a.artifact_id,
                            "type": a.type,
                            "title": a.title,
                            "content_text": a.content_text,
                            "verification_status": a.verification_status
                        }
                        for a in pack.artifacts
                    ],
                    "created_at": pack.created_at,
                    "execution_metadata": exec_meta_dict
                }
                result.append(pack_dict)
            return result
        
        # HTTP mode - not yet implemented
        try:
            response = requests.get(self._url(f"/api/cases/{case_id}/artifact_packs"))
            data = self._handle_response(response)
            return data if isinstance(data, list) else []
        except:
            return []
    
    def create_case(
        self,
        category_id: str,
        trigger_source: str = "User",
        contract_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> CreateCaseResponse:
        """Create a new case."""
        if self._integrated_mode:
            self._init_services()
            case_id = self._case_service.create_case(
                category_id=category_id,
                trigger_source=trigger_source,
                contract_id=contract_id,
                supplier_id=supplier_id,
                name=name
            )
            return CreateCaseResponse(
                case_id=case_id,
                success=True,
                message=f"Case {case_id} created"
            )
        
        request = CreateCaseRequest(
            category_id=category_id,
            trigger_source=trigger_source,
            contract_id=contract_id,
            supplier_id=supplier_id,
            name=name
        )
        
        response = requests.post(
            self._url("/api/cases"),
            json=request.model_dump()
        )
        data = self._handle_response(response)
        return CreateCaseResponse(**data)
    
    # ==================== CHAT ====================
    
    def send_message(
        self,
        case_id: str,
        message: str,
        use_tier_2: bool = False
    ) -> ChatResponse:
        """
        Send message to copilot.
        
        This goes through the Supervisor for governance.
        """
        if self._integrated_mode:
            self._init_services()
            return self._chat_service.process_message(
                case_id=case_id,
                user_message=message,
                use_tier_2=use_tier_2
            )
        
        request = ChatRequest(
            case_id=case_id,
            user_message=message,
            use_tier_2=use_tier_2
        )
        
        response = requests.post(
            self._url("/api/chat"),
            json=request.model_dump()
        )
        data = self._handle_response(response)
        return ChatResponse(**data)
    
    # ==================== DECISIONS ====================
    
    def approve_decision(
        self,
        case_id: str,
        reason: Optional[str] = None,
        edited_fields: Optional[Dict[str, Any]] = None,
        decision_data: Optional[Dict[str, Any]] = None
    ) -> DecisionResponse:
        """Approve a pending decision."""
        if self._integrated_mode:
            self._init_services()
            result = self._chat_service.process_decision(
                case_id=case_id,
                decision="Approve",
                reason=reason,
                edited_fields=edited_fields,
                decision_data=decision_data
            )
            return DecisionResponse(
                case_id=case_id,
                decision="Approve",
                success=result["success"],
                new_dtp_stage=result.get("new_dtp_stage"),
                message=result["message"]
            )
        
        request = DecisionRequest(
            case_id=case_id,
            decision="Approve",
            reason=reason,
            edited_fields=edited_fields or {},
            decision_data=decision_data
        )
        
        response = requests.post(
            self._url("/api/decisions/approve"),
            json=request.model_dump()
        )
        data = self._handle_response(response)
        return DecisionResponse(**data)
    
    def reject_decision(
        self,
        case_id: str,
        reason: Optional[str] = None
    ) -> DecisionResponse:
        """Reject a pending decision."""
        if self._integrated_mode:
            self._init_services()
            result = self._chat_service.process_decision(
                case_id=case_id,
                decision="Reject",
                reason=reason
            )
            return DecisionResponse(
                case_id=case_id,
                decision="Reject",
                success=result["success"],
                new_dtp_stage=result.get("new_dtp_stage"),
                message=result["message"]
            )
        
        request = DecisionRequest(
            case_id=case_id,
            decision="Reject",
            reason=reason
        )
        
        response = requests.post(
            self._url("/api/decisions/reject"),
            json=request.model_dump()
        )
        data = self._handle_response(response)
        return DecisionResponse(**data)
    
    # ==================== DOCUMENT INGESTION ====================
    
    def ingest_document(
        self,
        file_content: bytes,
        filename: str,
        document_type: str,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        region: Optional[str] = None,
        dtp_relevance: Optional[List[str]] = None,
        case_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> DocumentIngestResponse:
        """Ingest a document for RAG."""
        import json
        
        if self._integrated_mode:
            self._init_services()
            return self._ingestion_service.ingest_document(
                file_content=file_content,
                filename=filename,
                document_type=document_type,
                supplier_id=supplier_id,
                category_id=category_id,
                region=region,
                dtp_relevance=dtp_relevance,
                case_id=case_id,
                description=description
            )
        
        files = {
            "file": (filename, BytesIO(file_content), "application/octet-stream")
        }
        
        data = {
            "document_type": document_type
        }
        
        if supplier_id:
            data["supplier_id"] = supplier_id
        if category_id:
            data["category_id"] = category_id
        if region:
            data["region"] = region
        if dtp_relevance:
            data["dtp_relevance"] = json.dumps(dtp_relevance)
        if case_id:
            data["case_id"] = case_id
        if description:
            data["description"] = description
        
        response = requests.post(
            self._url("/api/ingest/document"),
            files=files,
            data=data
        )
        result = self._handle_response(response)
        return DocumentIngestResponse(**result)
    
    def list_documents(
        self,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> DocumentListResponse:
        """List ingested documents."""
        if self._integrated_mode:
            self._init_services()
            return self._ingestion_service.list_documents(
                supplier_id=supplier_id,
                category_id=category_id,
                document_type=document_type
            )
        
        params = {}
        if supplier_id:
            params["supplier_id"] = supplier_id
        if category_id:
            params["category_id"] = category_id
        if document_type:
            params["document_type"] = document_type
        
        response = requests.get(self._url("/api/documents"), params=params)
        data = self._handle_response(response)
        return DocumentListResponse(**data)
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document."""
        if self._integrated_mode:
            self._init_services()
            return self._ingestion_service.delete_document(document_id)
        
        response = requests.delete(self._url(f"/api/documents/{document_id}"))
        self._handle_response(response)
        return True
    
    # ==================== STRUCTURED DATA INGESTION ====================
    
    def preview_data(
        self,
        file_content: bytes,
        filename: str,
        data_type: str
    ) -> DataPreviewResponse:
        """Preview data before ingestion."""
        if self._integrated_mode:
            self._init_services()
            return self._ingestion_service.preview_data(
                file_content=file_content,
                filename=filename,
                data_type=data_type
            )
        
        files = {
            "file": (filename, BytesIO(file_content), "application/octet-stream")
        }
        
        data = {
            "data_type": data_type
        }
        
        response = requests.post(
            self._url("/api/ingest/data/preview"),
            files=files,
            data=data
        )
        result = self._handle_response(response)
        return DataPreviewResponse(**result)
    
    def ingest_data(
        self,
        file_content: bytes,
        filename: str,
        data_type: str,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        time_period: Optional[str] = None,
        description: Optional[str] = None
    ) -> DataIngestResponse:
        """Ingest structured data."""
        if self._integrated_mode:
            self._init_services()
            return self._ingestion_service.ingest_data(
                file_content=file_content,
                filename=filename,
                data_type=data_type,
                supplier_id=supplier_id,
                category_id=category_id,
                time_period=time_period,
                description=description
            )
        
        files = {
            "file": (filename, BytesIO(file_content), "application/octet-stream")
        }
        
        data = {
            "data_type": data_type
        }
        
        if supplier_id:
            data["supplier_id"] = supplier_id
        if category_id:
            data["category_id"] = category_id
        if time_period:
            data["time_period"] = time_period
        if description:
            data["description"] = description
        
        response = requests.post(
            self._url("/api/ingest/data"),
            files=files,
            data=data
        )
        result = self._handle_response(response)
        return DataIngestResponse(**result)
    
    def get_ingestion_history(
        self,
        data_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get ingestion history."""
        if self._integrated_mode:
            self._init_services()
            return self._ingestion_service.get_ingestion_history(
                data_type=data_type,
                limit=limit
            )
        
        params = {"limit": limit}
        if data_type:
            params["data_type"] = data_type
        
        response = requests.get(self._url("/api/ingest/history"), params=params)
        data = self._handle_response(response)
        return data.get("history", [])


class APIError(Exception):
    """API error with status code."""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# Singleton client
_client = None


def get_api_client() -> APIClient:
    """Get or create API client singleton."""
    global _client
    if _client is None:
        _client = APIClient()
    return _client


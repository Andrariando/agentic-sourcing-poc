"""
API Client for frontend-backend communication.

The frontend ONLY communicates with the backend through this client.
It NEVER accesses agents, vector stores, or databases directly.
"""
import requests
from typing import Optional, List, Dict, Any
from io import BytesIO

from shared.constants import API_BASE_URL
from shared.schemas import (
    CaseListResponse, CaseDetail, CreateCaseRequest, CreateCaseResponse,
    ChatRequest, ChatResponse,
    DecisionRequest, DecisionResponse,
    DocumentIngestResponse, DocumentListResponse,
    DataIngestResponse, DataPreviewResponse
)


class APIClient:
    """
    Client for communicating with the backend API.
    
    CRITICAL: This is the ONLY way the frontend accesses backend functionality.
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or API_BASE_URL
    
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
        try:
            response = requests.get(self._url("/health"), timeout=5)
            return self._handle_response(response)
        except requests.exceptions.ConnectionError:
            return {"status": "unhealthy", "error": "Cannot connect to backend"}
    
    # ==================== CASES ====================
    
    def list_cases(
        self,
        status: Optional[str] = None,
        dtp_stage: Optional[str] = None,
        category_id: Optional[str] = None,
        limit: int = 50
    ) -> CaseListResponse:
        """Get list of cases."""
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
        response = requests.get(self._url(f"/api/cases/{case_id}"))
        data = self._handle_response(response)
        return CaseDetail(**data)
    
    def create_case(
        self,
        category_id: str,
        trigger_source: str = "User",
        contract_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> CreateCaseResponse:
        """Create a new case."""
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
        edited_fields: Optional[Dict[str, Any]] = None
    ) -> DecisionResponse:
        """Approve a pending decision."""
        request = DecisionRequest(
            case_id=case_id,
            decision="Approve",
            reason=reason,
            edited_fields=edited_fields or {}
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


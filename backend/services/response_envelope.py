"""
Response envelope for standardized chat responses.

Provides structured responses with trace_id, agent_id, and backward
compatibility for plain string responses.
"""
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ResponseEnvelope(BaseModel):
    """
    Structured response envelope returned by agents.
    
    Provides:
    - trace_id: Unique identifier for tracing/debugging
    - agent_id: Which agent produced this response
    - intent: Classified user intent
    - message: User-facing text
    - artifacts: Optional list of generated artifacts
    - fallback_used: Whether fallback logic was used
    - error: Optional error message
    """
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    intent: str = ""
    message: str = ""
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    fallback_used: bool = False
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    @classmethod
    def from_string(cls, message: str, intent: str = "UNKNOWN", agent_id: str = "") -> "ResponseEnvelope":
        """
        Create envelope from plain string response (backward compatibility).
        
        This allows legacy code that returns strings to work seamlessly
        with the new envelope system.
        """
        return cls(
            message=message,
            intent=intent,
            agent_id=agent_id,
            fallback_used=False
        )
    
    @classmethod
    def from_error(cls, error_message: str, trace_id: Optional[str] = None) -> "ResponseEnvelope":
        """Create envelope for error responses."""
        return cls(
            trace_id=trace_id or str(uuid.uuid4()),
            message=f"An error occurred: {error_message}",
            error=error_message,
            fallback_used=True
        )
    
    def to_display_message(self) -> str:
        """
        Get the user-facing message for display.
        
        Used by rendering layer to support both envelope and plain string.
        """
        return self.message


def wrap_response(response, intent: str = "UNKNOWN", agent_id: str = "") -> ResponseEnvelope:
    """
    Wrap a response (string or envelope) into a ResponseEnvelope.
    
    Provides backward compatibility:
    - If already an envelope, return as-is
    - If string, wrap into envelope
    """
    if isinstance(response, ResponseEnvelope):
        return response
    elif isinstance(response, str):
        return ResponseEnvelope.from_string(response, intent, agent_id)
    else:
        # Try to extract message from dict-like objects
        try:
            message = str(response.get("message", str(response)))
            return ResponseEnvelope.from_string(message, intent, agent_id)
        except:
            return ResponseEnvelope.from_string(str(response), intent, agent_id)


def generate_trace_id() -> str:
    """Generate a unique trace ID for request tracking."""
    return str(uuid.uuid4())

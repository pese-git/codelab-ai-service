from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

class AgentRequest(BaseModel):
    session_id: str
    type: str
    content: str
    role: Literal["user", "assistant", "system", "tool"] = "user"

class AgentResponse(BaseModel):
    type: Literal["assistant_message", "tool_call"]
    token: Optional[str] = None
    is_final: bool = False
    tool_call: Optional[Dict[str, Any]] = None  # For tool_call type

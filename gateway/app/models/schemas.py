from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class WSUserMessage(BaseModel):
    type: Literal["user_message"]
    content: str
    role: Literal["user", "assistant", "system", "tool"]


class WSToolCall(BaseModel):
    """WebSocket message for tool call from Agent to IDE"""

    type: Literal["tool_call"]
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "type": "tool_call",
                "call_id": "call_abc123",
                "tool_name": "read_file",
                "arguments": {"path": "/src/main.py"},
            }
        }


class WSToolResult(BaseModel):
    """WebSocket message for tool result from IDE to Agent"""

    type: Literal["tool_result"]
    call_id: str
    result: Optional[Any] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "type": "tool_result",
                "call_id": "call_abc123",
                "result": {"content": "file content here"},
            }
        }


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


class WSErrorResponse(BaseModel):
    type: Literal["error"]
    content: str


class ToolCallTracking(BaseModel):
    """Tracks tool calls being routed through Gateway"""

    call_id: str
    session_id: str
    tool_name: str
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"  # pending, sent_to_ide, completed, failed, timeout
    ide_websocket_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

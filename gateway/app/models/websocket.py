from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel


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


class WSErrorResponse(BaseModel):
    type: Literal["error"]
    content: str

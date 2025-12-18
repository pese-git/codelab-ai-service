from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    name: Optional[str] = None # если требуется (например, имя инструмента)
    # session_id намеренно убирается из единичного сообщения: оно есть в SessionState


class MessageResponse(BaseModel):
    status: str
    message: str


class SSEToken(BaseModel):
    token: str
    is_final: bool
    type: str = "assistant_message"  # "assistant_message", "tool_call", "tool_result"
    metadata: Optional[Dict[str, Any]] = None  # Additional data for tool calls, etc.


class WSToolCall(BaseModel):
    """WebSocket message for tool call from Agent to IDE"""

    type: Literal["tool_call"]
    call_id: str = Field(description="Unique identifier for this tool call")
    tool_name: str = Field(description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(description="Arguments for the tool")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "tool_call",
                "call_id": "call_abc123",
                "tool_name": "read_file",
                "arguments": {"path": "/src/main.py"},
            }
        }


class ToolExecutionStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ReadFileArgs(BaseModel):
    path: str

from typing import Optional
class ToolArguments(BaseModel):
    read_file: Optional[ReadFileArgs] = None
    # Можно добавить другие инструменты: write_file: Optional[WriteFileArgs] = None

class ToolCall(BaseModel):
    id: str = Field(description="Unique identifier for this tool call")
    tool_name: str = Field(description="Name of the tool to execute")
    arguments: ToolArguments = Field(description="Arguments for the tool")
    created_at: datetime = Field(default_factory=datetime.now)
    status: ToolExecutionStatus = Field(default=ToolExecutionStatus.PENDING)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "call_abc123",
                "tool_name": "read_file",
                "arguments": {"path": "/src/main.py"},
                "status": "pending",
            }
        }


class ToolResult(BaseModel):
    call_id: str = Field(description="ID of the tool call this result belongs to")
    result: Optional[Any] = Field(description="Result of tool execution")
    error: Optional[str] = Field(description="Error message if execution failed")
    executed_at: datetime = Field(default_factory=datetime.now)
    execution_time_ms: Optional[int] = Field(description="Execution time in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "call_id": "call_abc123",
                "result": {"content": "file content here"},
                "execution_time_ms": 150,
            }
        }


class ToolCallRequest(BaseModel):
    session_id: str
    tool_call: ToolCall
    timeout_seconds: int = Field(default=30, description="Timeout for tool execution")


class PendingToolCall(BaseModel):
    """Tracks a tool call waiting for execution result"""

    tool_call: ToolCall
    session_id: str
    request_time: datetime = Field(default_factory=datetime.now)
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 3


class SessionState(BaseModel):
    """Maintains state for an active session"""

    session_id: str
    messages: List[Message] = Field(default_factory=list)
    pending_tool_calls: Dict[str, PendingToolCall] = Field(default_factory=dict)
    active_tool_calls: List[str] = Field(default_factory=list)
    last_activity: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

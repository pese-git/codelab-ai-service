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
    requires_approval: Optional[bool] = Field(
        default=False,
        description="Whether this tool call requires user approval before execution (HITL)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "tool_call",
                "call_id": "call_abc123",
                "tool_name": "read_file",
                "arguments": {"path": "/src/main.py"},
                "requires_approval": False,
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
    """Аргументы для инструмента read_file"""
    path: str = Field(description="Path to the file relative to project workspace")
    encoding: Optional[str] = Field(default="utf-8", description="File encoding")
    start_line: Optional[int] = Field(default=None, description="Starting line number (1-based, inclusive)", ge=1)
    end_line: Optional[int] = Field(default=None, description="Ending line number (1-based, inclusive)", ge=1)


class WriteFileArgs(BaseModel):
    """Аргументы для инструмента write_file"""
    path: str = Field(description="Path to the file relative to project workspace")
    content: str = Field(description="Content to write to the file")
    encoding: Optional[str] = Field(default="utf-8", description="File encoding")
    create_dirs: Optional[bool] = Field(default=False, description="Create parent directories if they don't exist")
    backup: Optional[bool] = Field(default=True, description="Create backup before overwriting existing file")


class ToolArguments(BaseModel):
    """Унифицированная модель аргументов для всех инструментов"""
    read_file: Optional[ReadFileArgs] = None
    write_file: Optional[WriteFileArgs] = None

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


class AgentStreamRequest(BaseModel):
    """Request model for streaming endpoint - accepts either user message or tool result"""

    session_id: str = Field(description="Session identifier")
    message: Dict[str, Any] = Field(description="Message content - can be user_message or tool_result")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "session_id": "session_123",
                    "message": {
                        "type": "user_message",
                        "content": "Hello, how are you?"
                    }
                },
                {
                    "session_id": "session_123",
                    "message": {
                        "type": "tool_result",
                        "call_id": "call_abc123",
                        "tool_name": "read_file",
                        "result": {"content": "file contents here"}
                    }
                }
            ]
        }


class StreamChunk(BaseModel):
    """SSE event chunk for streaming responses"""
    
    type: Literal["assistant_message", "tool_call", "error", "done", "switch_agent", "agent_switched"] = Field(
        description="Type of the stream chunk"
    )
    content: Optional[str] = Field(default=None, description="Text content for assistant messages")
    token: Optional[str] = Field(default=None, description="Single token for streaming")
    is_final: bool = Field(default=False, description="Whether this is the final chunk")
    
    # For tool_call type
    call_id: Optional[str] = Field(default=None, description="Tool call identifier")
    tool_name: Optional[str] = Field(default=None, description="Name of the tool to call")
    arguments: Optional[Dict[str, Any]] = Field(default=None, description="Tool arguments")
    requires_approval: Optional[bool] = Field(default=False, description="Whether this tool requires user approval (HITL)")
    
    # For error type
    error: Optional[str] = Field(default=None, description="Error message if any")
    
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "assistant_message",
                    "token": "Hello",
                    "is_final": False
                },
                {
                    "type": "tool_call",
                    "call_id": "call_123",
                    "tool_name": "read_file",
                    "arguments": {"path": "/src/main.py"},
                    "is_final": True
                },
                {
                    "type": "error",
                    "error": "Failed to process request",
                    "is_final": True
                },
                {
                    "type": "switch_agent",
                    "metadata": {"target_agent": "coder", "reason": "Coding task detected"},
                    "is_final": True
                },
                {
                    "type": "agent_switched",
                    "content": "Switched to coder agent",
                    "metadata": {"from_agent": "orchestrator", "to_agent": "coder"},
                    "is_final": False
                }
            ]
        }


# Multi-agent specific schemas

class AgentSwitchRequest(BaseModel):
    """Request to switch to a different agent"""
    
    type: Literal["switch_agent"]
    agent_type: str = Field(
        description="Target agent type: orchestrator, coder, architect, debug, ask"
    )
    content: str = Field(description="Message for the new agent")
    reason: Optional[str] = Field(
        default=None,
        description="Reason for the switch"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "switch_agent",
                "agent_type": "coder",
                "content": "Create a new widget",
                "reason": "User requested coder agent"
            }
        }


class AgentInfo(BaseModel):
    """Information about an agent"""
    
    type: str = Field(description="Agent type")
    name: str = Field(description="Agent name")
    description: str = Field(description="Agent description")
    allowed_tools: List[str] = Field(description="List of allowed tools")
    has_file_restrictions: bool = Field(
        description="Whether agent has file editing restrictions"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "coder",
                "name": "Coder Agent",
                "description": "Specialized in writing and modifying code",
                "allowed_tools": ["read_file", "write_file", "execute_command"],
                "has_file_restrictions": False
            }
        }

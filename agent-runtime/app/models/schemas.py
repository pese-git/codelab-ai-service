from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ===== Planning Models =====

class SubtaskStatus(str, Enum):
    """Status of a subtask in execution plan"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Subtask(BaseModel):
    """Individual subtask in an execution plan"""
    
    id: str = Field(description="Unique identifier for the subtask")
    description: str = Field(description="Description of what needs to be done")
    agent: str = Field(description="Agent type that should handle this subtask (coder, architect, debug, ask)")
    estimated_time: Optional[str] = Field(default=None, description="Estimated time to complete (e.g., '2 min', '5 min')")
    status: SubtaskStatus = Field(default=SubtaskStatus.PENDING, description="Current status of the subtask")
    result: Optional[str] = Field(default=None, description="Result or output after completion")
    error: Optional[str] = Field(default=None, description="Error message if subtask failed")
    dependencies: List[str] = Field(default_factory=list, description="IDs of subtasks that must complete before this one")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "subtask_1",
                "description": "Add Riverpod dependency to pubspec.yaml",
                "agent": "coder",
                "estimated_time": "2 min",
                "status": "pending",
                "dependencies": []
            }
        }


class ExecutionPlan(BaseModel):
    """Execution plan for complex tasks"""
    
    plan_id: str = Field(description="Unique identifier for the plan")
    session_id: str = Field(description="Session this plan belongs to")
    original_task: str = Field(description="Original user task that triggered planning")
    subtasks: List[Subtask] = Field(description="List of subtasks to execute")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_subtask_index: int = Field(default=0, description="Index of currently executing subtask")
    is_complete: bool = Field(default=False, description="Whether all subtasks are complete")
    requires_approval: bool = Field(default=True, description="Whether plan requires user approval")
    is_approved: bool = Field(default=False, description="Whether plan was approved by user")
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": "plan_abc123",
                "session_id": "session_123",
                "original_task": "Migrate from Provider to Riverpod",
                "subtasks": [
                    {
                        "id": "subtask_1",
                        "description": "Add riverpod dependency",
                        "agent": "coder",
                        "estimated_time": "2 min",
                        "status": "pending"
                    }
                ],
                "current_subtask_index": 0,
                "is_complete": False
            }
        }


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    name: Optional[str] = None # если требуется (например, имя инструмента)
    # session_id намеренно убирается из единичного сообщения: оно есть в SessionState


class ToolCall(BaseModel):
    """Tool call parsed from LLM response"""
    id: str = Field(description="Unique identifier for this tool call")
    tool_name: str = Field(description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(description="Arguments for the tool")


class SessionState(BaseModel):
    """Maintains state for an active session"""

    session_id: str
    messages: List[Message] = Field(default_factory=list)
    last_activity: datetime = Field(default_factory=datetime.now)


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
    
    type: Literal["assistant_message", "tool_call", "error", "done", "switch_agent", "agent_switched", "plan_notification"] = Field(
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

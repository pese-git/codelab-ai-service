"""
Common API schemas used across multiple endpoints.

Contains:
- StreamChunk: SSE streaming response chunks
- ToolCall: Tool call representation
- SessionState: Session state
- AgentInfo: Agent information

Note: Message is imported from domain.entities.message (full domain model)
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ....domain.entities.message import Message


class ToolCall(BaseModel):
    """Tool call parsed from LLM response"""
    id: str = Field(description="Unique identifier for this tool call")
    tool_name: str = Field(description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(description="Arguments for the tool")


class StreamChunk(BaseModel):
    """SSE event chunk for streaming responses"""
    
    type: Literal[
        "assistant_message",
        "tool_call",
        "error",
        "done",
        "switch_agent",
        "agent_switched",
        "status",  # For progress updates
        "plan_created",  # For plan creation notification
        "plan_approval_required",  # For plan approval request
        "plan_rejected",  # For plan rejection
        "plan_modification_requested",  # For plan modification request
        "execution_completed"  # For plan execution completion
    ] = Field(
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


class SessionState(BaseModel):
    """
    Maintains state for an active session.
    
    Note: This is a simplified version for API. Domain layer uses
    app.domain.entities.session.Session.
    For messages, use List[Dict] or import Message from domain.entities.
    """
    session_id: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    last_activity: datetime = Field(default_factory=datetime.now)


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

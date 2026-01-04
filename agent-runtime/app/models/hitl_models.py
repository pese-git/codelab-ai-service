"""
HITL (Human-in-the-Loop) models for tool approval workflow.

Provides models for:
- Policy configuration
- User decisions
- Audit logging
- Pending state management

HITL states are stored in AgentContext.metadata for session-level tracking.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HITLDecision(str, Enum):
    """User decision for tool call requiring approval"""
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class HITLPolicyRule(BaseModel):
    """Rule for determining if tool call requires HITL approval"""
    tool_name: str = Field(description="Tool name pattern (supports wildcards)")
    requires_approval: bool = Field(description="Whether this tool requires approval")
    reason: Optional[str] = Field(default=None, description="Reason for requiring approval")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "write_file",
                "requires_approval": True,
                "reason": "File modification requires user approval"
            }
        }


class HITLPolicy(BaseModel):
    """Policy configuration for HITL tool approval"""
    enabled: bool = Field(default=True, description="Whether HITL is enabled")
    rules: List[HITLPolicyRule] = Field(default_factory=list, description="List of policy rules")
    default_requires_approval: bool = Field(
        default=False,
        description="Default behavior for tools not matching any rule"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "rules": [
                    {
                        "tool_name": "write_file",
                        "requires_approval": True,
                        "reason": "File modification"
                    },
                    {
                        "tool_name": "execute_command",
                        "requires_approval": True,
                        "reason": "Command execution"
                    },
                    {
                        "tool_name": "delete_file",
                        "requires_approval": True,
                        "reason": "File deletion"
                    }
                ],
                "default_requires_approval": False
            }
        }


class HITLUserDecision(BaseModel):
    """User decision on tool call requiring approval (WebSocket message from IDE)"""
    type: Literal["hitl_decision"] = Field(default="hitl_decision")
    call_id: str = Field(description="Tool call identifier")
    decision: HITLDecision = Field(description="User decision")
    modified_arguments: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Modified arguments if decision is EDIT"
    )
    feedback: Optional[str] = Field(
        default=None,
        description="User feedback/reason for decision"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "hitl_decision",
                    "call_id": "call_abc123",
                    "decision": "approve"
                },
                {
                    "type": "hitl_decision",
                    "call_id": "call_abc123",
                    "decision": "edit",
                    "modified_arguments": {"path": "/src/main_v2.py", "content": "..."}
                },
                {
                    "type": "hitl_decision",
                    "call_id": "call_abc123",
                    "decision": "reject",
                    "feedback": "This operation is too risky"
                }
            ]
        }


class HITLAuditLog(BaseModel):
    """Audit log entry for HITL action"""
    session_id: str = Field(description="Session identifier")
    call_id: str = Field(description="Tool call identifier")
    tool_name: str = Field(description="Tool name")
    original_arguments: Dict[str, Any] = Field(description="Original tool arguments")
    decision: HITLDecision = Field(description="User decision")
    modified_arguments: Optional[Dict[str, Any]] = Field(default=None)
    feedback: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "call_id": "call_abc123",
                "tool_name": "write_file",
                "original_arguments": {"path": "/src/main.py", "content": "..."},
                "decision": "approve",
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class HITLPendingState(BaseModel):
    """
    State for tool call pending HITL approval.
    
    Stored in AgentContext.metadata['hitl_pending_calls'] as Dict[call_id, HITLPendingState]
    """
    call_id: str = Field(description="Tool call identifier")
    tool_name: str = Field(description="Tool name")
    arguments: Dict[str, Any] = Field(description="Tool arguments")
    reason: Optional[str] = Field(default=None, description="Reason for requiring approval")
    created_at: datetime = Field(default_factory=datetime.now)
    timeout_seconds: int = Field(default=300, description="Timeout for user decision (5 min)")
    
    def is_expired(self) -> bool:
        """Check if the pending state has expired"""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.timeout_seconds
    
    class Config:
        json_schema_extra = {
            "example": {
                "call_id": "call_abc123",
                "tool_name": "write_file",
                "arguments": {"path": "/src/main.py", "content": "..."},
                "reason": "File modification requires approval",
                "created_at": "2024-01-01T12:00:00",
                "timeout_seconds": 300
            }
        }

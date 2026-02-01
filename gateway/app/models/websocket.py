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
    requires_approval: Optional[bool] = False

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


class WSAgentSwitched(BaseModel):
    """WebSocket message for agent switch notification"""
    
    type: Literal["agent_switched"]
    content: str
    from_agent: str
    to_agent: str
    reason: str
    confidence: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "agent_switched",
                "content": "Switched to coder agent",
                "from_agent": "orchestrator",
                "to_agent": "coder",
                "reason": "Coding task detected",
                "confidence": "high"
            }
        }


class WSSwitchAgent(BaseModel):
    """WebSocket message for explicit agent switch request from IDE"""
    
    type: Literal["switch_agent"]
    agent_type: str
    content: str
    reason: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "switch_agent",
                "agent_type": "architect",
                "content": "Design the authentication system",
                "reason": "User requested architect"
            }
        }


class WSErrorResponse(BaseModel):
    type: Literal["error"]
    content: str


class WSHITLDecision(BaseModel):
    """WebSocket message for HITL user decision from IDE to Agent"""
    
    type: Literal["hitl_decision"]
    call_id: str
    decision: Literal["approve", "edit", "reject"]
    modified_arguments: Optional[Dict[str, Any]] = None
    feedback: Optional[str] = None
    
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
                    "modified_arguments": {"path": "/src/main_v2.py"}
                },
                {
                    "type": "hitl_decision",
                    "call_id": "call_abc123",
                    "decision": "reject",
                    "feedback": "This operation is too risky"
                }
            ]
        }


class WSPlanApprovalRequired(BaseModel):
    """WebSocket message for plan approval request from Agent to IDE"""
    
    type: Literal["plan_approval_required"]
    content: str
    approval_request_id: str
    plan_id: str
    plan_summary: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "plan_approval_required",
                "content": "Plan requires your approval before execution",
                "approval_request_id": "plan-approval-abc123",
                "plan_id": "plan-xyz789",
                "plan_summary": {
                    "goal": "Create Flutter login form",
                    "subtasks_count": 4,
                    "total_estimated_time": "20 min"
                }
            }
        }


class WSPlanDecision(BaseModel):
    """WebSocket message for plan approval decision from IDE to Agent"""
    
    type: Literal["plan_decision"]
    approval_request_id: str
    decision: Literal["approve", "reject", "modify"]
    feedback: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "plan_decision",
                    "approval_request_id": "plan-approval-abc123",
                    "decision": "approve"
                },
                {
                    "type": "plan_decision",
                    "approval_request_id": "plan-approval-abc123",
                    "decision": "reject",
                    "feedback": "Plan is too complex"
                },
                {
                    "type": "plan_decision",
                    "approval_request_id": "plan-approval-abc123",
                    "decision": "modify",
                    "feedback": "Please add error handling"
                }
            ]
        }

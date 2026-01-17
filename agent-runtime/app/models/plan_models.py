"""
Plan approval models - similar to HITL models but for execution plans.

Provides models for:
- User decisions on execution plans (approve/edit/reject)
- Audit logging for plan decisions
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PlanDecision(str, Enum):
    """User decision for execution plan"""
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class PlanUserDecision(BaseModel):
    """User decision on execution plan (message from IDE)"""
    type: Literal["plan_decision"] = Field(default="plan_decision")
    plan_id: str = Field(description="Plan identifier")
    decision: PlanDecision = Field(description="User decision")
    modified_subtasks: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Modified subtasks if decision is EDIT"
    )
    feedback: Optional[str] = Field(
        default=None,
        description="User feedback/reason for decision"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "plan_decision",
                    "plan_id": "plan_abc123",
                    "decision": "approve"
                },
                {
                    "type": "plan_decision",
                    "plan_id": "plan_abc123",
                    "decision": "edit",
                    "modified_subtasks": [
                        {
                            "id": "subtask_1",
                            "description": "Modified description",
                            "agent": "coder",
                            "estimated_time": "3 min"
                        }
                    ]
                },
                {
                    "type": "plan_decision",
                    "plan_id": "plan_abc123",
                    "decision": "reject",
                    "feedback": "This approach is not suitable"
                }
            ]
        }


class PlanAuditLog(BaseModel):
    """Audit log entry for plan decision"""
    session_id: str = Field(description="Session identifier")
    plan_id: str = Field(description="Plan identifier")
    original_task: str = Field(description="Original user task")
    decision: PlanDecision = Field(description="User decision")
    modified_subtasks: Optional[List[Dict[str, Any]]] = Field(default=None)
    feedback: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "plan_id": "plan_abc123",
                "original_task": "Create TODO app",
                "decision": "approve",
                "timestamp": "2024-01-01T12:00:00"
            }
        }

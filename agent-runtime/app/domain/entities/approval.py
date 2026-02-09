"""
Unified Approval System - Domain Entities.

Provides entities for:
- ApprovalPolicy: Centralized policy for all approval types
- PendingApprovalState: State of pending approval requests
- ApprovalRequestType: Types of approval requests

This replaces the HITL-specific entities with a unified approach.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
import re

from pydantic import BaseModel, Field, ConfigDict
from .base import Entity


class ApprovalRequestType(str, Enum):
    """Types of requests that may require approval"""
    TOOL = "tool"
    PLAN = "plan"


class ApprovalPolicyRule(BaseModel):
    """Rule for determining if a request requires approval"""
    
    # Matching criteria
    request_type: ApprovalRequestType = Field(
        description="Type of request: tool, plan, etc."
    )
    subject_pattern: str = Field(
        description="Regex pattern to match subject (tool name, plan description)"
    )
    
    # Conditions (all must be true for rule to match)
    conditions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional conditions from details (e.g., {file_size_gt: 1000000})"
    )
    
    # Decision
    requires_approval: bool = Field(
        description="Whether this request requires approval"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason why approval is required"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "request_type": "tool",
                    "subject_pattern": "write_file|execute_command",
                    "requires_approval": True,
                    "reason": "File modification/execution requires approval"
                },
                {
                    "request_type": "plan",
                    "subject_pattern": ".*",
                    "conditions": {"total_subtasks_gt": 5, "estimated_duration_gt_minutes": 10},
                    "requires_approval": True,
                    "reason": "Complex plan requires approval"
                }
            ]
        }


class ApprovalPolicy(BaseModel):
    """Policy configuration for approval system"""
    enabled: bool = Field(default=True)
    rules: List[ApprovalPolicyRule] = Field(default_factory=list)
    default_requires_approval: bool = Field(
        default=False,
        description="Default decision if no rules match"
    )
    
    @staticmethod
    def default() -> "ApprovalPolicy":
        """Default policy for production"""
        return ApprovalPolicy(
            enabled=True,
            rules=[
                # Tool-related rules
                ApprovalPolicyRule(
                    request_type=ApprovalRequestType.TOOL,
                    subject_pattern="write_file",
                    requires_approval=True,
                    reason="File modification requires approval"
                ),
                ApprovalPolicyRule(
                    request_type=ApprovalRequestType.TOOL,
                    subject_pattern="execute_command",
                    requires_approval=True,
                    reason="Command execution requires approval"
                ),
                ApprovalPolicyRule(
                    request_type=ApprovalRequestType.TOOL,
                    subject_pattern="delete_file|move_file|create_directory",
                    requires_approval=True,
                    reason="File system operation requires approval"
                ),
                # Safe operations - explicitly no approval needed
                ApprovalPolicyRule(
                    request_type=ApprovalRequestType.TOOL,
                    subject_pattern="read_file|list_files|search_files",
                    requires_approval=False
                ),
                # Plan-related rules
                ApprovalPolicyRule(
                    request_type=ApprovalRequestType.PLAN,
                    subject_pattern=".*",  # Any plan
                    requires_approval=True,
                    reason="All complex plans require approval"
                ),
            ],
            default_requires_approval=False
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "rules": [
                    {
                        "request_type": "tool",
                        "subject_pattern": "write_file",
                        "requires_approval": True,
                        "reason": "File modification"
                    }
                ],
                "default_requires_approval": False
            }
        }


class PendingApprovalState(Entity):
    """
    State of an approval request pending user decision.
    
    Unified entity for all request types.
    
    Note: Uses request_id as the primary identifier (mapped to Entity.id).
    """
    
    request_type: str = Field(description="Type: tool, plan, etc.")
    subject: str = Field(description="Subject (tool name, plan title)")
    session_id: str = Field(description="Related session")
    details: Dict[str, Any] = Field(description="Request details (flexible)")
    reason: Optional[str] = Field(default=None, description="Why approval is required")
    status: Literal['pending', 'approved', 'rejected'] = Field(
        default='pending'
    )
    
    @property
    def request_id(self) -> str:
        """Alias for id field to maintain backward compatibility."""
        return self.id
    
    def __init__(self, request_id: str = None, **data):
        """
        Initialize with request_id mapped to id.
        
        Args:
            request_id: Unique identifier (mapped to Entity.id)
            **data: Other fields
        """
        # Map request_id to id for Entity base class
        if request_id is not None:
            data['id'] = request_id
        elif 'id' not in data:
            raise ValueError("Either 'request_id' or 'id' must be provided")
        
        super().__init__(**data)
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "id": "req-tool-123",
                    "request_type": "tool",
                    "subject": "write_file",
                    "session_id": "session-abc",
                    "details": {
                        "path": "src/main.py",
                        "content": "...",
                        "size_bytes": 2048
                    },
                    "reason": "File modification requires approval",
                    "created_at": "2026-01-24T10:00:00Z",
                    "status": "pending"
                },
                {
                    "id": "req-plan-456",
                    "request_type": "plan",
                    "subject": "Migration to Riverpod",
                    "session_id": "session-abc",
                    "details": {
                        "plan_id": "plan-123",
                        "description": "Migrate from Provider to Riverpod",
                        "total_subtasks": 3,
                        "estimated_duration": "12 min",
                        "subtasks": []
                    },
                    "reason": "Complex plan requires approval",
                    "created_at": "2026-01-24T10:30:00Z",
                    "status": "pending"
                }
            ]
        }

"""
SQLAlchemy models for HITL (Human-in-the-Loop) persistence.

Contains:
- PendingApproval: Pending tool approval requests
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PendingApproval(Base):
    """
    SQLAlchemy model for pending tool approval requests.
    
    Stores tool calls that require user approval (HITL - Human-in-the-Loop).
    This ensures approval requests persist across IDE restarts and reinstalls.
    
    Note: call_id serves as the unique identifier (no separate approval_id needed).
    
    UPDATED: Added unified approval system fields (request_type, subject, details)
    for supporting multiple approval types (tools, plans, etc.)
    """
    __tablename__ = 'pending_approvals'
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    # Unified approval fields (NEW)
    request_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="Unified request identifier")
    request_type: Mapped[str] = mapped_column(String(50), nullable=False, default="tool", comment="Type of request: tool, plan, etc.")
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Subject of request (tool name, plan title)")
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="Request details (flexible JSON)")
    
    # Legacy HITL fields (for backward compatibility)
    call_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Tool call identifier (legacy, use request_id)")
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Session identifier")
    tool_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Name of the tool being called (legacy)")
    arguments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="Tool arguments as JSON (legacy)")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Reason why approval is required")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), comment="When approval was requested")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending', comment="Status: pending, approved, rejected")
    
    # Decision tracking
    decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="When decision was made")
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Reason for rejection (if applicable)")
    
    __table_args__ = (
        Index('idx_pending_approvals_request_id', 'request_id'),
        Index('idx_pending_approvals_call_id', 'call_id'),
        Index('idx_pending_approvals_session_id', 'session_id'),
        Index('idx_pending_approvals_status', 'status'),
        Index('idx_pending_approvals_created_at', 'created_at'),
        Index('idx_pending_approvals_request_type', 'request_type'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses"""
        return {
            'request_id': self.request_id,
            'request_type': self.request_type,
            'subject': self.subject,
            'session_id': self.session_id,
            'details': self.details,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status,
            'decision_at': self.decision_at.isoformat() if self.decision_at else None,
            'decision_reason': self.decision_reason,
            # Legacy fields for backward compatibility
            'call_id': self.call_id,
            'tool_name': self.tool_name,
            'arguments': self.arguments,
        }
    
    def __repr__(self) -> str:
        return (
            f"<PendingApproval(request_id='{self.request_id}', "
            f"type='{self.request_type}', subject='{self.subject}', "
            f"session_id='{self.session_id}', status='{self.status}')>"
        )

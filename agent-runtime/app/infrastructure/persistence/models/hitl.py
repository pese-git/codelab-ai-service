"""
SQLAlchemy models for HITL (Human-in-the-Loop) persistence.

Contains:
- PendingApproval: Pending tool approval requests
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

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
    """
    __tablename__ = 'pending_approvals'
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    # Removed redundant approval_id - call_id is sufficient as unique identifier
    call_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="Tool call identifier (unique)")
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Session identifier")
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Name of the tool being called")
    arguments: Mapped[dict] = mapped_column(JSON, nullable=False, comment="Tool arguments as JSON")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Reason why approval is required")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), comment="When approval was requested")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending', comment="Status: pending, approved, rejected")
    
    __table_args__ = (
        Index('idx_pending_approvals_call_id', 'call_id'),
        Index('idx_pending_approvals_session_id', 'session_id'),
        Index('idx_pending_approvals_status', 'status'),
        Index('idx_pending_approvals_created_at', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses"""
        return {
            'call_id': self.call_id,
            'session_id': self.session_id,
            'tool_name': self.tool_name,
            'arguments': self.arguments,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status
        }
    
    def __repr__(self) -> str:
        return (
            f"<PendingApproval(call_id='{self.call_id}', "
            f"session_id='{self.session_id}', tool_name='{self.tool_name}', "
            f"status='{self.status}')>"
        )

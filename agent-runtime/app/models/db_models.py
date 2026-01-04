"""
SQLAlchemy database models for Agent Runtime.

This module contains ORM models for persistent storage.
"""
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PendingApproval(Base):
    """
    SQLAlchemy model for pending tool approval requests.
    
    Stores tool calls that require user approval (HITL - Human-in-the-Loop).
    This ensures approval requests persist across IDE restarts and reinstalls.
    """
    __tablename__ = 'pending_approvals'
    
    approval_id = Column(String(255), primary_key=True, comment="Unique approval identifier (same as call_id)")
    session_id = Column(String(255), nullable=False, comment="Session identifier")
    call_id = Column(String(255), nullable=False, comment="Tool call identifier")
    tool_name = Column(String(255), nullable=False, comment="Name of the tool being called")
    arguments = Column(JSONB, nullable=False, comment="Tool arguments as JSON")
    reason = Column(Text, nullable=True, comment="Reason why approval is required")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="When approval was requested")
    status = Column(String(50), nullable=False, default='pending', comment="Status: pending, approved, rejected")
    
    __table_args__ = (
        Index('idx_pending_approvals_session_id', 'session_id'),
        Index('idx_pending_approvals_status', 'status'),
        Index('idx_pending_approvals_created_at', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses"""
        return {
            'approval_id': self.approval_id,
            'session_id': self.session_id,
            'call_id': self.call_id,
            'tool_name': self.tool_name,
            'arguments': self.arguments,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status
        }
    
    def __repr__(self) -> str:
        return (
            f"<PendingApproval(approval_id='{self.approval_id}', "
            f"session_id='{self.session_id}', tool_name='{self.tool_name}', "
            f"status='{self.status}')>"
        )

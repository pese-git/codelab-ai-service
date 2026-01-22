"""
SQLAlchemy models for session and message persistence.

Contains:
- SessionModel: Session state
- MessageModel: Individual messages in session
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import String, Text, Integer, DateTime, Boolean, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class SessionModel(Base):
    """SQLAlchemy model for session state"""
    __tablename__ = "sessions"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    title: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Session title from first user message")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Session description from LLM summarization")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Soft delete
    
    # Relationships
    messages = relationship("MessageModel", back_populates="session",
                          cascade="all, delete-orphan", lazy="dynamic")
    agent_context = relationship("AgentContextModel", back_populates="session",
                                uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_session_activity', 'id', 'last_activity'),
        Index('idx_active_sessions', 'is_active', 'last_activity'),
    )
    
    @property
    def session_id(self) -> str:
        """Alias for id (backward compatibility)"""
        return self.id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "session_id": self.session_id,  # Uses @property
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "is_active": self.is_active,
            "deleted_at": self.deleted_at
        }


class MessageModel(Base):
    """SQLAlchemy model for individual messages"""
    __tablename__ = "messages"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    session_db_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Nullable for tool_calls messages
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # For tool names
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # For tool responses
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serialized tool calls
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serialized metadata
    
    # Relationship
    session = relationship("SessionModel", back_populates="messages")
    
    __table_args__ = (
        Index('idx_session_timestamp', 'session_db_id', 'timestamp'),
        Index('idx_role_timestamp', 'role', 'timestamp'),
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name='valid_role'
        ),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM API"""
        result = {
            "role": self.role,
        }
        
        # Content can be None for assistant messages with tool_calls
        if self.content is not None:
            result["content"] = self.content
        else:
            result["content"] = None
        
        if self.name:
            result["name"] = self.name
        
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        
        if self.tool_calls:
            result["tool_calls"] = json.loads(self.tool_calls)
        
        return result

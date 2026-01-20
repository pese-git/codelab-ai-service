"""
SQLAlchemy models for agent context persistence.

Contains:
- AgentContextModel: Agent context state
- AgentSwitchModel: Agent switch history
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class AgentContextModel(Base):
    """SQLAlchemy model for agent context"""
    __tablename__ = "agent_contexts"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    session_db_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"),
                          unique=True, nullable=False, index=True)
    current_agent: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    switch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serialized metadata
    
    # Relationships
    session = relationship("SessionModel", back_populates="agent_context")
    switches = relationship("AgentSwitchModel", back_populates="context", 
                          cascade="all, delete-orphan", lazy="dynamic")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "session_db_id": self.session_db_id,
            "current_agent": self.current_agent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "switch_count": self.switch_count,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {}
        }


class AgentSwitchModel(Base):
    """SQLAlchemy model for agent switch history"""
    __tablename__ = "agent_switches"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    context_db_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_contexts.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    from_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)  # NULL for first agent
    to_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    switched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serialized metadata
    
    # Relationship
    context = relationship("AgentContextModel", back_populates="switches")
    
    __table_args__ = (
        Index('idx_context_switched', 'context_db_id', 'switched_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "switched_at": self.switched_at,
            "reason": self.reason,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {}
        }

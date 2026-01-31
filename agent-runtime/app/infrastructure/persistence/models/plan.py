"""
SQLAlchemy models for plan and subtask persistence.

Contains:
- PlanModel: Plan state and metadata
- SubtaskModel: Individual subtasks in plan
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import String, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class PlanModel(Base):
    """SQLAlchemy model for plan state"""
    __tablename__ = "plans"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    # Foreign key to session
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Session this plan belongs to"
    )
    
    # Plan data
    goal: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Goal/description of the plan"
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        comment="Plan status: draft, approved, in_progress, completed, failed, cancelled"
    )
    
    current_subtask_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="ID of currently executing subtask"
    )
    
    # Metadata as JSON
    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional metadata as JSON"
    )
    
    # Timestamps
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When plan was approved"
    )
    
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When execution started"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When plan completed/failed/cancelled"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="When plan was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="When plan was last updated"
    )
    
    # Relationships
    subtasks = relationship(
        "SubtaskModel",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eager load subtasks with plan
        order_by="SubtaskModel.created_at"
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_plans_session_id', 'session_id'),
        Index('idx_plans_status', 'status'),
        Index('idx_plans_created_at', 'created_at'),
        Index('idx_plans_session_status', 'session_id', 'status'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        import json
        
        return {
            "id": self.id,
            "session_id": self.session_id,
            "goal": self.goal,
            "status": self.status,
            "current_subtask_id": self.current_subtask_id,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
            "approved_at": self.approved_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "subtasks": [st.to_dict() for st in self.subtasks] if self.subtasks else []
        }


class SubtaskModel(Base):
    """SQLAlchemy model for individual subtasks"""
    __tablename__ = "subtasks"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    # Foreign key to plan
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Plan this subtask belongs to"
    )
    
    # Subtask data
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description of the subtask"
    )
    
    agent: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Agent responsible for execution: coder, debug, ask"
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Subtask status: pending, running, done, failed, blocked"
    )
    
    # Dependencies as JSON array of subtask IDs
    dependencies_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        comment="Array of subtask IDs this depends on (JSON)"
    )
    
    estimated_time: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Estimated time to complete"
    )
    
    # Results
    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Result of execution (when done)"
    )
    
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message (when failed)"
    )
    
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When subtask execution started"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When subtask completed/failed"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="When subtask was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="When subtask was last updated"
    )
    
    # Relationship
    plan = relationship("PlanModel", back_populates="subtasks")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_subtasks_plan_id', 'plan_id'),
        Index('idx_subtasks_status', 'status'),
        Index('idx_subtasks_agent', 'agent'),
        Index('idx_subtasks_plan_status', 'plan_id', 'status'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        import json
        
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "description": self.description,
            "agent": self.agent,
            "status": self.status,
            "dependencies": json.loads(self.dependencies_json) if self.dependencies_json else [],
            "estimated_time": self.estimated_time,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

"""
SQLAlchemy model for FSM state persistence.

Stores FSM state for each session to maintain state across HTTP requests.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import String, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class FSMStateModel(Base):
    """
    SQLAlchemy model for FSM state persistence.
    
    Stores current FSM state and metadata for each session.
    This allows FSM state to persist across HTTP requests and service restarts.
    
    Attributes:
        id: Primary key (UUID)
        session_id: Foreign key to sessions table
        current_state: Current FSM state (e.g., 'idle', 'plan_review', etc.)
        metadata: JSON metadata for the FSM context
        created_at: When FSM context was created
        updated_at: When FSM state was last updated
    """
    __tablename__ = "fsm_states"
    
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
        unique=True,  # One FSM state per session
        index=True
    )
    
    # FSM state
    current_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="idle",
        index=True,
        comment="Current FSM state (idle, classify, plan_review, etc.)"
    )
    
    # Context metadata (JSON) - renamed from 'metadata' to avoid SQLAlchemy reserved name
    context_metadata: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="FSM context metadata"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationship to session
    session = relationship("SessionModel", backref="fsm_state")
    
    __table_args__ = (
        Index('idx_fsm_session_state', 'session_id', 'current_state'),
        Index('idx_fsm_state', 'current_state'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "current_state": self.current_state,
            "metadata": self.context_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

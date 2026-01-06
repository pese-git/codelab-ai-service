"""
SQLAlchemy database module for persistent session and agent context storage.

Provides thread-safe database operations for:
- Session state persistence
- Agent context persistence
- Message history storage (normalized)
- Agent switch history tracking
- Pending approval requests (HITL)

Improved version with:
- Normalized schema (separate tables for messages and switches)
- Foreign key relationships
- Better indexing
- Soft delete support
- Query optimization
"""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, String, Text, Integer, DateTime, Boolean,
    ForeignKey, Index, CheckConstraint, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship, Mapped, mapped_column
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSON as PGJSON
from sqlalchemy.types import JSON

logger = logging.getLogger("agent-runtime.database")

Base = declarative_base()


# ==================== Models ====================

class PendingApproval(Base):
    """
    SQLAlchemy model for pending tool approval requests.
    
    Stores tool calls that require user approval (HITL - Human-in-the-Loop).
    This ensures approval requests persist across IDE restarts and reinstalls.
    """
    __tablename__ = 'pending_approvals'
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    approval_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Unique approval identifier (same as call_id)")
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Session identifier")
    call_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Tool call identifier")
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Name of the tool being called")
    arguments: Mapped[dict] = mapped_column(JSON, nullable=False, comment="Tool arguments as JSON")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Reason why approval is required")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), comment="When approval was requested")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending', comment="Status: pending, approved, rejected")
    
    __table_args__ = (
        Index('idx_pending_approvals_approval_id', 'approval_id'),
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


class SessionModel(Base):
    """SQLAlchemy model for session state"""
    __tablename__ = "sessions"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Session title from first user message")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Session description from LLM summarization")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_activity: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # Soft delete
    
    # Relationships
    messages = relationship("MessageModel", back_populates="session", 
                          cascade="all, delete-orphan", lazy="dynamic")
    agent_context = relationship("AgentContextModel", back_populates="session", 
                                uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_session_activity', 'session_id', 'last_activity'),
        Index('idx_active_sessions', 'is_active', 'last_activity'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "session_id": self.session_id,
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
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
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
    switched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
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


# ==================== Database Class ====================

class Database:
    """
    Thread-safe SQLAlchemy database manager for agent runtime.
    
    Stores:
    - Session states with normalized message history
    - Agent contexts with switch history
    - Supports soft delete and query optimization
    """
    
    def __init__(self, db_url: str = "sqlite:///data/agent_runtime.db"):
        """
        Initialize database connection.
        
        Args:
            db_url: SQLAlchemy database URL
        """
        self.db_url = db_url
        
        # Ensure data directory exists for SQLite
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine with connection pooling
        if "sqlite" in db_url:
            self.engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False
            )
        else:
            self.engine = create_engine(
                db_url,
                pool_size=20,
                max_overflow=40,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False
            )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Initialize database schema
        self._init_schema()
        
        logger.info(f"Database initialized with URL: {db_url}")
    
    def _init_schema(self):
        """Initialize database schema"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database schema initialized")
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self):
        """Context manager for database sessions with automatic commit/rollback"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            session.close()
    
    # ==================== Session Operations ====================
    
    def save_session(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        last_activity: datetime
    ) -> None:
        """
        Save or update session state with messages.
        
        Uses atomic transaction to prevent data loss between delete and insert operations.
        Automatically sets title from first user message if not already set.
        
        Args:
            session_id: Session identifier
            messages: List of messages in the session
            last_activity: Last activity timestamp
        """
        with self.session_scope() as db:
            # Get or create session
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            is_new_session = False
            if not session:
                # Create new session
                session = SessionModel(
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc),
                    last_activity=last_activity,
                    is_active=True
                )
                db.add(session)
                db.flush()  # Get ID
                is_new_session = True
                logger.info(f"Created new session {session_id} in database")
            else:
                # Update existing session
                session.last_activity = last_activity
                session.is_active = True
                logger.debug(f"Updated session {session_id} in database")
            
            # Auto-set title from first user message if not already set
            if not session.title and messages:
                first_user_msg = next((msg for msg in messages if msg.get("role") == "user"), None)
                if first_user_msg and first_user_msg.get("content"):
                    # Take first 500 chars as title
                    content = first_user_msg["content"]
                    session.title = content[:500] if len(content) > 500 else content
                    logger.debug(f"Auto-set title for session {session_id}")
            
            # Atomic replacement: prepare new messages first, then replace in single transaction
            # This ensures we don't lose data if operation fails midway
            new_messages = []
            for msg in messages:
                # Content can be None for assistant messages with tool_calls
                content = msg.get("content")
                if content is None and msg.get("tool_calls"):
                    # For tool_calls messages, content can be None or empty string
                    content = None
                elif content is None:
                    # For other messages, use empty string as default
                    content = ""
                
                message = MessageModel(
                    session_db_id=session.id,
                    role=msg.get("role", "user"),
                    content=content,
                    timestamp=datetime.now(timezone.utc),
                    name=msg.get("name"),
                    tool_call_id=msg.get("tool_call_id"),
                    tool_calls=json.dumps(msg["tool_calls"]) if msg.get("tool_calls") else None,
                    metadata_json=json.dumps(msg.get("metadata", {})) if msg.get("metadata") else None
                )
                new_messages.append(message)
            
            # Now perform atomic replacement within the same transaction
            # Delete old messages and add new ones - all commits together
            db.query(MessageModel).filter(
                MessageModel.session_db_id == session.id
            ).delete()
            
            # Add all new messages
            for message in new_messages:
                db.add(message)
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session state from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data dict with messages or None if not found
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session:
                return None
            
            # Load messages
            messages = db.query(MessageModel).filter(
                MessageModel.session_db_id == session.id
            ).order_by(MessageModel.timestamp.asc()).all()
            
            return {
                "session_id": session.session_id,
                "messages": [msg.to_dict() for msg in messages],
                "last_activity": session.last_activity,
                "created_at": session.created_at
            }
    
    def delete_session(self, session_id: str, soft: bool = True) -> bool:
        """
        Delete session from database.
        
        Args:
            session_id: Session identifier
            soft: If True, perform soft delete; if False, hard delete
            
        Returns:
            True if deleted, False if not found
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            if not session:
                return False
            
            if soft:
                # Soft delete
                session.deleted_at = datetime.now(timezone.utc)
                session.is_active = False
                logger.info(f"Soft deleted session {session_id} from database")
            else:
                # Hard delete (cascade will delete messages and context)
                db.delete(session)
                logger.info(f"Hard deleted session {session_id} from database")
            
            return True
    
    def list_all_sessions(self, include_deleted: bool = False) -> List[str]:
        """
        Get list of all session IDs.
        
        Args:
            include_deleted: Include soft-deleted sessions
            
        Returns:
            List of session IDs
        """
        with self.session_scope() as db:
            query = db.query(SessionModel.session_id)
            
            if not include_deleted:
                query = query.filter(SessionModel.deleted_at.is_(None))
            
            sessions = query.all()
            return [s[0] for s in sessions]
    
    def get_messages_paginated(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get paginated messages for a session.
        
        Args:
            session_id: Session identifier
            page: Page number (1-indexed)
            page_size: Number of messages per page
            
        Returns:
            List of message dictionaries
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session:
                return []
            
            offset = (page - 1) * page_size
            messages = db.query(MessageModel).filter(
                MessageModel.session_db_id == session.id
            ).order_by(
                MessageModel.timestamp.asc()
            ).limit(page_size).offset(offset).all()
            
            return [msg.to_dict() for msg in messages]
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with stats or None if session not found
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session:
                return None
            
            stats = db.query(
                func.count(MessageModel.id).label('message_count'),
                func.sum(MessageModel.token_count).label('total_tokens'),
                func.max(MessageModel.timestamp).label('last_message_at')
            ).filter(
                MessageModel.session_db_id == session.id
            ).first()
            
            return {
                "session_id": session_id,
                "message_count": stats.message_count or 0,
                "total_tokens": stats.total_tokens or 0,
                "last_message_at": stats.last_message_at,
                "created_at": session.created_at,
                "last_activity": session.last_activity
            }
    
    # ==================== Agent Context Operations ====================
    
    def save_agent_context(
        self,
        session_id: str,
        current_agent: str,
        agent_history: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        created_at: datetime,
        last_switch_at: Optional[datetime],
        switch_count: int
    ) -> None:
        """
        Save or update agent context.
        
        Args:
            session_id: Session identifier
            current_agent: Current active agent type
            agent_history: History of agent switches (for backward compatibility)
            metadata: Additional metadata
            created_at: Context creation timestamp
            last_switch_at: Last switch timestamp
            switch_count: Number of switches
        """
        with self.session_scope() as db:
            # Get session
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session:
                logger.error(f"Cannot save agent context: session {session_id} not found")
                return
            
            # Get or create context
            context = db.query(AgentContextModel).filter(
                AgentContextModel.session_db_id == session.id
            ).first()
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            if not context:
                # Create new context
                context = AgentContextModel(
                    session_db_id=session.id,
                    current_agent=current_agent,
                    created_at=created_at,
                    updated_at=datetime.now(timezone.utc),
                    switch_count=switch_count,
                    metadata_json=metadata_json
                )
                db.add(context)
                db.flush()  # Get ID
                logger.info(f"Created new agent context for {session_id} in database")
            else:
                # Update existing context
                context.current_agent = current_agent
                context.updated_at = datetime.now(timezone.utc)
                context.switch_count = switch_count
                context.metadata_json = metadata_json
                logger.debug(f"Updated agent context for {session_id} in database")
            
            # Sync agent_history to switches table (for backward compatibility)
            # Clear existing switches and recreate from history
            db.query(AgentSwitchModel).filter(
                AgentSwitchModel.context_db_id == context.id
            ).delete()
            
            for history_entry in agent_history:
                switch = AgentSwitchModel(
                    context_db_id=context.id,
                    from_agent=history_entry.get("from"),
                    to_agent=history_entry.get("to", current_agent),
                    switched_at=datetime.fromisoformat(history_entry["timestamp"])
                               if "timestamp" in history_entry else datetime.now(timezone.utc),
                    reason=history_entry.get("reason"),
                    metadata_json=json.dumps(history_entry.get("metadata", {}))
                                 if history_entry.get("metadata") else None
                )
                db.add(switch)
    
    def load_agent_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load agent context from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Agent context data dict or None if not found
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session:
                return None
            
            context = db.query(AgentContextModel).filter(
                AgentContextModel.session_db_id == session.id
            ).first()
            
            if not context:
                return None
            
            # Load switch history
            switches = db.query(AgentSwitchModel).filter(
                AgentSwitchModel.context_db_id == context.id
            ).order_by(AgentSwitchModel.switched_at.asc()).all()
            
            # Convert switches to agent_history format for backward compatibility
            agent_history = []
            for switch in switches:
                agent_history.append({
                    "from": switch.from_agent,
                    "to": switch.to_agent,
                    "reason": switch.reason,
                    "timestamp": switch.switched_at.isoformat()
                })
            
            return {
                "session_id": session_id,
                "current_agent": context.current_agent,
                "agent_history": agent_history,
                "metadata": json.loads(context.metadata_json) if context.metadata_json else {},
                "created_at": context.created_at,
                "last_switch_at": switches[-1].switched_at if switches else None,
                "switch_count": context.switch_count
            }
    
    def delete_agent_context(self, session_id: str) -> bool:
        """
        Delete agent context from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            if not session:
                return False
            
            context = db.query(AgentContextModel).filter(
                AgentContextModel.session_db_id == session.id
            ).first()
            
            if not context:
                return False
            
            # Cascade will delete switches
            db.delete(context)
            logger.info(f"Deleted agent context for {session_id} from database")
            return True
    
    def list_all_contexts(self) -> List[str]:
        """
        Get list of all session IDs with agent contexts.
        
        Returns:
            List of session IDs
        """
        with self.session_scope() as db:
            results = db.query(SessionModel.session_id).join(
                AgentContextModel,
                SessionModel.id == AgentContextModel.session_db_id
            ).filter(
                SessionModel.deleted_at.is_(None)
            ).all()
            
            return [r[0] for r in results]
    
    def get_agent_switch_history(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get agent switch history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of switches to return
            
        Returns:
            List of switch records
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session or not session.agent_context:
                return []
            
            switches = db.query(AgentSwitchModel).filter(
                AgentSwitchModel.context_db_id == session.agent_context.id
            ).order_by(
                AgentSwitchModel.switched_at.desc()
            ).limit(limit).all()
            
            return [switch.to_dict() for switch in switches]
    
    # ==================== Cleanup Operations ====================
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old inactive sessions (soft delete).
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        with self.session_scope() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            
            # Soft delete old sessions
            sessions_updated = db.query(SessionModel).filter(
                SessionModel.last_activity < cutoff,
                SessionModel.deleted_at.is_(None)
            ).update({
                "deleted_at": datetime.now(timezone.utc),
                "is_active": False
            }, synchronize_session=False)
            
            if sessions_updated > 0:
                logger.info(f"Soft deleted {sessions_updated} old sessions")
            
            return sessions_updated
    
    def hard_delete_old_sessions(self, days_old: int = 30) -> int:
        """
        Permanently delete sessions that were soft-deleted long ago.
        
        Args:
            days_old: Delete sessions soft-deleted more than this many days ago
            
        Returns:
            Number of sessions permanently deleted
        """
        with self.session_scope() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            # Hard delete old soft-deleted sessions
            sessions_deleted = db.query(SessionModel).filter(
                SessionModel.deleted_at < cutoff
            ).delete(synchronize_session=False)
            
            if sessions_deleted > 0:
                logger.info(f"Permanently deleted {sessions_deleted} old sessions")
            
            return sessions_deleted
    
    # ==================== Pending Approval Operations ====================
    
    def save_pending_approval(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: Optional[str] = None
    ) -> None:
        """
        Save pending approval request to database.
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier (used as approval_id)
            tool_name: Name of the tool requiring approval
            arguments: Tool arguments
            reason: Reason why approval is required
        """
        with self.session_scope() as db:
            # Check if approval already exists
            existing = db.query(PendingApproval).filter(
                PendingApproval.call_id == call_id
            ).first()
            
            if existing:
                logger.warning(f"Pending approval already exists for call_id={call_id}")
                return
            
            # Create new pending approval
            approval = PendingApproval(
                approval_id=call_id,  # Use call_id as approval_id
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,  # SQLAlchemy handles JSONB serialization
                reason=reason,
                status='pending'
            )
            
            db.add(approval)
            logger.info(f"Saved pending approval: session={session_id}, call_id={call_id}, tool={tool_name}")
    
    def get_pending_approvals(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all pending approval requests for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of pending approval dictionaries
        """
        with self.session_scope() as db:
            approvals = db.query(PendingApproval).filter(
                PendingApproval.session_id == session_id,
                PendingApproval.status == 'pending'
            ).order_by(PendingApproval.created_at.asc()).all()
            
            return [
                {
                    'call_id': approval.call_id,
                    'tool_name': approval.tool_name,
                    'arguments': approval.arguments,  # JSONB auto-deserialized
                    'reason': approval.reason,
                    'created_at': approval.created_at
                }
                for approval in approvals
            ]
    
    def delete_pending_approval(self, call_id: str) -> bool:
        """
        Delete pending approval request from database.
        
        Args:
            call_id: Tool call identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self.session_scope() as db:
            approval = db.query(PendingApproval).filter(
                PendingApproval.call_id == call_id
            ).first()
            
            if not approval:
                logger.warning(f"Pending approval not found for call_id={call_id}")
                return False
            
            db.delete(approval)
            logger.info(f"Deleted pending approval: call_id={call_id}")
            return True
    
    def update_approval_status(
        self,
        call_id: str,
        status: str
    ) -> bool:
        """
        Update status of pending approval.
        
        Args:
            call_id: Tool call identifier
            status: New status (approved, rejected, cancelled)
            
        Returns:
            True if updated, False if not found
        """
        with self.session_scope() as db:
            approval = db.query(PendingApproval).filter(
                PendingApproval.call_id == call_id
            ).first()
            
            if not approval:
                logger.warning(f"Pending approval not found for call_id={call_id}")
                return False
            
            approval.status = status
            logger.info(f"Updated approval status: call_id={call_id}, status={status}")
            return True


    def update_session_title(self, session_id: str, title: str) -> bool:
        """
        Update session title.
        
        Args:
            session_id: Session identifier
            title: New title (will be truncated to 500 chars)
            
        Returns:
            True if updated, False if session not found
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session:
                logger.warning(f"Session not found for title update: {session_id}")
                return False
            
            session.title = title[:500] if len(title) > 500 else title
            logger.info(f"Updated title for session {session_id}")
            return True
    
    def update_session_description(self, session_id: str, description: str) -> bool:
        """
        Update session description (typically from LLM summarization).
        
        Args:
            session_id: Session identifier
            description: New description from LLM
            
        Returns:
            True if updated, False if session not found
        """
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id,
                SessionModel.deleted_at.is_(None)
            ).first()
            
            if not session:
                logger.warning(f"Session not found for description update: {session_id}")
                return False
            
            session.description = description
            logger.info(f"Updated description for session {session_id}")
            return True


# ==================== Dependency Injection ====================

_database_instance: Optional[Database] = None


def get_database() -> Database:
    """
    Get database instance for dependency injection.
    
    Returns:
        Database instance
    """
    global _database_instance
    if _database_instance is None:
        _database_instance = Database()
    return _database_instance


def get_db() -> Database:
    """Get database instance (convenience wrapper)"""
    return get_database()

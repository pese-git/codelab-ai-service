"""
SQLAlchemy database module for persistent session and agent context storage.

Provides async database operations for:
- Session state persistence
- Agent context persistence
- Message history storage (normalized)
- Agent switch history tracking
- Pending approval requests (HITL)

Improved version with:
- Async SQLAlchemy support (like auth-service)
- Normalized schema (separate tables for messages and switches)
- Foreign key relationships
- Better indexing
- Soft delete support
- Query optimization
- Proper dependency injection pattern
"""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import (
    create_engine, String, Text, Integer, DateTime, Boolean,
    ForeignKey, Index, CheckConstraint, func, event
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
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


# ==================== Database Configuration ====================

# Database URL from config
db_url = None
async_db_url = None
engine = None
async_session_maker = None


def init_database(database_url: str):
    """
    Initialize database engine and session maker.
    
    Args:
        database_url: SQLAlchemy database URL
    """
    global db_url, async_db_url, engine, async_session_maker
    
    db_url = database_url
    
    # Ensure data directory exists for SQLite
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # Convert sqlite:/// to sqlite+aiosqlite:///
        async_db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif db_url.startswith("postgresql://"):
        # Convert postgresql:// to postgresql+asyncpg://
        async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_db_url = db_url
    
    # Create async engine
    engine = create_async_engine(
        async_db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    
    # Create async session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info(f"Database initialized with URL: {db_url}")


# Enable WAL mode for SQLite (for better concurrency)
if db_url and "sqlite" in db_url:
    sync_engine = create_engine(
        db_url,
        echo=False,
    )

    @event.listens_for(sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Set SQLite pragmas for better performance"""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
        cursor.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.
    
    Yields:
        AsyncSession: Database session
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database (create tables)"""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database schema initialized")


async def close_db():
    """Close database connections"""
    if engine is not None:
        await engine.dispose()
        logger.info("Database connections closed")


# ==================== Database Service Class ====================

class DatabaseService:
    """
    Async database service for agent runtime.
    
    Provides high-level operations for:
    - Session management
    - Agent context management
    - Message history
    - Pending approvals
    """
    
    def __init__(self):
        """Initialize database service"""
        pass
    
    # ==================== Session Operations ====================
    
    async def save_session(
        self,
        db: AsyncSession,
        session_id: str,
        messages: List[Dict[str, Any]],
        last_activity: datetime
    ) -> None:
        """
        Save or update session state with messages.
        
        Uses atomic transaction to prevent data loss between delete and insert operations.
        Automatically sets title from first user message if not already set.
        
        Args:
            db: Database session
            session_id: Session identifier
            messages: List of messages in the session
            last_activity: Last activity timestamp
        """
        from sqlalchemy import select
        
        # Get or create session
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.deleted_at.is_(None)
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            # Create new session
            session = SessionModel(
                id=session_id,
                created_at=datetime.now(timezone.utc),
                last_activity=last_activity,
                is_active=True
            )
            db.add(session)
            await db.flush()  # Get ID
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
        new_messages = []
        for msg in messages:
            # Content can be None for assistant messages with tool_calls
            content = msg.get("content")
            if content is None and msg.get("tool_calls"):
                content = None
            elif content is None:
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
        
        # Delete old messages and add new ones
        from sqlalchemy import delete
        await db.execute(
            delete(MessageModel).where(MessageModel.session_db_id == session.id)
        )
        
        # Add all new messages
        for message in new_messages:
            db.add(message)
        
        await db.commit()
    
    async def load_session(self, db: AsyncSession, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session state from database.
        
        Args:
            db: Database session
            session_id: Session identifier
            
        Returns:
            Session data dict with messages or None if not found
        """
        from sqlalchemy import select
        
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.deleted_at.is_(None)
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        # Load messages
        result = await db.execute(
            select(MessageModel)
            .where(MessageModel.session_db_id == session.id)
            .order_by(MessageModel.timestamp.asc())
        )
        messages = result.scalars().all()
        
        return {
            "session_id": session.id,
            "messages": [msg.to_dict() for msg in messages],
            "last_activity": session.last_activity,
            "created_at": session.created_at
        }
    
    async def delete_session(self, db: AsyncSession, session_id: str, soft: bool = True) -> bool:
        """
        Delete session from database.
        
        Args:
            db: Database session
            session_id: Session identifier
            soft: If True, perform soft delete; if False, hard delete
            
        Returns:
            True if deleted, False if not found
        """
        from sqlalchemy import select
        
        result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return False
        
        if soft:
            # Soft delete
            session.deleted_at = datetime.now(timezone.utc)
            session.is_active = False
            logger.info(f"Soft deleted session {session_id} from database")
        else:
            # Hard delete (cascade will delete messages and context)
            await db.delete(session)
            logger.info(f"Hard deleted session {session_id} from database")
        
        await db.commit()
        return True
    
    async def list_all_sessions(self, db: AsyncSession, include_deleted: bool = False) -> List[str]:
        """
        Get list of all session IDs.
        
        Args:
            db: Database session
            include_deleted: Include soft-deleted sessions
            
        Returns:
            List of session IDs
        """
        from sqlalchemy import select
        
        query = select(SessionModel.id)
        
        if not include_deleted:
            query = query.where(SessionModel.deleted_at.is_(None))
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        return list(sessions)
    
    # ==================== Agent Context Operations ====================
    
    async def save_agent_context(
        self,
        db: AsyncSession,
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
            db: Database session
            session_id: Session identifier
            current_agent: Current active agent type
            agent_history: History of agent switches
            metadata: Additional metadata
            created_at: Context creation timestamp
            last_switch_at: Last switch timestamp
            switch_count: Number of switches
        """
        from sqlalchemy import select, delete
        
        # Get session
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.deleted_at.is_(None)
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            logger.error(f"Cannot save agent context: session {session_id} not found")
            return
        
        # Get or create context
        result = await db.execute(
            select(AgentContextModel).where(AgentContextModel.session_db_id == session.id)
        )
        context = result.scalar_one_or_none()
        
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
            await db.flush()
            logger.info(f"Created new agent context for {session_id} in database")
        else:
            # Update existing context
            context.current_agent = current_agent
            context.updated_at = datetime.now(timezone.utc)
            context.switch_count = switch_count
            context.metadata_json = metadata_json
            logger.debug(f"Updated agent context for {session_id} in database")
        
        # Sync agent_history to switches table
        await db.execute(
            delete(AgentSwitchModel).where(AgentSwitchModel.context_db_id == context.id)
        )
        
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
        
        await db.commit()
    
    async def load_agent_context(self, db: AsyncSession, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load agent context from database.
        
        Args:
            db: Database session
            session_id: Session identifier
            
        Returns:
            Agent context data dict or None if not found
        """
        from sqlalchemy import select
        
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.deleted_at.is_(None)
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        result = await db.execute(
            select(AgentContextModel).where(AgentContextModel.session_db_id == session.id)
        )
        context = result.scalar_one_or_none()
        
        if not context:
            return None
        
        # Load switch history
        result = await db.execute(
            select(AgentSwitchModel)
            .where(AgentSwitchModel.context_db_id == context.id)
            .order_by(AgentSwitchModel.switched_at.asc())
        )
        switches = result.scalars().all()
        
        # Convert switches to agent_history format
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
    
    # ==================== Pending Approval Operations ====================
    
    async def save_pending_approval(
        self,
        db: AsyncSession,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: Optional[str] = None
    ) -> None:
        """
        Save pending approval request to database.
        
        Args:
            db: Database session
            session_id: Session identifier
            call_id: Tool call identifier (unique)
            tool_name: Name of the tool requiring approval
            arguments: Tool arguments
            reason: Reason why approval is required
        """
        from sqlalchemy import select
        
        # Check if approval already exists
        result = await db.execute(
            select(PendingApproval).where(PendingApproval.call_id == call_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.warning(f"Pending approval already exists for call_id={call_id}")
            return
        
        # Create new pending approval
        approval = PendingApproval(
            session_id=session_id,
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            status='pending'
        )
        
        db.add(approval)
        await db.commit()
        logger.info(f"Saved pending approval: session={session_id}, call_id={call_id}, tool={tool_name}")
    
    async def get_pending_approvals(self, db: AsyncSession, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all pending approval requests for a session.
        
        Args:
            db: Database session
            session_id: Session identifier
            
        Returns:
            List of pending approval dictionaries
        """
        from sqlalchemy import select
        
        result = await db.execute(
            select(PendingApproval)
            .where(
                PendingApproval.session_id == session_id,
                PendingApproval.status == 'pending'
            )
            .order_by(PendingApproval.created_at.asc())
        )
        approvals = result.scalars().all()
        
        return [
            {
                'call_id': approval.call_id,
                'tool_name': approval.tool_name,
                'arguments': approval.arguments,
                'reason': approval.reason,
                'created_at': approval.created_at
            }
            for approval in approvals
        ]
    
    async def delete_pending_approval(self, db: AsyncSession, call_id: str) -> bool:
        """
        Delete pending approval request from database.
        
        Args:
            db: Database session
            call_id: Tool call identifier
            
        Returns:
            True if deleted, False if not found
        """
        from sqlalchemy import select
        
        result = await db.execute(
            select(PendingApproval).where(PendingApproval.call_id == call_id)
        )
        approval = result.scalar_one_or_none()
        
        if not approval:
            logger.warning(f"Pending approval not found for call_id={call_id}")
            return False
        
        await db.delete(approval)
        await db.commit()
        logger.info(f"Deleted pending approval: call_id={call_id}")
        return True


# ==================== Dependency Injection ====================

_database_service: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """
    Get database service instance for dependency injection.
    
    Returns:
        DatabaseService instance
    """
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service


# ==================== Backward Compatibility ====================

class Database:
    """
    Backward compatibility wrapper for old synchronous code.
    
    This class provides a synchronous interface to the async database
    for legacy code that hasn't been migrated yet.
    
    ⚠️ DEPRECATED: Use DatabaseService with async/await instead.
    """
    
    def __init__(self, db_url: str = None):
        """Initialize database wrapper"""
        if db_url:
            logger.warning(
                "Database class is deprecated. "
                "Use DatabaseService with async/await instead."
            )
        self._db_service = get_database_service()
    
    def _run_async(self, coro):
        """Run async coroutine in sync context"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    async def _get_db_session(self):
        """Get database session"""
        async for db in get_db():
            return db
    
    def save_session(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        last_activity: datetime
    ) -> None:
        """Sync wrapper for save_session"""
        async def _save():
            async for db in get_db():
                await self._db_service.save_session(
                    db, session_id, messages, last_activity
                )
                break
        
        self._run_async(_save())
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for load_session"""
        async def _load():
            async for db in get_db():
                result = await self._db_service.load_session(db, session_id)
                return result
        
        return self._run_async(_load())
    
    def delete_session(self, session_id: str, soft: bool = True) -> bool:
        """Sync wrapper for delete_session"""
        async def _delete():
            async for db in get_db():
                result = await self._db_service.delete_session(db, session_id, soft)
                return result
        
        return self._run_async(_delete())
    
    def list_all_sessions(self, include_deleted: bool = False) -> List[str]:
        """Sync wrapper for list_all_sessions"""
        async def _list():
            async for db in get_db():
                result = await self._db_service.list_all_sessions(db, include_deleted)
                return result
        
        return self._run_async(_list())
    
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
        """Sync wrapper for save_agent_context"""
        async def _save():
            async for db in get_db():
                await self._db_service.save_agent_context(
                    db, session_id, current_agent, agent_history,
                    metadata, created_at, last_switch_at, switch_count
                )
                break
        
        self._run_async(_save())
    
    def load_agent_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for load_agent_context"""
        async def _load():
            async for db in get_db():
                result = await self._db_service.load_agent_context(db, session_id)
                return result
        
        return self._run_async(_load())
    
    def delete_agent_context(self, session_id: str) -> bool:
        """Sync wrapper for delete_agent_context"""
        async def _delete():
            async for db in get_db():
                # Используем delete_session для удаления контекста
                from sqlalchemy import select, delete as sql_delete
                result = await db.execute(
                    select(SessionModel).where(SessionModel.id == session_id)
                )
                session = result.scalar_one_or_none()
                
                if not session:
                    return False
                
                result = await db.execute(
                    select(AgentContextModel).where(
                        AgentContextModel.session_db_id == session.id
                    )
                )
                context = result.scalar_one_or_none()
                
                if not context:
                    return False
                
                await db.delete(context)
                await db.commit()
                return True
        
        return self._run_async(_delete())
    
    def list_all_contexts(self) -> List[str]:
        """Sync wrapper for list_all_contexts"""
        async def _list():
            async for db in get_db():
                from sqlalchemy import select
                result = await db.execute(
                    select(SessionModel.id).join(
                        AgentContextModel,
                        SessionModel.id == AgentContextModel.session_db_id
                    ).where(
                        SessionModel.deleted_at.is_(None)
                    )
                )
                sessions = result.scalars().all()
                return list(sessions)
        
        return self._run_async(_list())
    
    def save_pending_approval(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: Optional[str] = None
    ) -> None:
        """Sync wrapper for save_pending_approval"""
        async def _save():
            async for db in get_db():
                await self._db_service.save_pending_approval(
                    db, session_id, call_id, tool_name, arguments, reason
                )
                break
        
        self._run_async(_save())
    
    def get_pending_approvals(self, session_id: str) -> List[Dict[str, Any]]:
        """Sync wrapper for get_pending_approvals"""
        async def _get():
            async for db in get_db():
                result = await self._db_service.get_pending_approvals(db, session_id)
                return result
        
        return self._run_async(_get())
    
    def delete_pending_approval(self, call_id: str) -> bool:
        """Sync wrapper for delete_pending_approval"""
        async def _delete():
            async for db in get_db():
                result = await self._db_service.delete_pending_approval(db, call_id)
                return result
        
        return self._run_async(_delete())
    
    @contextmanager
    def session_scope(self):
        """
        Deprecated context manager for backward compatibility.
        
        ⚠️ This is a no-op for compatibility. Operations are executed immediately.
        """
        logger.warning(
            "session_scope() is deprecated and does nothing. "
            "Operations are executed immediately."
        )
        yield self


def get_db_legacy() -> Database:
    """
    Get Database instance for legacy code.
    
    ⚠️ DEPRECATED: Use get_database_service() instead.
    """
    return Database()


# Alias for backward compatibility
get_database = get_db_legacy

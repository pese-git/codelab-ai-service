"""
Database configuration and service for agent runtime.

Provides:
- Database initialization (init_database, init_db, close_db)
- Async session management (get_db)
- DatabaseService for high-level operations
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy import create_engine, select, delete, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .models import (
    Base,
    SessionModel,
    MessageModel,
    AgentContextModel,
    AgentSwitchModel,
    PendingApproval
)

logger = logging.getLogger("agent-runtime.infrastructure.persistence.database")

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
    
    # Create async engine with SQLite-specific configuration
    if "sqlite" in async_db_url:
        # Configure SQLite WAL mode via event listener on async engine
        engine = create_async_engine(
            async_db_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            """Set SQLite pragmas for better performance"""
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
            cursor.close()
        
        logger.info("SQLite WAL mode and performance pragmas configured")
    else:
        # Create async engine for non-SQLite databases
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
            logger.debug(f"[DEBUG] get_db(): Session created, yielding to handler")
            yield session
            logger.info(f"[DEBUG] get_db(): Handler completed, committing transaction NOW")
            await session.commit()
            logger.info(f"[DEBUG] get_db(): Transaction committed successfully")
        except Exception as e:
            logger.error(f"[DEBUG] get_db(): Exception occurred, rolling back: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug(f"[DEBUG] get_db(): Session closed")


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
        
        metadata_json = json.dumps(metadata, default=str) if metadata else None
        
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

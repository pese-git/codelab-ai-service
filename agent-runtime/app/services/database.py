"""
SQLAlchemy database module for persistent session and agent context storage.

Provides thread-safe database operations for:
- Session state persistence
- Agent context persistence
- Message history storage
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy import (
    create_engine, Column, String, Text, Integer, DateTime, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool

logger = logging.getLogger("agent-runtime.database")

Base = declarative_base()


class SessionModel(Base):
    """SQLAlchemy model for session state"""
    __tablename__ = "sessions"
    
    session_id = Column(String, primary_key=True)
    messages = Column(Text, nullable=False)  # JSON serialized
    last_activity = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "messages": json.loads(self.messages),
            "last_activity": self.last_activity,
            "created_at": self.created_at
        }


class AgentContextModel(Base):
    """SQLAlchemy model for agent context"""
    __tablename__ = "agent_contexts"
    
    session_id = Column(String, primary_key=True)
    current_agent = Column(String, nullable=False)
    agent_history = Column(Text, nullable=False)  # JSON serialized
    context_metadata = Column(Text, nullable=False)  # JSON serialized (renamed from metadata)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    last_switch_at = Column(DateTime, nullable=True, index=True)
    switch_count = Column(Integer, nullable=False, default=0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "current_agent": self.current_agent,
            "agent_history": json.loads(self.agent_history),
            "metadata": json.loads(self.context_metadata),
            "created_at": self.created_at,
            "last_switch_at": self.last_switch_at,
            "switch_count": self.switch_count
        }


class Database:
    """
    Thread-safe SQLAlchemy database manager for agent runtime.
    
    Stores:
    - Session states with message history
    - Agent contexts with switch history
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
        # For SQLite, use StaticPool to avoid threading issues
        if "sqlite" in db_url:
            self.engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False
            )
        else:
            self.engine = create_engine(db_url, echo=False)
        
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
    
    # ==================== Session Operations ====================
    
    def save_session(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        last_activity: datetime
    ) -> None:
        """
        Save or update session state.
        
        Args:
            session_id: Session identifier
            messages: List of messages in the session
            last_activity: Last activity timestamp
        """
        db = self.get_session()
        try:
            # Check if session exists
            existing = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            messages_json = json.dumps(messages)
            
            if existing:
                # Update existing session
                existing.messages = messages_json
                existing.last_activity = last_activity
                logger.debug(f"Updated session {session_id} in database")
            else:
                # Create new session
                new_session = SessionModel(
                    session_id=session_id,
                    messages=messages_json,
                    last_activity=last_activity,
                    created_at=datetime.now()
                )
                db.add(new_session)
                logger.info(f"Created new session {session_id} in database")
            
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving session {session_id}: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session state from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data dict or None if not found
        """
        db = self.get_session()
        try:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            if session:
                return session.to_dict()
            
            return None
        finally:
            db.close()
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        db = self.get_session()
        try:
            deleted = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).delete()
            db.commit()
            
            if deleted:
                logger.info(f"Deleted session {session_id} from database")
            
            return deleted > 0
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting session {session_id}: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    def list_all_sessions(self) -> List[str]:
        """
        Get list of all session IDs.
        
        Returns:
            List of session IDs
        """
        db = self.get_session()
        try:
            sessions = db.query(SessionModel.session_id).all()
            return [s[0] for s in sessions]
        finally:
            db.close()
    
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
            agent_history: History of agent switches
            metadata: Additional metadata
            created_at: Context creation timestamp
            last_switch_at: Last switch timestamp
            switch_count: Number of switches
        """
        db = self.get_session()
        try:
            # Check if context exists
            existing = db.query(AgentContextModel).filter(
                AgentContextModel.session_id == session_id
            ).first()
            
            agent_history_json = json.dumps(agent_history)
            metadata_json = json.dumps(metadata)
            
            if existing:
                # Update existing context
                existing.current_agent = current_agent
                existing.agent_history = agent_history_json
                existing.context_metadata = metadata_json
                existing.last_switch_at = last_switch_at
                existing.switch_count = switch_count
                logger.debug(f"Updated agent context for {session_id} in database")
            else:
                # Create new context
                new_context = AgentContextModel(
                    session_id=session_id,
                    current_agent=current_agent,
                    agent_history=agent_history_json,
                    context_metadata=metadata_json,
                    created_at=created_at,
                    last_switch_at=last_switch_at,
                    switch_count=switch_count
                )
                db.add(new_context)
                logger.info(f"Created new agent context for {session_id} in database")
            
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving agent context {session_id}: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    def load_agent_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load agent context from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Agent context data dict or None if not found
        """
        db = self.get_session()
        try:
            context = db.query(AgentContextModel).filter(
                AgentContextModel.session_id == session_id
            ).first()
            
            if context:
                return context.to_dict()
            
            return None
        finally:
            db.close()
    
    def delete_agent_context(self, session_id: str) -> bool:
        """
        Delete agent context from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        db = self.get_session()
        try:
            deleted = db.query(AgentContextModel).filter(
                AgentContextModel.session_id == session_id
            ).delete()
            db.commit()
            
            if deleted:
                logger.info(f"Deleted agent context for {session_id} from database")
            
            return deleted > 0
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting agent context {session_id}: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    def list_all_contexts(self) -> List[str]:
        """
        Get list of all session IDs with agent contexts.
        
        Returns:
            List of session IDs
        """
        db = self.get_session()
        try:
            contexts = db.query(AgentContextModel.session_id).all()
            return [c[0] for c in contexts]
        finally:
            db.close()
    
    # ==================== Cleanup Operations ====================
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old inactive sessions and their contexts.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        db = self.get_session()
        try:
            # Calculate cutoff time
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            
            # Delete old sessions
            sessions_deleted = db.query(SessionModel).filter(
                SessionModel.last_activity < cutoff
            ).delete()
            
            # Delete orphaned contexts (sessions that no longer exist)
            subquery = db.query(SessionModel.session_id).subquery()
            contexts_deleted = db.query(AgentContextModel).filter(
                ~AgentContextModel.session_id.in_(subquery)
            ).delete(synchronize_session=False)
            
            db.commit()
            
            if sessions_deleted > 0 or contexts_deleted > 0:
                logger.info(
                    f"Cleaned up {sessions_deleted} old sessions and "
                    f"{contexts_deleted} orphaned contexts"
                )
            
            return sessions_deleted
        except Exception as e:
            db.rollback()
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            raise
        finally:
            db.close()


# Database instance factory for dependency injection
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


# Convenience function for non-DI contexts
def get_db() -> Database:
    """Get database instance (convenience wrapper)"""
    return get_database()

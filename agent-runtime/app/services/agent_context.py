"""
Agent context management for multi-agent system.

Maintains state and history for each agent session.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from app.agents.base_agent import AgentType
from app.services.database import Database, get_db

logger = logging.getLogger("agent-runtime.agent_context")


class AgentContext(BaseModel):
    """
    Context for an agent working within a session.
    
    Tracks:
    - Current active agent
    - History of agent switches
    - Additional metadata
    """
    
    session_id: str = Field(description="Session identifier")
    current_agent: AgentType = Field(
        default=AgentType.ORCHESTRATOR,
        description="Currently active agent"
    )
    agent_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="History of agent switches"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Context creation timestamp"
    )
    last_switch_at: Optional[datetime] = Field(
        default=None,
        description="Last agent switch timestamp"
    )
    switch_count: int = Field(
        default=0,
        description="Number of agent switches in this session"
    )
    
    # Database instance (not serialized)
    _db: Optional[Database] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def set_db(self, db: Database) -> None:
        """Set database instance for persistence"""
        self._db = db
    
    def switch_agent(self, new_agent: AgentType, reason: str) -> None:
        """
        Switch to a different agent.
        
        Args:
            new_agent: Target agent type
            reason: Reason for the switch
        """
        if self.current_agent == new_agent:
            logger.debug(
                f"Agent switch requested to same agent {new_agent.value}, "
                f"skipping for session {self.session_id}"
            )
            return
        
        # Record switch in history
        switch_record = {
            "from": self.current_agent.value,
            "to": new_agent.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        self.agent_history.append(switch_record)
        
        logger.info(
            f"Agent switch in session {self.session_id}: "
            f"{self.current_agent.value} -> {new_agent.value} "
            f"(reason: {reason})"
        )
        
        # Update state
        self.current_agent = new_agent
        self.last_switch_at = datetime.now()
        self.switch_count += 1
        
        # Persist to database
        if self._db:
            self._persist()
    
    def _persist(self) -> None:
        """Persist context to database"""
        if not self._db:
            return
            
        try:
            self._db.save_agent_context(
                session_id=self.session_id,
                current_agent=self.current_agent.value,
                agent_history=self.agent_history,
                metadata=self.metadata,
                created_at=self.created_at,
                last_switch_at=self.last_switch_at,
                switch_count=self.switch_count
            )
        except Exception as e:
            logger.error(f"Error persisting agent context {self.session_id}: {e}", exc_info=True)
    
    def get_agent_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of agent switches.
        
        Returns:
            List of switch records
        """
        return self.agent_history.copy()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the context.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        if self._db:
            self._persist()  # Persist to database
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)


class AgentContextManager:
    """
    Manages agent contexts for all active sessions.
    
    Provides:
    - Context creation and retrieval
    - Context cleanup
    - Session management
    """
    
    def __init__(self, db: Optional[Database] = None):
        """Initialize the context manager"""
        self._contexts: Dict[str, AgentContext] = {}
        self._db = db or get_db()
        self._load_all_contexts()
        logger.info("AgentContextManager initialized")
    
    def _load_all_contexts(self) -> None:
        """Load all agent contexts from database into memory cache"""
        try:
            session_ids = self._db.list_all_contexts()
            for session_id in session_ids:
                context_data = self._db.load_agent_context(session_id)
                if context_data:
                    context = AgentContext(
                        session_id=context_data["session_id"],
                        current_agent=AgentType(context_data["current_agent"]),
                        agent_history=context_data["agent_history"],
                        metadata=context_data["metadata"],
                        created_at=context_data["created_at"],
                        last_switch_at=context_data["last_switch_at"],
                        switch_count=context_data["switch_count"]
                    )
                    context.set_db(self._db)
                    self._contexts[session_id] = context
            
            logger.info(f"Loaded {len(self._contexts)} agent contexts from database")
        except Exception as e:
            logger.error(f"Error loading agent contexts from database: {e}", exc_info=True)
    
    def get_or_create(
        self, 
        session_id: str,
        initial_agent: AgentType = AgentType.ORCHESTRATOR
    ) -> AgentContext:
        """
        Get existing context or create a new one.
        
        Args:
            session_id: Session identifier
            initial_agent: Initial agent type for new contexts
            
        Returns:
            Agent context for the session
        """
        if session_id not in self._contexts:
            context = AgentContext(
                session_id=session_id,
                current_agent=initial_agent
            )
            context.set_db(self._db)
            self._contexts[session_id] = context
            context._persist()  # Persist to database
            
            logger.info(
                f"Created new agent context for session {session_id} "
                f"with initial agent {initial_agent.value}"
            )
        
        return self._contexts[session_id]
    
    def get(self, session_id: str) -> Optional[AgentContext]:
        """
        Get existing context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Agent context or None if not found
        """
        return self._contexts.get(session_id)
    
    def exists(self, session_id: str) -> bool:
        """
        Check if context exists for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if context exists
        """
        return session_id in self._contexts
    
    def delete(self, session_id: str) -> bool:
        """
        Delete context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if context was deleted, False if not found
        """
        if session_id in self._contexts:
            del self._contexts[session_id]
            self._db.delete_agent_context(session_id)  # Delete from database
            logger.info(f"Deleted agent context for session {session_id}")
            return True
        
        logger.warning(
            f"Attempted to delete non-existent context for session {session_id}"
        )
        return False
    
    def get_all_sessions(self) -> List[str]:
        """
        Get list of all active session IDs.
        
        Returns:
            List of session IDs
        """
        return list(self._contexts.keys())
    
    def get_session_count(self) -> int:
        """
        Get number of active sessions.
        
        Returns:
            Number of sessions
        """
        return len(self._contexts)
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old inactive sessions.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now()
        sessions_to_delete = []
        
        for session_id, context in self._contexts.items():
            age = now - context.created_at
            if age.total_seconds() > (max_age_hours * 3600):
                sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            self.delete(session_id)
        
        if sessions_to_delete:
            logger.info(
                f"Cleaned up {len(sessions_to_delete)} old sessions "
                f"(older than {max_age_hours} hours)"
            )
        
        return len(sessions_to_delete)


# Singleton instance
_agent_context_manager_instance: Optional[AgentContextManager] = None


def get_agent_context_manager(db: Database = None) -> AgentContextManager:
    """
    Get AgentContextManager instance for dependency injection.
    
    Args:
        db: Optional database instance
        
    Returns:
        AgentContextManager instance
    """
    global _agent_context_manager_instance
    if _agent_context_manager_instance is None:
        _agent_context_manager_instance = AgentContextManager(db)
    return _agent_context_manager_instance


# Convenience accessor for backward compatibility
agent_context_manager = get_agent_context_manager()

"""
Agent context management for multi-agent system.

Maintains state and history for each agent session.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from app.agents.base_agent import AgentType

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
    
    def __init__(self):
        """Initialize the context manager"""
        self._contexts: Dict[str, AgentContext] = {}
        logger.info("AgentContextManager initialized")
    
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
            self._contexts[session_id] = context
            
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
agent_context_manager = AgentContextManager()

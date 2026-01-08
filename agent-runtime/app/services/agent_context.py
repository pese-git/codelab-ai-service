"""
DEPRECATED: This module is kept for backward compatibility only.
Use app.services.agent_context_async instead.

This module provides a proxy to the async AgentContextManager for code
that hasn't been migrated yet.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import logging

from app.agents.base_agent import AgentType

logger = logging.getLogger("agent-runtime.agent_context")

# Import async version module
import app.services.agent_context_async as async_module
from app.services.agent_context_async import AgentContext


class AgentContextManager:
    """
    DEPRECATED: Compatibility proxy for AsyncAgentContextManager.
    
    This class delegates all calls to the async AgentContextManager.
    Methods are synchronous wrappers that work with the in-memory cache.
    
    ⚠️ WARNING: This is a compatibility layer. New code should use AsyncAgentContextManager.
    """
    
    def __init__(self, db=None):
        """Initialize compatibility wrapper"""
        # Just a proxy, no initialization needed
        pass
    
    @property
    def _manager(self):
        """Get async manager instance"""
        if async_module.agent_context_manager is None:
            raise RuntimeError(
                "AsyncAgentContextManager not initialized. "
                "Make sure the application has started."
            )
        return async_module.agent_context_manager
    
    def get_or_create(
        self, 
        session_id: str,
        initial_agent: AgentType = AgentType.ORCHESTRATOR
    ) -> AgentContext:
        """
        Get existing context or create a new one.
        
        Note: For new contexts, persistence happens in background.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If called from async context
                if session_id not in self._manager._contexts:
                    context = AgentContext(
                        session_id=session_id,
                        current_agent=initial_agent
                    )
                    self._manager._contexts[session_id] = context
                    # Schedule for persistence
                    asyncio.create_task(self._manager._persist_immediately(session_id))
                
                return self._manager._contexts[session_id]
            else:
                return loop.run_until_complete(
                    self._manager.get_or_create(session_id, initial_agent)
                )
        except RuntimeError:
            # No event loop - just return from cache or create
            if session_id not in self._manager._contexts:
                context = AgentContext(
                    session_id=session_id,
                    current_agent=initial_agent
                )
                self._manager._contexts[session_id] = context
            return self._manager._contexts[session_id]
    
    def get(self, session_id: str) -> Optional[AgentContext]:
        """Get existing context"""
        return self._manager.get(session_id)
    
    def exists(self, session_id: str) -> bool:
        """Check if context exists for session"""
        return self._manager.exists(session_id)
    
    def delete(self, session_id: str) -> bool:
        """Delete context for a session"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(self._manager.delete(session_id))
                # Return True optimistically
                return True
            else:
                return loop.run_until_complete(self._manager.delete(session_id))
        except RuntimeError:
            # No event loop - just delete from cache
            if session_id in self._manager._contexts:
                del self._manager._contexts[session_id]
                return True
            return False
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all active session IDs"""
        return self._manager.get_all_sessions()
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return self._manager.get_session_count()
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up old inactive sessions"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._manager.cleanup_old_sessions(max_age_hours))
                return 0  # Return 0 as we don't wait for completion
            else:
                return loop.run_until_complete(
                    self._manager.cleanup_old_sessions(max_age_hours)
                )
        except RuntimeError:
            logger.error("Cannot cleanup sessions without event loop")
            return 0


# Singleton instance
_agent_context_manager_instance: Optional[AgentContextManager] = None


def get_agent_context_manager(db=None) -> AgentContextManager:
    """
    Get AgentContextManager instance (compatibility function).
    
    Returns:
        AgentContextManager proxy instance
    """
    global _agent_context_manager_instance
    if _agent_context_manager_instance is None:
        _agent_context_manager_instance = AgentContextManager(db)
    return _agent_context_manager_instance


# Convenience accessor for backward compatibility
agent_context_manager = get_agent_context_manager()

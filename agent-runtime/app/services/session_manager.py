"""
DEPRECATED: This module is kept for backward compatibility only.
Use app.services.session_manager_async instead.

This module provides a proxy to the async SessionManager for code
that hasn't been migrated yet.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models.schemas import Message, SessionState

logger = logging.getLogger("agent-runtime.session_manager")

# Import async version module
import app.services.session_manager_async as async_module


class SessionManager:
    """
    DEPRECATED: Compatibility proxy for AsyncSessionManager.
    
    This class delegates all calls to the async SessionManager.
    Methods are synchronous wrappers that work with the in-memory cache.
    
    ⚠️ WARNING: This is a compatibility layer. New code should use AsyncSessionManager.
    """

    def __init__(self, db=None) -> None:
        """Initialize compatibility wrapper"""
        # Just a proxy, no initialization needed
        pass
    
    @property
    def _manager(self):
        """Get async manager instance"""
        if async_module.session_manager is None:
            raise RuntimeError(
                "AsyncSessionManager not initialized. "
                "Make sure the application has started."
            )
        return async_module.session_manager
    
    def exists(self, session_id: str) -> bool:
        """Check if session exists"""
        return self._manager.exists(session_id)
    
    def create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        """
        Create a new session (sync wrapper).
        
        Note: This doesn't persist immediately. Use async version for immediate persistence.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If called from async context, just create in memory
                # Persistence will happen in background
                from app.models.schemas import SessionState, Message
                
                if session_id in self._manager._sessions:
                    raise ValueError(f"Session {session_id} already exists")
                
                state = SessionState.model_construct(session_id=session_id)
                if system_prompt:
                    state.messages.append(
                        Message.model_construct(role="system", content=system_prompt)
                    )
                
                self._manager._sessions[session_id] = state
                # Schedule for persistence
                asyncio.create_task(self._manager._persist_immediately(session_id))
                return state
            else:
                return loop.run_until_complete(
                    self._manager.create(session_id, system_prompt)
                )
        except RuntimeError:
            # No event loop
            logger.error("Cannot create session without event loop")
            raise RuntimeError("SessionManager requires async context")
    
    def get(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID"""
        return self._manager.get(session_id)
    
    def get_or_create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        """Get existing session or create new one"""
        if session_id not in self._manager._sessions:
            return self.create(session_id, system_prompt)
        return self._manager._sessions[session_id]
    
    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        name: Optional[str] = None
    ) -> None:
        """Append a message to session history"""
        state = self.get(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        msg = Message.model_construct(role=role, content=content, name=name)
        state.messages.append(msg)
        state.last_activity = datetime.now(timezone.utc)
        
        # Schedule for persistence
        import asyncio
        try:
            asyncio.create_task(self._manager._schedule_persist(session_id))
        except RuntimeError:
            # No event loop, will be persisted by background task
            pass
    
    def append_tool_result(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        result: str
    ) -> None:
        """Append tool execution result to session history"""
        state = self.get(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        
        tool_message = {
            "role": "tool",
            "content": result,
            "tool_call_id": call_id,
            "name": tool_name
        }
        
        state.messages.append(tool_message)
        state.last_activity = datetime.now(timezone.utc)
        
        # Schedule for persistence
        import asyncio
        try:
            asyncio.create_task(self._manager._schedule_persist(session_id))
        except RuntimeError:
            # No event loop, will be persisted by background task
            pass
    
    def get_history(self, session_id: str) -> List[dict]:
        """Get session message history"""
        return self._manager.get_history(session_id)
    
    def all_sessions(self) -> List[SessionState]:
        """Get all active sessions"""
        return self._manager.all_sessions()
    
    def delete(self, session_id: str) -> None:
        """Delete a session"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._manager.delete(session_id))
            else:
                loop.run_until_complete(self._manager.delete(session_id))
        except RuntimeError:
            logger.error("Cannot delete session without event loop")


# Singleton instance - proxies to async version
_session_manager_instance: Optional[SessionManager] = None


def get_session_manager(db=None) -> SessionManager:
    """
    Get SessionManager instance (compatibility function).
    
    Returns:
        SessionManager proxy instance
    """
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionManager(db)
    return _session_manager_instance


# Convenience accessor for backward compatibility
session_manager = get_session_manager()

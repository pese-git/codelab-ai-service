"""
Async Agent context management for multi-agent system.

Maintains state and history for each agent session with async database operations.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.agents.base_agent import AgentType
from app.services.database import get_db, get_database_service, DatabaseService

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
        default_factory=lambda: datetime.now(timezone.utc),
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
    
    # Mark for persistence
    _needs_persist: bool = False
    
    class Config:
        arbitrary_types_allowed = True
    
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.agent_history.append(switch_record)
        
        logger.info(
            f"Agent switch in session {self.session_id}: "
            f"{self.current_agent.value} -> {new_agent.value} "
            f"(reason: {reason})"
        )
        
        # Update state
        self.current_agent = new_agent
        self.last_switch_at = datetime.now(timezone.utc)
        self.switch_count += 1
        self._needs_persist = True
    
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
        self._needs_persist = True
    
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


class AsyncAgentContextManager:
    """
    Async agent context manager for all active sessions.
    
    Provides:
    - Context creation and retrieval
    - Context cleanup
    - Session management
    - Background persistence
    """
    
    def __init__(self):
        """Initialize the context manager"""
        self._contexts: Dict[str, AgentContext] = {}
        self._lock = asyncio.Lock()
        self._db_service = get_database_service()
        self._write_task: Optional[asyncio.Task] = None
        self._initialized = False
        logger.info("AsyncAgentContextManager created")
    
    async def initialize(self):
        """
        Initialize context manager - load contexts from database.
        
        Must be called after creating the instance.
        """
        if self._initialized:
            return
        
        try:
            async for db in get_db():
                session_ids = await self._db_service.list_all_sessions(db)
                
                for session_id in session_ids:
                    context_data = await self._db_service.load_agent_context(db, session_id)
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
                        self._contexts[session_id] = context
                
                logger.info(f"Loaded {len(self._contexts)} agent contexts from database")
                break
            
            # Start background write task
            self._write_task = asyncio.create_task(self._background_writer())
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing agent context manager: {e}", exc_info=True)
            # Continue with empty cache
            self._initialized = True
    
    async def _background_writer(self):
        """Background task for persisting contexts"""
        while True:
            try:
                await asyncio.sleep(5)  # Write every 5 seconds
                
                # Find contexts that need persistence
                contexts_to_persist = []
                async with self._lock:
                    for session_id, context in self._contexts.items():
                        if context._needs_persist:
                            contexts_to_persist.append(session_id)
                            context._needs_persist = False
                
                if not contexts_to_persist:
                    continue
                
                # Persist contexts
                async for db in get_db():
                    for session_id in contexts_to_persist:
                        context = self._contexts.get(session_id)
                        if context:
                            await self._db_service.save_agent_context(
                                db=db,
                                session_id=session_id,
                                current_agent=context.current_agent.value,
                                agent_history=context.agent_history,
                                metadata=context.metadata,
                                created_at=context.created_at,
                                last_switch_at=context.last_switch_at,
                                switch_count=context.switch_count
                            )
                    break
                
                logger.debug(f"Background writer persisted {len(contexts_to_persist)} contexts")
                
            except asyncio.CancelledError:
                logger.info("Background writer cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background writer: {e}", exc_info=True)
    
    async def _persist_immediately(self, session_id: str):
        """Persist context immediately"""
        try:
            context = self._contexts.get(session_id)
            if context:
                async for db in get_db():
                    await self._db_service.save_agent_context(
                        db=db,
                        session_id=session_id,
                        current_agent=context.current_agent.value,
                        agent_history=context.agent_history,
                        metadata=context.metadata,
                        created_at=context.created_at,
                        last_switch_at=context.last_switch_at,
                        switch_count=context.switch_count
                    )
                    break
                context._needs_persist = False
        except Exception as e:
            logger.error(f"Error persisting context {session_id}: {e}", exc_info=True)
    
    async def get_or_create(
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
        async with self._lock:
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
                
                # Persist immediately for new contexts
                await self._persist_immediately(session_id)
            
            return self._contexts[session_id]
    
    def get(self, session_id: str) -> Optional[AgentContext]:
        """
        Get existing context (sync for compatibility).
        
        Args:
            session_id: Session identifier
            
        Returns:
            Agent context or None if not found
        """
        return self._contexts.get(session_id)
    
    def get_or_create_sync(
        self,
        session_id: str,
        initial_agent: AgentType = AgentType.ORCHESTRATOR
    ) -> AgentContext:
        """
        Get existing context or create a new one (sync version).
        
        Creates context in memory only. Persistence happens in background.
        Use this for sync code that needs immediate context access.
        
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
            context._needs_persist = True
            
            logger.info(
                f"Created new agent context (sync) for session {session_id} "
                f"with initial agent {initial_agent.value}"
            )
        
        return self._contexts[session_id]
    
    def exists(self, session_id: str) -> bool:
        """
        Check if context exists for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if context exists
        """
        return session_id in self._contexts
    
    async def delete(self, session_id: str) -> bool:
        """
        Delete context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if context was deleted, False if not found
        """
        async with self._lock:
            if session_id in self._contexts:
                del self._contexts[session_id]
                logger.info(f"Deleted agent context for session {session_id}")
            else:
                logger.warning(
                    f"Attempted to delete non-existent context for session {session_id}"
                )
                return False
        
        # Delete from database
        async for db in get_db():
            from sqlalchemy import select, delete as sql_delete
            from app.services.database import SessionModel, AgentContextModel
            
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
            
            if context:
                await db.delete(context)
                await db.commit()
            
            break
        
        return True
    
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
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old inactive sessions.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(timezone.utc)
        sessions_to_delete = []
        
        async with self._lock:
            for session_id, context in self._contexts.items():
                age = now - context.created_at
                if age.total_seconds() > (max_age_hours * 3600):
                    sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            await self.delete(session_id)
        
        if sessions_to_delete:
            logger.info(
                f"Cleaned up {len(sessions_to_delete)} old sessions "
                f"(older than {max_age_hours} hours)"
            )
        
        return len(sessions_to_delete)
    
    async def shutdown(self):
        """Shutdown context manager - flush pending writes"""
        logger.info("Shutting down agent context manager...")
        
        # Cancel background writer
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
        
        # Flush all contexts that need persistence
        contexts_to_persist = []
        async with self._lock:
            for session_id, context in self._contexts.items():
                if context._needs_persist:
                    contexts_to_persist.append(session_id)
        
        if contexts_to_persist:
            logger.info(f"Flushing {len(contexts_to_persist)} pending contexts...")
            async for db in get_db():
                for session_id in contexts_to_persist:
                    context = self._contexts.get(session_id)
                    if context:
                        await self._db_service.save_agent_context(
                            db=db,
                            session_id=session_id,
                            current_agent=context.current_agent.value,
                            agent_history=context.agent_history,
                            metadata=context.metadata,
                            created_at=context.created_at,
                            last_switch_at=context.last_switch_at,
                            switch_count=context.switch_count
                        )
                break
            logger.info("All pending contexts flushed")
        
        logger.info("Agent context manager shutdown complete")


# Global instance
_agent_context_manager_instance: Optional[AsyncAgentContextManager] = None


async def get_async_agent_context_manager() -> AsyncAgentContextManager:
    """
    Get AsyncAgentContextManager instance (singleton).
    
    Returns:
        AsyncAgentContextManager instance
    """
    global _agent_context_manager_instance
    if _agent_context_manager_instance is None:
        _agent_context_manager_instance = AsyncAgentContextManager()
        await _agent_context_manager_instance.initialize()
    return _agent_context_manager_instance


# Convenience accessor (will be initialized on first use)
agent_context_manager: Optional[AsyncAgentContextManager] = None


async def init_agent_context_manager():
    """Initialize global agent context manager"""
    global agent_context_manager
    if agent_context_manager is None:
        agent_context_manager = await get_async_agent_context_manager()

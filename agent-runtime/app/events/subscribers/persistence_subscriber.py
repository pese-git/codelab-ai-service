"""
Persistence subscriber for event-driven database persistence.

Replaces timer-based background writers with event-driven approach.
"""

import asyncio
import logging
from typing import Set, Dict
from datetime import datetime, timedelta

from ..event_bus import event_bus
from ..base_event import BaseEvent
from ..event_types import EventType
from app.core.config import AppConfig

logger = logging.getLogger(__name__)


class PersistenceSubscriber:
    """
    Event-driven persistence subscriber.
    
    Listens to update events and triggers database persistence:
    - Debouncing to avoid too frequent writes
    - Batch processing for efficiency
    - Configurable flush interval
    """
    
    def __init__(
        self,
        enabled: bool = None,
        debounce_seconds: float = 2.0,
        max_batch_size: int = 50
    ):
        """
        Initialize persistence subscriber.
        
        Args:
            enabled: Whether to enable event-driven persistence
                    (defaults to AppConfig.USE_EVENT_DRIVEN_PERSISTENCE)
            debounce_seconds: Minimum time between persists for same session
            max_batch_size: Maximum sessions to persist in one batch
        """
        self._enabled = enabled if enabled is not None else AppConfig.USE_EVENT_DRIVEN_PERSISTENCE
        self._debounce_seconds = debounce_seconds
        self._max_batch_size = max_batch_size
        
        # Pending sessions to persist
        self._pending_sessions: Set[str] = set()
        self._pending_contexts: Set[str] = set()
        
        # Last persist time for debouncing
        self._last_persist: Dict[str, datetime] = {}
        
        # Lock for thread-safety
        self._lock = asyncio.Lock()
        
        # Flush task
        self._flush_task: asyncio.Task = None
        
        if self._enabled:
            self._setup_subscriptions()
            self._start_flush_task()
            logger.info(
                f"PersistenceSubscriber initialized (ENABLED, "
                f"debounce={debounce_seconds}s, max_batch={max_batch_size})"
            )
        else:
            logger.info("PersistenceSubscriber initialized (DISABLED)")
    
    def _setup_subscriptions(self):
        """Subscribe to update events."""
        
        # Session updates
        event_bus.subscribe(
            event_type=EventType.SESSION_UPDATED,
            handler=self._on_session_updated,
            priority=1  # Low priority - persist after other handlers
        )
        
        event_bus.subscribe(
            event_type=EventType.MESSAGE_ADDED,
            handler=self._on_message_added,
            priority=1
        )
        
        # Agent context updates
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=self._on_agent_switched,
            priority=1
        )
    
    def _start_flush_task(self):
        """Start background flush task."""
        self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def _flush_loop(self):
        """Background task to flush pending persists."""
        while True:
            try:
                await asyncio.sleep(self._debounce_seconds)
                await self._flush_pending()
            except asyncio.CancelledError:
                logger.info("Flush loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}", exc_info=True)
    
    async def _on_session_updated(self, event: BaseEvent):
        """Handle session updated event."""
        if not self._enabled:
            return
        
        session_id = event.session_id
        if not session_id:
            return
        
        await self._schedule_session_persist(session_id)
    
    async def _on_message_added(self, event: BaseEvent):
        """Handle message added event."""
        if not self._enabled:
            return
        
        session_id = event.session_id
        if not session_id:
            return
        
        await self._schedule_session_persist(session_id)
    
    async def _on_agent_switched(self, event: BaseEvent):
        """Handle agent switched event."""
        if not self._enabled:
            return
        
        session_id = event.session_id
        if not session_id:
            return
        
        await self._schedule_context_persist(session_id)
    
    async def _schedule_session_persist(self, session_id: str):
        """Schedule session for persistence with debouncing."""
        async with self._lock:
            # Check debounce
            last_time = self._last_persist.get(f"session:{session_id}")
            if last_time:
                elapsed = (datetime.utcnow() - last_time).total_seconds()
                if elapsed < self._debounce_seconds:
                    # Too soon, skip
                    return
            
            self._pending_sessions.add(session_id)
            logger.debug(f"Scheduled session persist: {session_id}")
    
    async def _schedule_context_persist(self, session_id: str):
        """Schedule context for persistence with debouncing."""
        async with self._lock:
            # Check debounce
            last_time = self._last_persist.get(f"context:{session_id}")
            if last_time:
                elapsed = (datetime.utcnow() - last_time).total_seconds()
                if elapsed < self._debounce_seconds:
                    # Too soon, skip
                    return
            
            self._pending_contexts.add(session_id)
            logger.debug(f"Scheduled context persist: {session_id}")
    
    async def _flush_pending(self):
        """Flush all pending persists."""
        async with self._lock:
            if not self._pending_sessions and not self._pending_contexts:
                return
            
            sessions_to_persist = list(self._pending_sessions)[:self._max_batch_size]
            contexts_to_persist = list(self._pending_contexts)[:self._max_batch_size]
            
            # Clear from pending
            for session_id in sessions_to_persist:
                self._pending_sessions.discard(session_id)
            
            for session_id in contexts_to_persist:
                self._pending_contexts.discard(session_id)
        
        # Persist sessions
        if sessions_to_persist:
            await self._persist_sessions(sessions_to_persist)
        
        # Persist contexts
        if contexts_to_persist:
            await self._persist_contexts(contexts_to_persist)
    
    async def _persist_sessions(self, session_ids: list):
        """Persist sessions to database."""
        from app.services.session_manager_async import session_manager
        from app.services.database import get_db
        
        if not session_manager:
            return
        
        logger.debug(f"Persisting {len(session_ids)} sessions")
        
        async for db in get_db():
            for session_id in session_ids:
                try:
                    state = session_manager.get(session_id)
                    if state:
                        messages = []
                        for msg in state.messages:
                            if isinstance(msg, dict):
                                messages.append(msg)
                            else:
                                messages.append(msg.model_dump())
                        
                        await session_manager._db_service.save_session(
                            db=db,
                            session_id=session_id,
                            messages=messages,
                            last_activity=state.last_activity
                        )
                        
                        # Update last persist time
                        self._last_persist[f"session:{session_id}"] = datetime.utcnow()
                        
                except Exception as e:
                    logger.error(f"Error persisting session {session_id}: {e}")
            
            break
        
        logger.info(f"Persisted {len(session_ids)} sessions")
    
    async def _persist_contexts(self, session_ids: list):
        """Persist agent contexts to database."""
        from app.services.agent_context_async import agent_context_manager
        from app.services.database import get_db
        
        if not agent_context_manager:
            return
        
        logger.debug(f"Persisting {len(session_ids)} contexts")
        
        async for db in get_db():
            for session_id in session_ids:
                try:
                    context = agent_context_manager.get(session_id)
                    if context and context._needs_persist:
                        await agent_context_manager._db_service.save_agent_context(
                            db=db,
                            session_id=session_id,
                            current_agent=context.current_agent.value,
                            switch_count=context.switch_count,
                            metadata=context.metadata,
                            agent_history=context.agent_history,
                            last_switch_at=context.last_switch_at
                        )
                        
                        context._needs_persist = False
                        
                        # Update last persist time
                        self._last_persist[f"context:{session_id}"] = datetime.utcnow()
                        
                except Exception as e:
                    logger.error(f"Error persisting context {session_id}: {e}")
            
            break
        
        logger.info(f"Persisted {len(session_ids)} contexts")
    
    async def flush_all(self):
        """Flush all pending persists immediately (for shutdown)."""
        logger.info("Flushing all pending persists...")
        await self._flush_pending()
    
    async def shutdown(self):
        """Shutdown persistence subscriber."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self.flush_all()
        logger.info("PersistenceSubscriber shutdown complete")
    
    def is_enabled(self) -> bool:
        """Check if event-driven persistence is enabled."""
        return self._enabled
    
    def get_pending_count(self) -> dict:
        """Get count of pending persists."""
        return {
            "sessions": len(self._pending_sessions),
            "contexts": len(self._pending_contexts)
        }


# Global singleton instance (created only if enabled)
persistence_subscriber = None


def init_persistence_subscriber(enabled: bool = None):
    """
    Initialize global persistence subscriber.
    
    Args:
        enabled: Whether to enable event-driven persistence
                (defaults to AppConfig.USE_EVENT_DRIVEN_PERSISTENCE)
    """
    global persistence_subscriber
    
    if persistence_subscriber is None:
        persistence_subscriber = PersistenceSubscriber(enabled=enabled)
    
    return persistence_subscriber

"""
Async Session Manager for agent runtime.

Manages all agent sessions with async database operations.
Thread-safe storage with async persistence.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING

from app.models.schemas import Message, SessionState
from app.services.database import get_db, get_database_service, DatabaseService

if TYPE_CHECKING:
    from app.models.schemas import ExecutionPlan, Subtask

logger = logging.getLogger("agent-runtime.session_manager")


class AsyncSessionManager:
    """
    Async session manager with database persistence.
    
    Features:
    - In-memory cache for fast access
    - Async database persistence
    - Background task for batch writes
    - Thread-safe operations
    """
    
    def __init__(self):
        """Initialize session manager"""
        self._sessions: Dict[str, SessionState] = {}
        self._plans: Dict[str, "ExecutionPlan"] = {}  # session_id -> ExecutionPlan
        self._pending_confirmations: set[str] = set()  # session_ids waiting for plan confirmation
        self._lock = asyncio.Lock()
        self._db_service = get_database_service()
        self._pending_writes: set[str] = set()
        self._write_task: Optional[asyncio.Task] = None
        self._initialized = False
        logger.info("AsyncSessionManager created")
    
    async def initialize(self):
        """
        Initialize session manager - load sessions from database.
        
        Must be called after creating the instance.
        """
        if self._initialized:
            return
        
        try:
            async for db in get_db():
                session_ids = await self._db_service.list_all_sessions(db)
                
                for session_id in session_ids:
                    session_data = await self._db_service.load_session(db, session_id)
                    if session_data:
                        # Fix messages with None content (for tool_calls messages)
                        messages = []
                        for msg in session_data["messages"]:
                            # Ensure content is never None for Pydantic validation
                            if msg.get("content") is None:
                                msg["content"] = ""
                            messages.append(msg)
                        
                        state = SessionState(
                            session_id=session_data["session_id"],
                            messages=messages,
                            last_activity=session_data["last_activity"]
                        )
                        self._sessions[session_id] = state
                
                logger.info(f"Loaded {len(self._sessions)} sessions from database")
                break
            
            # Start background write task
            self._write_task = asyncio.create_task(self._background_writer())
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing session manager: {e}", exc_info=True)
            # Continue with empty cache
            self._initialized = True
    
    async def _background_writer(self):
        """Background task for batch writing sessions to database"""
        while True:
            try:
                await asyncio.sleep(5)  # Write every 5 seconds
                
                async with self._lock:
                    if not self._pending_writes:
                        continue
                    
                    session_ids = list(self._pending_writes)
                    self._pending_writes.clear()
                
                # Write all pending sessions
                async for db in get_db():
                    for session_id in session_ids:
                        state = self._sessions.get(session_id)
                        if state:
                            messages = []
                            for msg in state.messages:
                                if isinstance(msg, dict):
                                    messages.append(msg)
                                else:
                                    messages.append(msg.model_dump())
                            
                            await self._db_service.save_session(
                                db=db,
                                session_id=session_id,
                                messages=messages,
                                last_activity=state.last_activity
                            )
                    break
                
                if session_ids:
                    logger.debug(f"Background writer persisted {len(session_ids)} sessions")
                    
            except asyncio.CancelledError:
                logger.info("Background writer cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background writer: {e}", exc_info=True)
    
    async def _schedule_persist(self, session_id: str):
        """Schedule session for persistence"""
        async with self._lock:
            self._pending_writes.add(session_id)
    
    async def _persist_immediately(self, session_id: str):
        """Persist session immediately (for critical operations)"""
        try:
            state = self._sessions.get(session_id)
            if state:
                messages = []
                for msg in state.messages:
                    if isinstance(msg, dict):
                        messages.append(msg)
                    else:
                        messages.append(msg.model_dump())
                
                async for db in get_db():
                    await self._db_service.save_session(
                        db=db,
                        session_id=session_id,
                        messages=messages,
                        last_activity=state.last_activity
                    )
                    break
        except Exception as e:
            logger.error(f"Error persisting session {session_id}: {e}", exc_info=True)
    
    def exists(self, session_id: str) -> bool:
        """Check if session exists (sync for compatibility)"""
        exists = session_id in self._sessions
        logger.debug(f"Session exists check: {session_id} -> {exists}")
        return exists
    
    async def create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        """
        Create a new session with optional system prompt.
        
        Args:
            session_id: Unique session identifier
            system_prompt: Optional system prompt to initialize the session
            
        Returns:
            Created SessionState
            
        Raises:
            ValueError: If session already exists
        """
        async with self._lock:
            if session_id in self._sessions:
                logger.error(f"Attempt to create duplicate session: {session_id}")
                raise ValueError(f"Session {session_id} already exists")
            
            state = SessionState.model_construct(session_id=session_id)
            if system_prompt:
                state.messages.append(
                    Message.model_construct(role="system", content=system_prompt)
                )
            
            self._sessions[session_id] = state
            logger.info(f"Created session: {session_id} with {len(state.messages)} initial messages")
        
        # Persist immediately for new sessions
        await self._persist_immediately(session_id)
        return state
    
    def get(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID (sync for compatibility)"""
        session = self._sessions.get(session_id)
        if session:
            logger.debug(f"Retrieved session: {session_id}")
        else:
            logger.debug(f"Session not found: {session_id}")
        return session
    
    async def get_or_create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        """
        Get existing session or create new one if it doesn't exist.
        
        Args:
            session_id: Unique session identifier
            system_prompt: Optional system prompt for new sessions
            
        Returns:
            Existing or newly created SessionState
        """
        if session_id not in self._sessions:
            logger.info(f"Creating new session: {session_id}")
            return await self.create(session_id, system_prompt)
        
        logger.debug(f"Found existing session: {session_id}")
        return self._sessions[session_id]
    
    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        name: Optional[str] = None
    ) -> None:
        """
        Append a message to session history.
        
        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system, tool)
            content: Message content
            name: Optional name (e.g., tool name)
            
        Raises:
            ValueError: If session not found
        """
        async with self._lock:
            state = self.get(session_id)
            if not state:
                logger.error(f"Cannot append message: session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            
            msg = Message.model_construct(role=role, content=content, name=name)
            state.messages.append(msg)
            state.last_activity = datetime.now(timezone.utc)
            
            logger.debug(
                f"Appended {role} message to {session_id}: "
                f"{len(content)} chars, total messages: {len(state.messages)}"
            )
        
        # Schedule for background persistence
        await self._schedule_persist(session_id)
    
    async def append_tool_result(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        result: str
    ) -> None:
        """
        Append tool execution result to session history.
        
        Creates a tool message with tool_call_id for OpenAI API compatibility.
        
        Args:
            session_id: Session identifier
            call_id: Tool call ID (must match assistant message tool_call id)
            tool_name: Name of the executed tool
            result: Tool execution result as string
            
        Raises:
            ValueError: If session not found
        """
        async with self._lock:
            state = self.get(session_id)
            if not state:
                logger.error(f"Cannot append tool result: session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            
            logger.info(
                f"Appending tool result to {session_id}: "
                f"call_id={call_id}, tool={tool_name}, result_len={len(result)}"
            )
            
            tool_message = {
                "role": "tool",
                "content": result,
                "tool_call_id": call_id,
                "name": tool_name
            }
            
            state.messages.append(tool_message)
            state.last_activity = datetime.now(timezone.utc)
            
            logger.debug(
                f"Tool result appended: call_id={call_id}, "
                f"total messages: {len(state.messages)}"
            )
        
        # Schedule for background persistence
        await self._schedule_persist(session_id)
    
    def get_history(self, session_id: str) -> List[dict]:
        """
        Get session message history as list of dicts for LLM.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dictionaries
        """
        state = self.get(session_id)
        if not state:
            logger.warning(f"Cannot get history: session {session_id} not found")
            return []
        
        history = []
        for msg in state.messages:
            if isinstance(msg, dict):
                history.append(msg)
            else:
                history.append(msg.model_dump())
        
        logger.debug(f"Retrieved history for {session_id}: {len(history)} messages")
        return history
    
    def all_sessions(self) -> List[SessionState]:
        """Get all active sessions"""
        sessions = list(self._sessions.values())
        logger.debug(f"Retrieved all sessions: {len(sessions)} total")
        return sessions
    
    async def delete(self, session_id: str) -> None:
        """Delete a session"""
        async with self._lock:
            if session_id in self._sessions:
                logger.info(f"Deleting session: {session_id}")
                del self._sessions[session_id]
                # Remove from pending writes
                self._pending_writes.discard(session_id)
            else:
                logger.warning(f"Cannot delete: session {session_id} not found")
        
        # Delete from database
        async for db in get_db():
            await self._db_service.delete_session(db, session_id)
            break
    
    async def shutdown(self):
        """Shutdown session manager - flush pending writes"""
        logger.info("Shutting down session manager...")
        
        # Cancel background writer
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
        
        # Flush all pending writes
        async with self._lock:
            session_ids = list(self._pending_writes)
            self._pending_writes.clear()
        
        if session_ids:
            logger.info(f"Flushing {len(session_ids)} pending sessions...")
            async for db in get_db():
                for session_id in session_ids:
                    state = self._sessions.get(session_id)
                    if state:
                        messages = []
                        for msg in state.messages:
                            if isinstance(msg, dict):
                                messages.append(msg)
                            else:
                                messages.append(msg.model_dump())
                        
                        await self._db_service.save_session(
                            db=db,
                            session_id=session_id,
                            messages=messages,
                            last_activity=state.last_activity
                        )
                break
            logger.info("All pending sessions flushed")
        
        logger.info("Session manager shutdown complete")
    
    # ===== Plan Management Methods =====
    
    def set_plan(self, session_id: str, plan: "ExecutionPlan") -> None:
        """
        Store execution plan for a session.
        
        Args:
            session_id: Session identifier
            plan: ExecutionPlan to store
        """
        self._plans[session_id] = plan
        logger.info(
            f"Stored execution plan for session {session_id}: "
            f"{len(plan.subtasks)} subtasks"
        )
    
    def get_plan(self, session_id: str) -> Optional["ExecutionPlan"]:
        """
        Get execution plan for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ExecutionPlan if exists, None otherwise
        """
        plan = self._plans.get(session_id)
        if plan:
            logger.debug(
                f"Retrieved plan for session {session_id}: "
                f"subtask {plan.current_subtask_index + 1}/{len(plan.subtasks)}"
            )
        return plan
    
    def has_plan(self, session_id: str) -> bool:
        """
        Check if session has an active execution plan.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if plan exists, False otherwise
        """
        return session_id in self._plans
    
    def mark_subtask_complete(
        self,
        session_id: str,
        subtask_id: str,
        result: Optional[str] = None
    ) -> bool:
        """
        Mark a subtask as completed.
        
        Args:
            session_id: Session identifier
            subtask_id: Subtask identifier
            result: Optional result/output from subtask execution
            
        Returns:
            True if subtask was found and marked, False otherwise
        """
        plan = self.get_plan(session_id)
        if not plan:
            logger.warning(f"No plan found for session {session_id}")
            return False
        
        # Find and update subtask
        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                from app.models.schemas import SubtaskStatus
                subtask.status = SubtaskStatus.COMPLETED
                if result:
                    subtask.result = result
                logger.info(
                    f"Marked subtask {subtask_id} as completed in session {session_id}"
                )
                return True
        
        logger.warning(
            f"Subtask {subtask_id} not found in plan for session {session_id}"
        )
        return False
    
    def mark_subtask_failed(
        self,
        session_id: str,
        subtask_id: str,
        error: str
    ) -> bool:
        """
        Mark a subtask as failed.
        
        Args:
            session_id: Session identifier
            subtask_id: Subtask identifier
            error: Error message
            
        Returns:
            True if subtask was found and marked, False otherwise
        """
        plan = self.get_plan(session_id)
        if not plan:
            logger.warning(f"No plan found for session {session_id}")
            return False
        
        # Find and update subtask
        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                from app.models.schemas import SubtaskStatus
                subtask.status = SubtaskStatus.FAILED
                subtask.error = error
                logger.error(
                    f"Marked subtask {subtask_id} as failed in session {session_id}: {error}"
                )
                return True
        
        logger.warning(
            f"Subtask {subtask_id} not found in plan for session {session_id}"
        )
        return False
    
    def get_next_subtask(self, session_id: str) -> Optional["Subtask"]:
        """
        Get the next pending or in-progress subtask to execute.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Next Subtask to execute, or None if all complete
        """
        plan = self.get_plan(session_id)
        if not plan:
            return None
        
        from app.models.schemas import SubtaskStatus
        
        # First, check if there's an IN_PROGRESS subtask (waiting for tool_result)
        for i, subtask in enumerate(plan.subtasks):
            if subtask.status == SubtaskStatus.IN_PROGRESS:
                plan.current_subtask_index = i
                logger.info(
                    f"Continuing IN_PROGRESS subtask for session {session_id}: "
                    f"{subtask.id} ({i + 1}/{len(plan.subtasks)})"
                )
                return subtask
        
        # Find next pending subtask that has all dependencies met
        for i, subtask in enumerate(plan.subtasks):
            if subtask.status == SubtaskStatus.PENDING:
                # Check if all dependencies are completed
                dependencies_met = True
                for dep_id in subtask.dependencies:
                    dep_subtask = next(
                        (s for s in plan.subtasks if s.id == dep_id),
                        None
                    )
                    if not dep_subtask or dep_subtask.status != SubtaskStatus.COMPLETED:
                        dependencies_met = False
                        break
                
                if dependencies_met:
                    # Mark as in progress
                    subtask.status = SubtaskStatus.IN_PROGRESS
                    plan.current_subtask_index = i
                    logger.info(
                        f"Next subtask for session {session_id}: "
                        f"{subtask.id} ({i + 1}/{len(plan.subtasks)})"
                    )
                    return subtask
        
        # Check if all subtasks are complete
        all_complete = all(
            s.status in [SubtaskStatus.COMPLETED, SubtaskStatus.SKIPPED]
            for s in plan.subtasks
        )
        
        if all_complete:
            plan.is_complete = True
            logger.info(f"All subtasks completed for session {session_id}")
        
        return None
    
    def clear_plan(self, session_id: str) -> None:
        """
        Clear execution plan for a session.

        Args:
            session_id: Session identifier
        """
        if session_id in self._plans:
            del self._plans[session_id]
            logger.info(f"Cleared execution plan for session {session_id}")

    def set_pending_plan_confirmation(self, session_id: str) -> None:
        """
        Mark session as waiting for plan confirmation.

        Args:
            session_id: Session identifier
        """
        self._pending_confirmations.add(session_id)
        logger.info(f"Set pending confirmation for session {session_id}")

    def has_pending_plan_confirmation(self, session_id: str) -> bool:
        """
        Check if session is waiting for plan confirmation.

        Args:
            session_id: Session identifier

        Returns:
            True if waiting for confirmation, False otherwise
        """
        return session_id in self._pending_confirmations

    def clear_pending_plan_confirmation(self, session_id: str) -> None:
        """
        Clear pending confirmation state for a session.

        Args:
            session_id: Session identifier
        """
        self._pending_confirmations.discard(session_id)
        logger.info(f"Cleared pending confirmation for session {session_id}")


# Global instance
_session_manager_instance: Optional[AsyncSessionManager] = None


async def get_async_session_manager() -> AsyncSessionManager:
    """
    Get AsyncSessionManager instance (singleton).
    
    Returns:
        AsyncSessionManager instance
    """
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = AsyncSessionManager()
        await _session_manager_instance.initialize()
    return _session_manager_instance


# Convenience accessor (will be initialized on first use)
session_manager: Optional[AsyncSessionManager] = None


async def init_session_manager():
    """Initialize global session manager"""
    global session_manager
    if session_manager is None:
        session_manager = await get_async_session_manager()

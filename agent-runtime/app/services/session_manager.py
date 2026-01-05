import logging
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List, Optional, Union

from app.models.schemas import Message, SessionState
from app.services.database import Database, get_db

logger = logging.getLogger("agent-runtime.session_manager")


class SessionManager:
    """
    Manages all agent sessions: creation, access, and message history.
    
    Thread-safe storage with SQLite persistence for session states.
    Sessions are cached in memory and automatically persisted to database.
    """

    def __init__(self, db: Optional[Database] = None) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._lock = RLock()
        self._db = db or get_db()
        self._load_all_sessions()
    
    def _load_all_sessions(self) -> None:
        """Load all sessions from database into memory cache"""
        try:
            session_ids = self._db.list_all_sessions()
            for session_id in session_ids:
                session_data = self._db.load_session(session_id)
                if session_data:
                    state = SessionState(
                        session_id=session_data["session_id"],
                        messages=session_data["messages"],
                        last_activity=session_data["last_activity"]
                    )
                    self._sessions[session_id] = state
            
            logger.info(f"Loaded {len(self._sessions)} sessions from database")
        except Exception as e:
            logger.error(f"Error loading sessions from database: {e}", exc_info=True)
    
    def _persist_session(self, session_id: str) -> None:
        """Persist session to database"""
        try:
            state = self._sessions.get(session_id)
            if state:
                # Convert messages to dict format
                messages = []
                for msg in state.messages:
                    if isinstance(msg, dict):
                        messages.append(msg)
                    else:
                        messages.append(msg.model_dump())
                
                self._db.save_session(
                    session_id=session_id,
                    messages=messages,
                    last_activity=state.last_activity
                )
        except Exception as e:
            logger.error(f"Error persisting session {session_id}: {e}", exc_info=True)

    def exists(self, session_id: str) -> bool:
        """Check if session exists"""
        with self._lock:
            exists = session_id in self._sessions
            logger.debug(f"Session exists check: {session_id} -> {exists}")
            return exists

    def create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
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
        with self._lock:
            if session_id in self._sessions:
                logger.error(f"Attempt to create duplicate session: {session_id}")
                raise ValueError(f"Session {session_id} already exists")
            
            state = SessionState.model_construct(session_id=session_id)
            if system_prompt:
                state.messages.append(
                    Message.model_construct(role="system", content=system_prompt)
                )
            
            self._sessions[session_id] = state
            self._persist_session(session_id)  # Persist to database
            logger.info(f"Created session: {session_id} with {len(state.messages)} initial messages")
            return state

    def get(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                logger.debug(f"Retrieved session: {session_id}")
            else:
                logger.debug(f"Session not found: {session_id}")
            return session

    def get_or_create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        """
        Get existing session or create new one if it doesn't exist.
        
        Args:
            session_id: Unique session identifier
            system_prompt: Optional system prompt for new sessions
            
        Returns:
            Existing or newly created SessionState
        """
        with self._lock:
            if session_id not in self._sessions:
                logger.info(f"Creating new session: {session_id}")
                return self.create(session_id, system_prompt)
            
            logger.debug(f"Found existing session: {session_id}")
            return self._sessions[session_id]

    def append_message(
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
        with self._lock:
            state = self.get(session_id)
            if not state:
                logger.error(f"Cannot append message: session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            
            msg = Message.model_construct(role=role, content=content, name=name)
            state.messages.append(msg)
            state.last_activity = datetime.now(timezone.utc)
            
            self._persist_session(session_id)  # Persist to database
            
            logger.debug(
                f"Appended {role} message to {session_id}: "
                f"{len(content)} chars, total messages: {len(state.messages)}"
            )

    def append_tool_result(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        result: str
    ) -> None:
        """
        Append tool execution result to session history.
        
        Creates a tool message with tool_call_id for OpenAI API compatibility.
        The tool_call_id must match the id from the assistant's tool_call.
        
        Args:
            session_id: Session identifier
            call_id: Tool call ID (must match assistant message tool_call id)
            tool_name: Name of the executed tool
            result: Tool execution result as string
            
        Raises:
            ValueError: If session not found
        """
        with self._lock:
            state = self.get(session_id)
            if not state:
                logger.error(f"Cannot append tool result: session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            
            logger.info(
                f"Appending tool result to {session_id}: "
                f"call_id={call_id}, tool={tool_name}, result_len={len(result)}"
            )
            
            # Create tool message following OpenAI API spec
            # CRITICAL: tool_call_id must match the id from assistant message tool_calls
            tool_message = {
                "role": "tool",
                "content": result,
                "tool_call_id": call_id,
                "name": tool_name
            }
            
            state.messages.append(tool_message)
            state.last_activity = datetime.now(timezone.utc)
            
            self._persist_session(session_id)  # Persist to database
            
            logger.debug(
                f"Tool result appended: call_id={call_id}, "
                f"total messages: {len(state.messages)}"
            )

    def get_history(self, session_id: str) -> List[dict]:
        """
        Get session message history as list of dicts for LLM.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dictionaries
        """
        with self._lock:
            state = self.get(session_id)
            if not state:
                logger.warning(f"Cannot get history: session {session_id} not found")
                return []
            
            # Convert messages to dict format
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
        with self._lock:
            sessions = list(self._sessions.values())
            logger.debug(f"Retrieved all sessions: {len(sessions)} total")
            return sessions

    def delete(self, session_id: str) -> None:
        """Delete a session"""
        with self._lock:
            if session_id in self._sessions:
                logger.info(f"Deleting session: {session_id}")
                del self._sessions[session_id]
                self._db.delete_session(session_id)  # Delete from database
            else:
                logger.warning(f"Cannot delete: session {session_id} not found")


# Singleton instance for global use
_session_manager_instance: Optional[SessionManager] = None


def get_session_manager(db: Database = None) -> SessionManager:
    """
    Get SessionManager instance for dependency injection.
    
    Args:
        db: Optional database instance
        
    Returns:
        SessionManager instance
    """
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionManager(db)
    return _session_manager_instance


# Convenience accessor for backward compatibility
session_manager = get_session_manager()

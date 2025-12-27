import logging
import pprint
from datetime import datetime
from threading import RLock
from typing import Dict, List, Optional

from app.models.schemas import SessionState

logger = logging.getLogger("agent-runtime.session_manager")


class SessionManager:
    """
    Управляет всеми сессиями: создание, доступ, изменение сообщений.
    В будущем можно заменить in-memory storage на persistent storage (например, Redis/BoltDB).
    """

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = RLock()

    def exists(self, session_id: str) -> bool:
        with self._lock:
            exists = session_id in self._sessions
            logger.debug(f"Session exists check: {session_id} -> {exists}")
            return exists

    def create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        from app.models.schemas import Message

        with self._lock:
            if session_id in self._sessions:
                logger.error(f"[SessionManager] Attempt to create duplicate session: {session_id}")
                raise ValueError(f"Session {session_id} already exists")
            state = SessionState.model_construct(session_id=session_id)
            if system_prompt:
                state.messages.append(Message.model_construct(role="system", content=system_prompt))
            self._sessions[session_id] = state
            logger.info(
                f"[SessionManager] Created session: {session_id}. State:\n"
                + pprint.pformat(state.model_dump(), indent=2, width=120)
            )
            return state

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            session = self._sessions.get(session_id)
            logger.debug(
                f"[SessionManager] Get session: {session_id} -> {'found' if session else 'not found'}"
            )
            return session

    def get_or_create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                logger.info(f"[SessionManager] Creating new session in get_or_create: {session_id}")
                return self.create(session_id, system_prompt)
            logger.debug(f"[SessionManager] Found existing session in get_or_create: {session_id}")
            return self._sessions[session_id]

    def append_message(self, session_id: str, role: str, content: str, name: Optional[str] = None):
        from app.models.schemas import Message

        with self._lock:
            state = self.get(session_id)
            if not state:
                logger.error(f"[SessionManager] append_message: Session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            msg = Message.model_construct(role=role, content=content, name=name)
            state.messages.append(msg)
            state.last_activity = datetime.now()
            logger.debug(
                f"[SessionManager] Appended message to {session_id}:\n"
                + pprint.pformat(msg.model_dump(), indent=2, width=120)
            )
            logger.debug(
                f"[SessionManager] New session messages for {session_id}:\n"
                + pprint.pformat([m.model_dump() for m in state.messages], indent=2, width=120)
            )

    def append_tool_result(self, session_id: str, tool_name: str, result: str):
        """
        Добавляет tool_result в историю сессии как function message.
        Используется для добавления результатов выполнения инструментов.
        """
        from app.models.schemas import Message

        with self._lock:
            state = self.get(session_id)
            if not state:
                logger.error(f"[SessionManager] append_tool_result: Session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            msg = Message.model_construct(role="function", content=result, name=tool_name)
            state.messages.append(msg)
            state.last_activity = datetime.now()
            logger.debug(
                f"[SessionManager] Appended tool_result to {session_id}:\n"
                + pprint.pformat(msg.model_dump(), indent=2, width=120)
            )

    def get_history(self, session_id: str) -> List[dict]:
        """
        Возвращает историю сообщений сессии в виде списка dict.
        Используется для передачи в LLM.
        """
        with self._lock:
            state = self.get(session_id)
            if not state:
                logger.warning(f"[SessionManager] get_history: Session {session_id} not found")
                return []
            history = [m.model_dump() for m in state.messages]
            logger.debug(
                f"[SessionManager] Retrieved history for {session_id}: {len(history)} messages"
            )
            return history

    def all_sessions(self) -> List[SessionState]:
        with self._lock:
            logger.debug(
                f"[SessionManager] all_sessions called, found {len(self._sessions)} sessions"
            )
            return list(self._sessions.values())

    def delete(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                logger.info(f"[SessionManager] Deleting session: {session_id}")
                del self._sessions[session_id]
            else:
                logger.warning(
                    f"[SessionManager] Tried to delete non-existent session: {session_id}"
                )


# Singleton instance for global use
session_manager = SessionManager()

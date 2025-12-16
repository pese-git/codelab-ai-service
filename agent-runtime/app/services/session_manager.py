from datetime import datetime
from threading import RLock
from typing import Dict, List, Optional

from app.models.schemas import SessionState


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
            return session_id in self._sessions

    def create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"Session {session_id} already exists")
            state = SessionState.model_construct(session_id=session_id)
            if system_prompt:
                state.messages.append({"role": "system", "content": system_prompt})
            self._sessions[session_id] = state
            return state

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_or_create(self, session_id: str, system_prompt: Optional[str] = None) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                return self.create(session_id, system_prompt)
            return self._sessions[session_id]

    def append_message(self, session_id: str, role: str, content: str):
        with self._lock:
            state = self.get(session_id)
            if not state:
                raise ValueError(f"Session {session_id} not found")
            state.messages.append({"role": role, "content": content})
            state.last_activity = datetime.now()

    def all_sessions(self) -> List[SessionState]:
        with self._lock:
            return list(self._sessions.values())

    def delete(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]


# Singleton instance for global use
session_manager = SessionManager()

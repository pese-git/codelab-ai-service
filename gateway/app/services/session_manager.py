import asyncio
from typing import Dict, Optional

from fastapi import WebSocket


class SessionManager:
    """Управляет активными WebSocket-сессиями: хранит, отдаёт, удаляет."""

    def __init__(self):
        self._active_websockets: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def add(self, session_id: str, websocket: WebSocket):
        async with self._lock:
            self._active_websockets[session_id] = websocket

    async def get(self, session_id: str) -> Optional[WebSocket]:
        async with self._lock:
            return self._active_websockets.get(session_id)

    async def remove(self, session_id: str):
        async with self._lock:
            self._active_websockets.pop(session_id, None)

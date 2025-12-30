import asyncio
from typing import Dict, List

class TokenBufferManager:
    """
    Асинхронный менеджер для хранения и управления token_buffers (session_id -> List[str]).
    Безопасен для многопоточности.
    """
    def __init__(self):
        self._buffers: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> List[str]:
        async with self._lock:
            return self._buffers.setdefault(session_id, [])

    async def remove(self, session_id: str):
        async with self._lock:
            self._buffers.pop(session_id, None)

    async def set(self, session_id: str, buffer: List[str]):
        async with self._lock:
            self._buffers[session_id] = buffer

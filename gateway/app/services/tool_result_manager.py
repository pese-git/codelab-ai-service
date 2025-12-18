import asyncio
from typing import Dict, Any, Optional

class ToolResultManager:
    """Хранит pending tool results (call_id -> future), thread-safe."""
    def __init__(self):
        self._pending: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def register(self, call_id: str) -> asyncio.Future:
        async with self._lock:
            fut = asyncio.get_event_loop().create_future()
            self._pending[call_id] = fut
            return fut

    async def resolve(self, call_id: str, result: Any):
        async with self._lock:
            fut = self._pending.pop(call_id, None)
            if fut and not fut.done():
                fut.set_result(result)

    async def reject(self, call_id: str, exc: Exception):
        async with self._lock:
            fut = self._pending.pop(call_id, None)
            if fut and not fut.done():
                fut.set_exception(exc)

    async def pop(self, call_id: str) -> Optional[asyncio.Future]:
        async with self._lock:
            return self._pending.pop(call_id, None)

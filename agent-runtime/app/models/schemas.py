"""
Common schemas - алиасы для обратной совместимости.

Этот модуль предоставляет алиасы для схем из app.api.v1.schemas.common
для обратной совместимости с существующим кодом.
"""

from app.api.v1.schemas.common import StreamChunk, ToolCall
from app.domain.entities.message import Message

__all__ = ["StreamChunk", "ToolCall", "Message"]

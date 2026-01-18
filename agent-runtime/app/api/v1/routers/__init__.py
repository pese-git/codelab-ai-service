"""
API роутеры v1.

Этот модуль содержит все роутеры для API v1.
Каждый роутер отвечает за свою область функциональности.
"""

from .health_router import router as health_router
from .sessions_router import router as sessions_router
from .messages_router import router as messages_router
from .agents_router import router as agents_router

__all__ = [
    "health_router",
    "sessions_router",
    "messages_router",
    "agents_router",
]

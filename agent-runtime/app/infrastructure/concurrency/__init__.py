"""
Управление конкурентностью.

Этот модуль содержит механизмы для безопасной работы
с конкурентными операциями.
"""

from .session_lock import SessionLockManager, session_lock_manager

__all__ = [
    "SessionLockManager",
    "session_lock_manager",
]

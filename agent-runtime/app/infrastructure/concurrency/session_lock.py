"""
Session-level locks для предотвращения race conditions.

Обеспечивает безопасный конкурентный доступ к сессиям.
"""

import asyncio
import logging
from typing import Dict
from contextlib import asynccontextmanager

logger = logging.getLogger("agent-runtime.infrastructure.session_lock")


class SessionLockManager:
    """
    Менеджер блокировок на уровне сессий.
    
    Предотвращает race conditions при одновременном доступе
    к одной сессии из разных запросов.
    
    Использует отдельную блокировку для каждой сессии,
    что позволяет параллельно обрабатывать разные сессии.
    
    Атрибуты:
        _locks: Словарь блокировок по session_id
        _global_lock: Глобальная блокировка для управления словарем
    
    Пример:
        >>> lock_manager = SessionLockManager()
        >>> async with lock_manager.lock("session-1"):
        ...     # Безопасная работа с сессией
        ...     session = await get_session("session-1")
        ...     session.add_message(...)
    """
    
    def __init__(self):
        """Инициализация менеджера блокировок"""
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        logger.info("SessionLockManager initialized")
    
    @asynccontextmanager
    async def lock(self, session_id: str):
        """
        Получить блокировку для сессии.
        
        Создает новую блокировку если её нет, или использует существующую.
        Автоматически освобождает блокировку при выходе из контекста.
        
        Args:
            session_id: ID сессии для блокировки
            
        Yields:
            None
            
        Пример:
            >>> async with lock_manager.lock("session-1"):
            ...     # Только один запрос может выполнять этот код одновременно
            ...     # для session-1
            ...     await process_message(session_id="session-1", ...)
        """
        # Получить или создать блокировку для сессии
        async with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
                logger.debug(f"Created new lock for session {session_id}")
            lock = self._locks[session_id]
        
        # Захватить блокировку сессии
        logger.debug(f"Acquiring lock for session {session_id}")
        async with lock:
            logger.debug(f"Lock acquired for session {session_id}")
            try:
                yield
            finally:
                logger.debug(f"Lock released for session {session_id}")
    
    async def cleanup_unused_locks(self, max_locks: int = 1000):
        """
        Очистить неиспользуемые блокировки.
        
        Удаляет блокировки для сессий, которые не используются,
        чтобы предотвратить утечку памяти.
        
        Args:
            max_locks: Максимальное количество блокировок
            
        Returns:
            Количество удаленных блокировок
            
        Пример:
            >>> count = await lock_manager.cleanup_unused_locks()
            >>> print(f"Cleaned up {count} unused locks")
        """
        async with self._global_lock:
            if len(self._locks) <= max_locks:
                return 0
            
            # Найти неиспользуемые блокировки (не захвачены)
            unused = []
            for session_id, lock in self._locks.items():
                if not lock.locked():
                    unused.append(session_id)
            
            # Удалить старые неиспользуемые блокировки
            # Оставляем только max_locks самых новых
            to_remove = len(self._locks) - max_locks
            if to_remove > 0:
                for session_id in unused[:to_remove]:
                    del self._locks[session_id]
                
                logger.info(f"Cleaned up {to_remove} unused session locks")
                return to_remove
            
            return 0
    
    def get_lock_count(self) -> int:
        """
        Получить количество активных блокировок.
        
        Returns:
            Количество блокировок
        """
        return len(self._locks)
    
    def is_locked(self, session_id: str) -> bool:
        """
        Проверить, заблокирована ли сессия.
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если сессия заблокирована
        """
        lock = self._locks.get(session_id)
        return lock.locked() if lock else False


# Глобальный singleton instance
session_lock_manager = SessionLockManager()

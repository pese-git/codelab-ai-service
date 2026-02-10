"""
Request Deduplicator для предотвращения дублирования обработки запросов.

Использует in-memory cache с TTL для отслеживания обработанных запросов.
"""

import logging
import time
from typing import Optional, Dict, Tuple
from threading import Lock

logger = logging.getLogger("agent-runtime.infrastructure.request_deduplicator")


class RequestDeduplicator:
    """
    Дедупликатор запросов с TTL-based cache.
    
    Отслеживает обработанные запросы и предотвращает их повторную обработку
    в течение заданного времени (TTL).
    
    Атрибуты:
        _cache: Словарь {request_key: (timestamp, result)}
        _lock: Lock для thread-safe операций
        _ttl_seconds: Время жизни записи в кэше (секунды)
        _max_cache_size: Максимальный размер кэша
    
    Пример:
        >>> deduplicator = RequestDeduplicator(ttl_seconds=60)
        >>> 
        >>> # Проверить, был ли запрос обработан
        >>> if deduplicator.is_duplicate("session-123", "call-456"):
        ...     print("Duplicate request, skipping")
        ...     return
        >>> 
        >>> # Отметить запрос как обработанный
        >>> deduplicator.mark_processed("session-123", "call-456")
    """
    
    def __init__(
        self,
        ttl_seconds: int = 60,
        max_cache_size: int = 10000
    ):
        """
        Инициализация дедупликатора.
        
        Args:
            ttl_seconds: Время жизни записи в кэше (по умолчанию 60 секунд)
            max_cache_size: Максимальный размер кэша (по умолчанию 10000)
        """
        self._cache: Dict[str, Tuple[float, Optional[str]]] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._max_cache_size = max_cache_size
        
        logger.info(
            f"RequestDeduplicator инициализирован "
            f"(ttl={ttl_seconds}s, max_size={max_cache_size})"
        )
    
    def is_duplicate(
        self,
        session_id: str,
        request_id: str
    ) -> bool:
        """
        Проверить, был ли запрос уже обработан.
        
        Args:
            session_id: ID сессии
            request_id: ID запроса (например, call_id для tool_result)
            
        Returns:
            True если запрос уже обрабатывался, False иначе
        """
        key = self._make_key(session_id, request_id)
        
        with self._lock:
            # Очистить устаревшие записи
            self._cleanup_expired()
            
            if key in self._cache:
                timestamp, _ = self._cache[key]
                age = time.time() - timestamp
                
                if age < self._ttl_seconds:
                    logger.warning(
                        f"🔄 Duplicate request detected: "
                        f"session={session_id}, request_id={request_id}, "
                        f"age={age:.2f}s"
                    )
                    return True
                else:
                    # Запись устарела, удаляем
                    del self._cache[key]
        
        return False
    
    def mark_processed(
        self,
        session_id: str,
        request_id: str,
        result: Optional[str] = None
    ) -> None:
        """
        Отметить запрос как обработанный.
        
        Args:
            session_id: ID сессии
            request_id: ID запроса
            result: Результат обработки (опционально)
        """
        key = self._make_key(session_id, request_id)
        
        with self._lock:
            # Проверить размер кэша
            if len(self._cache) >= self._max_cache_size:
                logger.warning(
                    f"⚠️ Cache size limit reached ({self._max_cache_size}), "
                    f"cleaning up old entries"
                )
                self._cleanup_oldest()
            
            self._cache[key] = (time.time(), result)
            
            logger.debug(
                f"✅ Request marked as processed: "
                f"session={session_id}, request_id={request_id}"
            )
    
    def get_result(
        self,
        session_id: str,
        request_id: str
    ) -> Optional[str]:
        """
        Получить результат обработки запроса (если есть).
        
        Args:
            session_id: ID сессии
            request_id: ID запроса
            
        Returns:
            Результат обработки или None
        """
        key = self._make_key(session_id, request_id)
        
        with self._lock:
            if key in self._cache:
                timestamp, result = self._cache[key]
                age = time.time() - timestamp
                
                if age < self._ttl_seconds:
                    return result
                else:
                    del self._cache[key]
        
        return None
    
    def clear(self) -> None:
        """Очистить весь кэш."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """
        Получить статистику кэша.
        
        Returns:
            Словарь со статистикой
        """
        with self._lock:
            return {
                "cache_size": len(self._cache),
                "max_cache_size": self._max_cache_size,
                "ttl_seconds": self._ttl_seconds
            }
    
    def _make_key(self, session_id: str, request_id: str) -> str:
        """Создать ключ для кэша."""
        return f"{session_id}:{request_id}"
    
    def _cleanup_expired(self) -> None:
        """Удалить устаревшие записи из кэша."""
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self._cache.items()
            if current_time - timestamp >= self._ttl_seconds
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
    
    def _cleanup_oldest(self) -> None:
        """Удалить 20% самых старых записей."""
        if not self._cache:
            return
        
        # Сортировать по timestamp
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1][0]
        )
        
        # Удалить 20% самых старых
        remove_count = max(1, len(sorted_items) // 5)
        for key, _ in sorted_items[:remove_count]:
            del self._cache[key]
        
        logger.debug(f"Cleaned up {remove_count} oldest entries")


# Singleton instance
_deduplicator_instance: Optional[RequestDeduplicator] = None


def get_request_deduplicator() -> RequestDeduplicator:
    """
    Получить singleton instance дедупликатора.
    
    Returns:
        RequestDeduplicator instance
    """
    global _deduplicator_instance
    
    if _deduplicator_instance is None:
        _deduplicator_instance = RequestDeduplicator(
            ttl_seconds=60,  # 1 минута
            max_cache_size=10000
        )
    
    return _deduplicator_instance

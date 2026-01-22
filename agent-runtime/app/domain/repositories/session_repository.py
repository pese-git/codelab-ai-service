"""
Интерфейс репозитория сессий.

Определяет контракт для работы с сессиями диалога.
"""

from abc import abstractmethod
from typing import List, Optional
from datetime import datetime

from .base import Repository
from ..entities.session import Session


class SessionRepository(Repository[Session]):
    """
    Интерфейс репозитория для сессий.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с сессиями.
    
    Пример:
        >>> class SessionRepositoryImpl(SessionRepository):
        ...     async def find_by_id(self, session_id: str):
        ...         # Реализация поиска сессии
        ...         pass
    """
    
    @abstractmethod
    async def find_by_id(self, session_id: str) -> Optional[Session]:
        """
        Найти сессию по ID.
        
        Args:
            session_id: Уникальный идентификатор сессии
            
        Returns:
            Сессия если найдена, None иначе
            
        Пример:
            >>> session = await repository.find_by_id("session-123")
            >>> if session:
            ...     print(f"Found session with {session.get_message_count()} messages")
        """
        pass
    
    @abstractmethod
    async def find_active(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """
        Найти активные сессии.
        
        Возвращает только сессии с is_active=True,
        отсортированные по last_activity (новые первыми).
        
        Args:
            limit: Максимальное количество сессий
            offset: Смещение от начала списка
            
        Returns:
            Список активных сессий
            
        Пример:
            >>> active_sessions = await repository.find_active(limit=10)
            >>> for session in active_sessions:
            ...     print(f"Session {session.id}: {session.title}")
        """
        pass
    
    @abstractmethod
    async def find_by_activity_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[Session]:
        """
        Найти сессии по диапазону активности.
        
        Полезно для аналитики и отчетов.
        
        Args:
            start_time: Начало диапазона
            end_time: Конец диапазона
            limit: Максимальное количество сессий
            
        Returns:
            Список сессий в указанном диапазоне
            
        Пример:
            >>> from datetime import timedelta
            >>> now = datetime.now(timezone.utc)
            >>> yesterday = now - timedelta(days=1)
            >>> recent = await repository.find_by_activity_range(
            ...     start_time=yesterday,
            ...     end_time=now
            ... )
        """
        pass
    
    @abstractmethod
    async def cleanup_old(
        self,
        max_age_hours: int = 24,
        batch_size: int = 100
    ) -> int:
        """
        Очистить старые неактивные сессии.
        
        Деактивирует или удаляет сессии, которые не были
        активны в течение указанного времени.
        
        Args:
            max_age_hours: Максимальный возраст сессии в часах
            batch_size: Размер батча для обработки
            
        Returns:
            Количество очищенных сессий
            
        Пример:
            >>> # Очистить сессии старше 24 часов
            >>> count = await repository.cleanup_old(max_age_hours=24)
            >>> print(f"Cleaned up {count} old sessions")
        """
        pass
    
    @abstractmethod
    async def count_active(self) -> int:
        """
        Подсчитать количество активных сессий.
        
        Returns:
            Количество активных сессий
            
        Пример:
            >>> active_count = await repository.count_active()
            >>> print(f"Active sessions: {active_count}")
        """
        pass

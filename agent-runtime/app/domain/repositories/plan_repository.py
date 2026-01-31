"""
Интерфейс репозитория планов.

Определяет контракт для работы с планами выполнения задач.
"""

from abc import abstractmethod
from typing import List, Optional

from .base import Repository
from ..entities.plan import Plan, PlanStatus


class PlanRepository(Repository[Plan]):
    """
    Интерфейс репозитория для планов.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с планами.
    
    Пример:
        >>> class PlanRepositoryImpl(PlanRepository):
        ...     async def find_by_id(self, plan_id: str):
        ...         # Реализация поиска плана
        ...         pass
    """
    
    @abstractmethod
    async def find_by_id(self, plan_id: str) -> Optional[Plan]:
        """
        Найти план по ID.
        
        Args:
            plan_id: Уникальный идентификатор плана
            
        Returns:
            План если найден, None иначе
            
        Пример:
            >>> plan = await repository.find_by_id("plan-123")
            >>> if plan:
            ...     print(f"Found plan with {len(plan.subtasks)} subtasks")
        """
        pass
    
    @abstractmethod
    async def find_by_session_id(self, session_id: str) -> Optional[Plan]:
        """
        Найти активный план для сессии.
        
        Возвращает последний план в статусе IN_PROGRESS или APPROVED.
        Если таких нет, возвращает None.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Активный план или None
            
        Пример:
            >>> plan = await repository.find_by_session_id("session-123")
            >>> if plan:
            ...     next_task = plan.get_next_subtask()
        """
        pass
    
    @abstractmethod
    async def find_all_by_session_id(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Plan]:
        """
        Найти все планы для сессии.
        
        Возвращает планы отсортированные по created_at (новые первыми).
        Полезно для истории планов и аналитики.
        
        Args:
            session_id: ID сессии
            limit: Максимальное количество планов
            offset: Смещение от начала списка
            
        Returns:
            Список планов
            
        Пример:
            >>> plans = await repository.find_all_by_session_id(
            ...     "session-123",
            ...     limit=10
            ... )
            >>> for plan in plans:
            ...     print(f"Plan {plan.id}: {plan.status.value}")
        """
        pass
    
    @abstractmethod
    async def find_by_status(
        self,
        status: PlanStatus,
        limit: int = 100
    ) -> List[Plan]:
        """
        Найти планы по статусу.
        
        Полезно для мониторинга и отладки.
        
        Args:
            status: Статус плана
            limit: Максимальное количество планов
            
        Returns:
            Список планов с указанным статусом
            
        Пример:
            >>> in_progress = await repository.find_by_status(
            ...     PlanStatus.IN_PROGRESS
            ... )
            >>> print(f"Plans in progress: {len(in_progress)}")
        """
        pass
    
    @abstractmethod
    async def count_by_session(self, session_id: str) -> int:
        """
        Подсчитать количество планов для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Количество планов
            
        Пример:
            >>> count = await repository.count_by_session("session-123")
            >>> print(f"Session has {count} plans")
        """
        pass

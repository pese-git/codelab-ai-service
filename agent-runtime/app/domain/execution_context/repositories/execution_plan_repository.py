"""
Repository Interface для ExecutionPlan.

Определяет контракт для работы с планами выполнения.
"""

from abc import abstractmethod
from typing import List, Optional

from app.domain.shared.repository import Repository
from app.domain.execution_context.entities import ExecutionPlan
from app.domain.execution_context.value_objects import PlanId, PlanStatus
from app.domain.session_context.value_objects import ConversationId


class ExecutionPlanRepository(Repository[ExecutionPlan, PlanId]):
    """
    Интерфейс репозитория для планов выполнения.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с планами.
    
    Example:
        >>> class ExecutionPlanRepositoryImpl(ExecutionPlanRepository):
        ...     async def find_by_id(self, plan_id: PlanId):
        ...         # Реализация поиска плана
        ...         pass
    """
    
    @abstractmethod
    async def find_by_id(self, plan_id: PlanId) -> Optional[ExecutionPlan]:
        """
        Найти план по ID.
        
        Args:
            plan_id: Уникальный идентификатор плана
            
        Returns:
            План если найден, None иначе
            
        Example:
            >>> plan = await repository.find_by_id(PlanId("plan-123"))
            >>> if plan:
            ...     print(f"Found plan with {len(plan.subtasks)} subtasks")
        """
        pass
    
    @abstractmethod
    async def find_by_conversation_id(
        self,
        conversation_id: ConversationId
    ) -> Optional[ExecutionPlan]:
        """
        Найти активный план для диалога.
        
        Возвращает последний план в статусе IN_PROGRESS или APPROVED.
        Если таких нет, возвращает None.
        
        Args:
            conversation_id: ID диалога
            
        Returns:
            Активный план или None
            
        Example:
            >>> plan = await repository.find_by_conversation_id(
            ...     ConversationId("conv-123")
            ... )
            >>> if plan:
            ...     next_task = plan.get_next_subtask()
        """
        pass
    
    @abstractmethod
    async def find_all_by_conversation_id(
        self,
        conversation_id: ConversationId,
        limit: int = 50,
        offset: int = 0
    ) -> List[ExecutionPlan]:
        """
        Найти все планы для диалога.
        
        Возвращает планы отсортированные по created_at (новые первыми).
        Полезно для истории планов и аналитики.
        
        Args:
            conversation_id: ID диалога
            limit: Максимальное количество планов
            offset: Смещение от начала списка
            
        Returns:
            Список планов
            
        Example:
            >>> plans = await repository.find_all_by_conversation_id(
            ...     ConversationId("conv-123"),
            ...     limit=10
            ... )
            >>> for plan in plans:
            ...     print(f"Plan {plan.id}: {plan.status}")
        """
        pass
    
    @abstractmethod
    async def find_by_status(
        self,
        status: PlanStatus,
        limit: int = 100
    ) -> List[ExecutionPlan]:
        """
        Найти планы по статусу.
        
        Полезно для мониторинга и отладки.
        
        Args:
            status: Статус плана
            limit: Максимальное количество планов
            
        Returns:
            Список планов с указанным статусом
            
        Example:
            >>> in_progress = await repository.find_by_status(
            ...     PlanStatus.in_progress()
            ... )
            >>> print(f"Plans in progress: {len(in_progress)}")
        """
        pass
    
    @abstractmethod
    async def count_by_conversation(self, conversation_id: ConversationId) -> int:
        """
        Подсчитать количество планов для диалога.
        
        Args:
            conversation_id: ID диалога
            
        Returns:
            Количество планов
            
        Example:
            >>> count = await repository.count_by_conversation(
            ...     ConversationId("conv-123")
            ... )
            >>> print(f"Conversation has {count} plans")
        """
        pass
    
    @abstractmethod
    async def save(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Сохранить план.
        
        Создает новый план или обновляет существующий.
        
        Args:
            plan: План для сохранения
            
        Returns:
            Сохраненный план
            
        Example:
            >>> plan = ExecutionPlan(id=PlanId("plan-1"), ...)
            >>> saved_plan = await repository.save(plan)
        """
        pass
    
    @abstractmethod
    async def delete(self, plan_id: PlanId) -> bool:
        """
        Удалить план.
        
        Args:
            plan_id: ID плана для удаления
            
        Returns:
            True если план был удален, False если не найден
            
        Example:
            >>> deleted = await repository.delete(PlanId("plan-123"))
            >>> if deleted:
            ...     print("Plan deleted successfully")
        """
        pass

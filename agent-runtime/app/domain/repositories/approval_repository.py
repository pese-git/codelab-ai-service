"""
Интерфейс репозитория для approval requests.

Определяет контракт для работы с запросами на одобрение (approvals).
"""

from abc import abstractmethod
from typing import List, Optional
from datetime import datetime

from .base import Repository
from ..entities.approval import PendingApprovalState


class ApprovalRepository(Repository[PendingApprovalState]):
    """
    Интерфейс репозитория для approval requests.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с запросами на одобрение.
    
    Пример:
        >>> class ApprovalRepositoryImpl(ApprovalRepository):
        ...     async def save_pending(self, request_id: str, ...):
        ...         # Реализация сохранения approval request
        ...         pass
    """
    
    @abstractmethod
    async def save_pending(
        self,
        request_id: str,
        request_type: str,
        subject: str,
        session_id: str,
        details: dict,
        reason: Optional[str] = None
    ) -> None:
        """
        Сохранить pending approval request.
        
        Args:
            request_id: Уникальный идентификатор запроса
            request_type: Тип запроса ("tool", "plan", etc.)
            subject: Предмет запроса (имя инструмента, название плана)
            session_id: Идентификатор сессии
            details: Детали запроса (гибкий JSON формат)
            reason: Причина, почему требуется одобрение
            
        Raises:
            ValueError: Если request_id уже существует
            
        Пример:
            >>> await repository.save_pending(
            ...     request_id="req-123",
            ...     request_type="tool",
            ...     subject="write_file",
            ...     session_id="session-abc",
            ...     details={"path": "test.py", "content": "..."},
            ...     reason="File modification requires approval"
            ... )
        """
        pass
    
    @abstractmethod
    async def get_pending(self, request_id: str) -> Optional[PendingApprovalState]:
        """
        Получить pending approval по request_id.
        
        Args:
            request_id: Идентификатор запроса
            
        Returns:
            PendingApprovalState если найден, None иначе
            
        Пример:
            >>> approval = await repository.get_pending("req-123")
            >>> if approval:
            ...     print(f"Found approval: {approval.subject}")
        """
        pass
    
    @abstractmethod
    async def get_all_pending(
        self,
        session_id: str,
        request_type: Optional[str] = None
    ) -> List[PendingApprovalState]:
        """
        Получить все pending approvals для сессии.
        
        Используется IDE для восстановления pending requests после перезапуска.
        
        Args:
            session_id: Идентификатор сессии
            request_type: Опциональный фильтр по типу запроса
            
        Returns:
            Список pending approval requests
            
        Пример:
            >>> # Получить все pending approvals для сессии
            >>> approvals = await repository.get_all_pending("session-abc")
            >>> 
            >>> # Получить только tool approvals
            >>> tool_approvals = await repository.get_all_pending(
            ...     "session-abc",
            ...     request_type="tool"
            ... )
        """
        pass
    
    @abstractmethod
    async def update_status(
        self,
        request_id: str,
        status: str,
        decision_at: datetime,
        decision_reason: Optional[str] = None
    ) -> bool:
        """
        Обновить статус approval request.
        
        Args:
            request_id: Идентификатор запроса
            status: Новый статус ("approved", "rejected")
            decision_at: Время принятия решения
            decision_reason: Причина отклонения (опционально)
            
        Returns:
            True если обновлено, False если не найдено
            
        Пример:
            >>> success = await repository.update_status(
            ...     request_id="req-123",
            ...     status="approved",
            ...     decision_at=datetime.now(timezone.utc)
            ... )
        """
        pass
    
    @abstractmethod
    async def delete_pending(self, request_id: str) -> bool:
        """
        Удалить pending approval request.
        
        Args:
            request_id: Идентификатор запроса
            
        Returns:
            True если удалено, False если не найдено
            
        Пример:
            >>> deleted = await repository.delete_pending("req-123")
            >>> if deleted:
            ...     print("Approval request deleted")
        """
        pass
    
    @abstractmethod
    async def count_pending(self, session_id: str) -> int:
        """
        Подсчитать количество pending approvals для сессии.
        
        Args:
            session_id: Идентификатор сессии
            
        Returns:
            Количество pending approvals
            
        Пример:
            >>> count = await repository.count_pending("session-abc")
            >>> print(f"Pending approvals: {count}")
        """
        pass

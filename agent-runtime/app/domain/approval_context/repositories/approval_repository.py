"""
ApprovalRepository Interface.

Типобезопасный интерфейс репозитория для запросов на утверждение.
"""

from abc import abstractmethod
from typing import List, Optional

from app.domain.shared.repository import Repository
from ..entities.approval_request import ApprovalRequest
from ..value_objects.approval_id import ApprovalId
from ..value_objects.approval_status import ApprovalStatus


class ApprovalRepository(Repository[ApprovalRequest, ApprovalId]):
    """
    Типобезопасный интерфейс репозитория для запросов на утверждение.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с утверждениями.
    
    Примеры:
        >>> class ApprovalRepositoryImpl(ApprovalRepository):
        ...     async def find_by_id(self, approval_id: ApprovalId):
        ...         # Реализация поиска по ID
        ...         pass
    """
    
    @abstractmethod
    async def find_by_id(
        self,
        approval_id: ApprovalId,
    ) -> Optional[ApprovalRequest]:
        """
        Найти запрос на утверждение по ID.
        
        Args:
            approval_id: ID запроса
            
        Returns:
            ApprovalRequest если найден, None иначе
            
        Примеры:
            >>> approval_id = ApprovalId("req-tool-123")
            >>> request = await repository.find_by_id(approval_id)
            >>> if request:
            ...     print(f"Found: {request.subject}")
        """
        pass
    
    @abstractmethod
    async def find_pending_by_session(
        self,
        session_id: str,
    ) -> List[ApprovalRequest]:
        """
        Найти все ожидающие утверждения для сессии.
        
        Возвращает только запросы со статусом PENDING.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список ApprovalRequest со статусом PENDING
            
        Примеры:
            >>> pending = await repository.find_pending_by_session("session-abc")
            >>> for request in pending:
            ...     print(f"Pending: {request.subject}")
        """
        pass
    
    @abstractmethod
    async def find_by_session(
        self,
        session_id: str,
        status: Optional[ApprovalStatus] = None,
    ) -> List[ApprovalRequest]:
        """
        Найти все утверждения для сессии с опциональной фильтрацией по статусу.
        
        Args:
            session_id: ID сессии
            status: Опциональный фильтр по статусу
            
        Returns:
            Список ApprovalRequest
            
        Примеры:
            >>> # Все утверждения для сессии
            >>> all_requests = await repository.find_by_session("session-abc")
            >>> 
            >>> # Только одобренные
            >>> approved = await repository.find_by_session(
            ...     "session-abc",
            ...     ApprovalStatus(ApprovalStatusEnum.APPROVED)
            ... )
        """
        pass
    
    @abstractmethod
    async def save(self, approval: ApprovalRequest) -> None:
        """
        Сохранить запрос на утверждение.
        
        Создает новый запрос или обновляет существующий.
        
        Args:
            approval: Запрос для сохранения
            
        Примеры:
            >>> request = ApprovalRequest.create(...)
            >>> await repository.save(request)
        """
        pass
    
    @abstractmethod
    async def delete(self, approval_id: ApprovalId) -> bool:
        """
        Удалить запрос на утверждение.
        
        Args:
            approval_id: ID запроса для удаления
            
        Returns:
            True если удален, False если не найден
            
        Примеры:
            >>> approval_id = ApprovalId("req-tool-123")
            >>> deleted = await repository.delete(approval_id)
        """
        pass
    
    @abstractmethod
    async def count_pending(self, session_id: str) -> int:
        """
        Подсчитать количество ожидающих утверждений для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Количество запросов со статусом PENDING
            
        Примеры:
            >>> count = await repository.count_pending("session-abc")
            >>> print(f"Pending approvals: {count}")
        """
        pass
    
    @abstractmethod
    async def find_expired(
        self,
        session_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """
        Найти истекшие запросы (превысили timeout).
        
        Args:
            session_id: Опциональный фильтр по сессии
            
        Returns:
            Список ApprovalRequest, которые истекли
            
        Примеры:
            >>> expired = await repository.find_expired()
            >>> for request in expired:
            ...     await request.expire()
            ...     await repository.save(request)
        """
        pass

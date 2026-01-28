"""
Интерфейс репозитория HITL (Human-in-the-Loop).

Определяет контракт для работы с HITL pending approvals и audit logs.
"""

from abc import abstractmethod
from typing import List, Optional

from .base import Repository
from ..entities.hitl import HITLPendingState, HITLAuditLog


class HITLRepository(Repository[HITLPendingState]):
    """
    Интерфейс репозитория для HITL операций.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с HITL pending approvals.
    
    Пример:
        >>> class HITLRepositoryImpl(HITLRepository):
        ...     async def find_by_session_id(self, session_id: str):
        ...         # Реализация поиска pending approvals
        ...         pass
    """
    
    @abstractmethod
    async def find_by_session_id(
        self,
        session_id: str
    ) -> List[HITLPendingState]:
        """
        Найти все pending approvals для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список pending approvals для сессии
            
        Пример:
            >>> pending = await repository.find_by_session_id("session-123")
            >>> for approval in pending:
            ...     print(f"Tool: {approval.tool_name}, Call ID: {approval.call_id}")
        """
        pass
    
    @abstractmethod
    async def find_by_call_id(
        self,
        session_id: str,
        call_id: str
    ) -> Optional[HITLPendingState]:
        """
        Найти pending approval по call_id.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call
            
        Returns:
            Pending approval если найден, None иначе
            
        Пример:
            >>> approval = await repository.find_by_call_id(
            ...     "session-123",
            ...     "call-456"
            ... )
            >>> if approval:
            ...     print(f"Found pending approval for {approval.tool_name}")
        """
        pass
    
    @abstractmethod
    async def save_pending(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict,
        reason: Optional[str] = None
    ) -> HITLPendingState:
        """
        Сохранить pending approval.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call (уникальный)
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            reason: Причина требования одобрения
            
        Returns:
            Созданный HITLPendingState
            
        Пример:
            >>> pending = await repository.save_pending(
            ...     session_id="session-123",
            ...     call_id="call-456",
            ...     tool_name="write_file",
            ...     arguments={"path": "test.py", "content": "..."},
            ...     reason="Dangerous operation"
            ... )
        """
        pass
    
    @abstractmethod
    async def delete_by_call_id(self, call_id: str) -> bool:
        """
        Удалить pending approval по call_id.
        
        Args:
            call_id: ID tool call
            
        Returns:
            True если удален, False если не найден
            
        Пример:
            >>> deleted = await repository.delete_by_call_id("call-456")
            >>> if deleted:
            ...     print("Pending approval removed")
        """
        pass
    
    @abstractmethod
    async def cleanup_expired(
        self,
        session_id: str,
        timeout_seconds: int = 300
    ) -> int:
        """
        Очистить expired pending approvals для сессии.
        
        Args:
            session_id: ID сессии
            timeout_seconds: Timeout в секундах
            
        Returns:
            Количество удаленных pending approvals
            
        Пример:
            >>> count = await repository.cleanup_expired(
            ...     "session-123",
            ...     timeout_seconds=300
            ... )
            >>> print(f"Cleaned up {count} expired approvals")
        """
        pass
    
    @abstractmethod
    async def save_audit_log(self, audit_log: HITLAuditLog) -> None:
        """
        Сохранить audit log entry.
        
        Note: Опционально - audit logs могут отслеживаться через events.
        Реализация может быть no-op если используется event-driven audit.
        
        Args:
            audit_log: Audit log entry для сохранения
            
        Пример:
            >>> from ..entities.hitl import HITLDecision
            >>> audit = HITLAuditLog(
            ...     session_id="session-123",
            ...     call_id="call-456",
            ...     tool_name="write_file",
            ...     original_arguments={"path": "test.py"},
            ...     decision=HITLDecision.APPROVE
            ... )
            >>> await repository.save_audit_log(audit)
        """
        pass

"""
HITL Service для управления Human-in-the-Loop workflow (Domain Layer).

Координирует работу с HITL состоянием через Repository pattern.
Не имеет прямых зависимостей от Infrastructure.
"""
import logging
from typing import Dict, List, Optional, Callable, Awaitable

from ..entities.hitl import (
    HITLPendingState,
    HITLUserDecision,
    HITLDecision,
    HITLAuditLog
)
from ..repositories.hitl_repository import HITLRepository
from ...events.event_bus import event_bus
from ...events.tool_events import (
    HITLApprovalRequestedEvent,
    HITLDecisionMadeEvent
)

logger = logging.getLogger("agent-runtime.domain.hitl_service")


class HITLService:
    """
    Domain service для управления HITL workflow.
    
    Следует принципам Clean Architecture:
    - Stateless (без внутреннего состояния)
    - Dependency Injection (все зависимости через конструктор)
    - Зависит только от абстракций (HITLRepository interface)
    - Не знает о деталях Infrastructure
    
    Атрибуты:
        _repository: Repository для работы с HITL данными
        _event_publisher: Функция для публикации событий (опционально)
    
    Пример:
        >>> repository = HITLRepositoryImpl(db, db_service)
        >>> service = HITLService(repository=repository)
        >>> pending = await service.add_pending(
        ...     session_id="session-123",
        ...     call_id="call-456",
        ...     tool_name="write_file",
        ...     arguments={"path": "test.py"},
        ...     reason="Dangerous operation"
        ... )
    """
    
    def __init__(
        self,
        repository: HITLRepository,
        event_publisher: Optional[Callable[[object], Awaitable[None]]] = None
    ):
        """
        Инициализация HITL service с зависимостями.
        
        Args:
            repository: HITL repository (инжектируется)
            event_publisher: Опциональная функция для публикации событий (инжектируется)
        """
        self._repository = repository
        self._event_publisher = event_publisher
    
    async def add_pending(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: Dict,
        reason: Optional[str] = None,
        timeout_seconds: int = 300
    ) -> HITLPendingState:
        """
        Добавить tool call в pending HITL approval.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            reason: Причина требования одобрения
            timeout_seconds: Timeout для решения пользователя
            
        Returns:
            Созданный HITLPendingState
            
        Пример:
            >>> pending = await service.add_pending(
            ...     session_id="session-123",
            ...     call_id="call-456",
            ...     tool_name="write_file",
            ...     arguments={"path": "test.py", "content": "..."},
            ...     reason="File modification requires approval"
            ... )
        """
        # Сохранить через repository
        pending_state = await self._repository.save_pending(
            session_id=session_id,
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason
        )
        
        logger.info(
            f"Added pending HITL approval: session={session_id}, "
            f"call_id={call_id}, tool={tool_name}"
        )
        
        # Опубликовать событие
        await event_bus.publish(
            HITLApprovalRequestedEvent(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
                reason=reason or "",
                timeout_seconds=timeout_seconds
            )
        )
        
        return pending_state
    
    async def get_pending(
        self,
        session_id: str,
        call_id: str
    ) -> Optional[HITLPendingState]:
        """
        Получить pending HITL state для tool call.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call
            
        Returns:
            HITLPendingState если найден, None иначе
            
        Пример:
            >>> pending = await service.get_pending("session-123", "call-456")
            >>> if pending:
            ...     print(f"Tool: {pending.tool_name}, Reason: {pending.reason}")
        """
        return await self._repository.find_by_call_id(session_id, call_id)
    
    async def get_all_pending(
        self,
        session_id: str
    ) -> List[HITLPendingState]:
        """
        Получить все pending HITL states для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список HITLPendingState объектов
            
        Пример:
            >>> pending_list = await service.get_all_pending("session-123")
            >>> for pending in pending_list:
            ...     print(f"Pending: {pending.tool_name} ({pending.call_id})")
        """
        return await self._repository.find_by_session_id(session_id)
    
    async def remove_pending(
        self,
        session_id: str,
        call_id: str
    ) -> bool:
        """
        Удалить pending HITL state.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call
            
        Returns:
            True если удален, False если не найден
            
        Пример:
            >>> removed = await service.remove_pending("session-123", "call-456")
            >>> if removed:
            ...     print("Pending approval removed")
        """
        removed = await self._repository.delete_by_call_id(call_id)
        
        if removed:
            logger.info(f"Removed pending HITL state: call_id={call_id}")
        
        return removed
    
    async def cleanup_expired(
        self,
        session_id: str
    ) -> int:
        """
        Очистить expired pending HITL states.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Количество удаленных expired states
            
        Пример:
            >>> count = await service.cleanup_expired("session-123")
            >>> print(f"Cleaned up {count} expired approvals")
        """
        expired_count = await self._repository.cleanup_expired(
            session_id=session_id,
            timeout_seconds=300
        )
        
        if expired_count > 0:
            logger.info(
                f"Cleaned up {expired_count} expired HITL states "
                f"for session {session_id}"
            )
        
        return expired_count
    
    async def log_decision(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        original_arguments: Dict,
        decision: HITLDecision,
        modified_arguments: Optional[Dict] = None,
        feedback: Optional[str] = None
    ) -> HITLAuditLog:
        """
        Залогировать решение пользователя в audit log.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call
            tool_name: Имя инструмента
            original_arguments: Оригинальные аргументы инструмента
            decision: Решение пользователя
            modified_arguments: Модифицированные аргументы (для EDIT)
            feedback: Feedback пользователя (для REJECT)
            
        Returns:
            Созданный HITLAuditLog
            
        Пример:
            >>> audit = await service.log_decision(
            ...     session_id="session-123",
            ...     call_id="call-456",
            ...     tool_name="write_file",
            ...     original_arguments={"path": "test.py"},
            ...     decision=HITLDecision.APPROVE
            ... )
        """
        # Создать audit log entry
        audit_log = HITLAuditLog(
            session_id=session_id,
            call_id=call_id,
            tool_name=tool_name,
            original_arguments=original_arguments,
            decision=decision,
            modified_arguments=modified_arguments,
            feedback=feedback
        )
        
        logger.info(
            f"Logged HITL decision: session={session_id}, call_id={call_id}, "
            f"decision={decision.value}, tool={tool_name}"
        )
        
        # Опубликовать событие
        await event_bus.publish(
            HITLDecisionMadeEvent(
                session_id=session_id,
                call_id=call_id,
                decision=decision.value,
                tool_name=tool_name,
                original_args=original_arguments,
                modified_args=modified_arguments
            )
        )
        
        return audit_log

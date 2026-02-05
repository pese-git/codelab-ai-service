"""
ApprovalService Domain Service.

Сервис для управления жизненным циклом утверждений.
"""

import logging
from typing import Any, Dict, List, Optional

from ..entities.approval_request import ApprovalRequest
from ..repositories.approval_repository import ApprovalRepository
from ..value_objects.approval_id import ApprovalId
from ..value_objects.approval_type import ApprovalType
from ..value_objects.approval_status import ApprovalStatus, ApprovalStatusEnum
from ..events.approval_events import UserDecisionRequired

logger = logging.getLogger("agent-runtime.domain.approval_service")


class ApprovalService:
    """
    Domain Service для управления утверждениями.
    
    Responsibilities:
    - Создание запросов на утверждение
    - Обработка решений пользователя (approve/reject)
    - Управление жизненным циклом утверждений
    - Обработка истекших запросов
    - Генерация Domain Events
    
    Примеры:
        >>> service = ApprovalService(repository)
        >>> 
        >>> # Создание запроса
        >>> request = await service.request_approval(
        ...     approval_id=ApprovalId("req-tool-123"),
        ...     approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
        ...     session_id="session-abc",
        ...     subject="write_file",
        ...     request_data={"path": "test.py"},
        ...     reason="File modification requires approval"
        ... )
        >>> 
        >>> # Одобрение
        >>> await service.grant_approval(
        ...     approval_id=ApprovalId("req-tool-123"),
        ...     decision="User confirmed"
        ... )
    """
    
    def __init__(self, repository: ApprovalRepository):
        """
        Создать ApprovalService.
        
        Args:
            repository: Репозиторий для работы с утверждениями
        """
        self._repository = repository
        logger.info("ApprovalService initialized")
    
    async def request_approval(
        self,
        approval_id: ApprovalId,
        approval_type: ApprovalType,
        session_id: str,
        subject: str,
        request_data: Dict[str, Any],
        reason: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> ApprovalRequest:
        """
        Создать запрос на утверждение.
        
        Args:
            approval_id: Уникальный ID запроса
            approval_type: Тип утверждения
            session_id: ID сессии
            subject: Предмет утверждения
            request_data: Данные запроса
            reason: Причина требования утверждения
            timeout_seconds: Таймаут ожидания решения
            
        Returns:
            Созданный ApprovalRequest
            
        Raises:
            ValueError: Если запрос с таким ID уже существует
        """
        # Проверка существования
        existing = await self._repository.find_by_id(approval_id)
        if existing:
            raise ValueError(f"Approval request {approval_id} already exists")
        
        # Создание запроса
        request = ApprovalRequest.create(
            approval_id=approval_id,
            approval_type=approval_type,
            session_id=session_id,
            subject=subject,
            request_data=request_data,
            reason=reason,
            timeout_seconds=timeout_seconds,
        )
        
        # Генерация события о необходимости решения пользователя
        request.add_domain_event(
            UserDecisionRequired(
                approval_id=approval_id,
                reason=reason or "Approval required",
            )
        )
        
        # Сохранение
        await self._repository.save(request)
        
        logger.info(
            f"Approval requested: id={approval_id}, "
            f"type={approval_type}, subject='{subject}'"
        )
        
        return request
    
    async def grant_approval(
        self,
        approval_id: ApprovalId,
        decision: str,
    ) -> None:
        """
        Одобрить запрос на утверждение.
        
        Args:
            approval_id: ID запроса
            decision: Решение пользователя
            
        Raises:
            ValueError: Если запрос не найден или переход невозможен
        """
        # Получение запроса
        request = await self._repository.find_by_id(approval_id)
        if not request:
            raise ValueError(f"Approval request {approval_id} not found")
        
        # Одобрение (генерирует ApprovalGranted event)
        request.approve(decision)
        
        # Сохранение
        await self._repository.save(request)
        
        logger.info(f"Approval granted: id={approval_id}")
    
    async def reject_approval(
        self,
        approval_id: ApprovalId,
        reason: str,
    ) -> None:
        """
        Отклонить запрос на утверждение.
        
        Args:
            approval_id: ID запроса
            reason: Причина отклонения
            
        Raises:
            ValueError: Если запрос не найден или переход невозможен
        """
        # Получение запроса
        request = await self._repository.find_by_id(approval_id)
        if not request:
            raise ValueError(f"Approval request {approval_id} not found")
        
        # Отклонение (генерирует ApprovalRejected event)
        request.reject(reason)
        
        # Сохранение
        await self._repository.save(request)
        
        logger.info(f"Approval rejected: id={approval_id}, reason='{reason}'")
    
    async def get_pending_approvals(
        self,
        session_id: str,
    ) -> List[ApprovalRequest]:
        """
        Получить все ожидающие утверждения для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список ApprovalRequest со статусом PENDING
        """
        return await self._repository.find_pending_by_session(session_id)
    
    async def get_approval(
        self,
        approval_id: ApprovalId,
    ) -> Optional[ApprovalRequest]:
        """
        Получить запрос на утверждение по ID.
        
        Args:
            approval_id: ID запроса
            
        Returns:
            ApprovalRequest если найден, None иначе
        """
        return await self._repository.find_by_id(approval_id)
    
    async def process_expired_approvals(
        self,
        session_id: Optional[str] = None,
    ) -> int:
        """
        Обработать истекшие запросы на утверждение.
        
        Находит все запросы, превысившие timeout, и помечает их как EXPIRED.
        
        Args:
            session_id: Опциональный фильтр по сессии
            
        Returns:
            Количество обработанных истекших запросов
        """
        expired_requests = await self._repository.find_expired(session_id)
        
        count = 0
        for request in expired_requests:
            try:
                # Пометка как истекший (генерирует ApprovalExpired event)
                request.expire()
                await self._repository.save(request)
                count += 1
                
                logger.info(f"Approval expired: id={request.approval_id}")
            
            except Exception as e:
                logger.error(
                    f"Failed to expire approval {request.approval_id}: {e}",
                    exc_info=True,
                )
        
        if count > 0:
            logger.info(f"Processed {count} expired approvals")
        
        return count
    
    async def count_pending(self, session_id: str) -> int:
        """
        Подсчитать количество ожидающих утверждений для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Количество запросов со статусом PENDING
        """
        return await self._repository.count_pending(session_id)
    
    async def has_pending_approvals(self, session_id: str) -> bool:
        """
        Проверить, есть ли ожидающие утверждения для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если есть хотя бы один запрос со статусом PENDING
        """
        count = await self.count_pending(session_id)
        return count > 0

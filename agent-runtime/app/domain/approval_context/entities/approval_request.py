"""
ApprovalRequest Entity.

Запрос на утверждение с типобезопасными Value Objects.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import Field

from app.domain.shared.base_entity import Entity
from ..value_objects.approval_id import ApprovalId
from ..value_objects.approval_type import ApprovalType
from ..value_objects.approval_status import ApprovalStatus, ApprovalStatusEnum
from ..events.approval_events import (
    ApprovalRequested,
    ApprovalGranted,
    ApprovalRejected,
    ApprovalExpired,
)


class ApprovalRequest(Entity):
    """
    Запрос на утверждение.
    
    Aggregate Root для управления жизненным циклом утверждения.
    
    Обеспечивает:
    - Типобезопасность через Value Objects
    - Валидацию переходов состояний
    - Генерацию Domain Events
    - Инкапсуляцию бизнес-правил
    
    Attributes:
        id: Уникальный идентификатор (ApprovalId)
        approval_type: Тип утверждения
        status: Текущий статус
        session_id: ID сессии
        subject: Предмет утверждения (имя инструмента, название плана)
        request_data: Данные запроса (гибкий формат)
        reason: Причина, почему требуется утверждение
        decision: Решение пользователя (для approved/rejected)
        decided_at: Время принятия решения
        timeout_seconds: Таймаут ожидания решения
    
    Примеры:
        >>> # Создание запроса
        >>> request = ApprovalRequest.create(
        ...     approval_id=ApprovalId(value="req-tool-123"),
        ...     approval_type=ApprovalType(value=ApprovalTypeEnum.TOOL_CALL),
        ...     session_id="session-abc",
        ...     subject="write_file",
        ...     request_data={"path": "test.py", "content": "..."},
        ...     reason="File modification requires approval"
        ... )
        >>> 
        >>> # Одобрение
        >>> request.approve("User confirmed")
        >>> request.status.is_approved()
        True
    """
    
    id: ApprovalId = Field(..., description="Уникальный идентификатор")
    approval_type: ApprovalType = Field(..., description="Тип утверждения")
    status: ApprovalStatus = Field(..., description="Статус утверждения")
    session_id: str = Field(..., description="ID сессии")
    subject: str = Field(..., description="Предмет утверждения")
    request_data: Dict[str, Any] = Field(..., description="Данные запроса")
    reason: Optional[str] = Field(None, description="Причина требования утверждения")
    decision: Optional[str] = Field(None, description="Решение пользователя")
    decided_at: Optional[datetime] = Field(None, description="Время решения")
    timeout_seconds: int = Field(300, description="Таймаут ожидания")
    
    @classmethod
    def create(
        cls,
        approval_id: ApprovalId,
        approval_type: ApprovalType,
        session_id: str,
        subject: str,
        request_data: Dict[str, Any],
        reason: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> "ApprovalRequest":
        """
        Создать новый запрос на утверждение.
        
        Factory method для создания запроса в начальном состоянии PENDING.
        
        Args:
            approval_id: Уникальный идентификатор
            approval_type: Тип утверждения
            session_id: ID сессии
            subject: Предмет утверждения
            request_data: Данные запроса
            reason: Причина требования утверждения
            timeout_seconds: Таймаут ожидания
            
        Returns:
            Новый ApprovalRequest в статусе PENDING
        """
        request = cls(
            id=approval_id,
            approval_type=approval_type,
            status=ApprovalStatus(value=ApprovalStatusEnum.PENDING),
            session_id=session_id,
            subject=subject,
            request_data=request_data,
            reason=reason,
            timeout_seconds=timeout_seconds,
        )
        
        # Генерация события
        request.add_domain_event(
            ApprovalRequested(
                approval_id=approval_id,
                approval_type=approval_type,
                session_id=session_id,
                subject=subject,
                reason=reason,
            )
        )
        
        return request
    
    @property
    def approval_id(self) -> ApprovalId:
        """Получить ID утверждения."""
        return self.id
    
    def approve(self, decision: str) -> None:
        """
        Одобрить запрос.
        
        Args:
            decision: Решение пользователя
            
        Raises:
            ValueError: Если переход в APPROVED невозможен
        """
        target_status = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        
        if not self.status.can_transition_to(target_status):
            raise ValueError(
                f"Cannot approve: invalid transition from {self.status} to {target_status}"
            )
        
        self.status = target_status
        self.decision = decision
        self.decided_at = datetime.now(timezone.utc)
        self.mark_updated()
        
        # Генерация события
        self.add_domain_event(
            ApprovalGranted(
                approval_id=self.id,
                decision=decision,
                approved_at=self.decided_at,
            )
        )
    
    def reject(self, reason: str) -> None:
        """
        Отклонить запрос.
        
        Args:
            reason: Причина отклонения
            
        Raises:
            ValueError: Если переход в REJECTED невозможен
        """
        target_status = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        
        if not self.status.can_transition_to(target_status):
            raise ValueError(
                f"Cannot reject: invalid transition from {self.status} to {target_status}"
            )
        
        self.status = target_status
        self.decision = reason
        self.decided_at = datetime.now(timezone.utc)
        self.mark_updated()
        
        # Генерация события
        self.add_domain_event(
            ApprovalRejected(
                approval_id=self.id,
                reason=reason,
                rejected_at=self.decided_at,
            )
        )
    
    def expire(self) -> None:
        """
        Пометить запрос как истекший.
        
        Вызывается когда истекает таймаут ожидания решения.
        
        Raises:
            ValueError: Если переход в EXPIRED невозможен
        """
        target_status = ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        
        if not self.status.can_transition_to(target_status):
            raise ValueError(
                f"Cannot expire: invalid transition from {self.status} to {target_status}"
            )
        
        self.status = target_status
        self.decided_at = datetime.now(timezone.utc)
        self.mark_updated()
        
        # Генерация события
        self.add_domain_event(
            ApprovalExpired(
                approval_id=self.id,
                expired_at=self.decided_at,
            )
        )
    
    def is_expired(self) -> bool:
        """
        Проверить, истек ли таймаут ожидания.
        
        Returns:
            True если прошло больше timeout_seconds с момента создания
        """
        if not self.status.is_pending():
            return False
        
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.timeout_seconds
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return (
            f"ApprovalRequest(id={self.id}, "
            f"type={self.approval_type}, "
            f"status={self.status}, "
            f"subject='{self.subject}')"
        )

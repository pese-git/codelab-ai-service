"""
Domain Events для Approval Context.

События жизненного цикла утверждений и политик HITL.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from app.domain.shared.domain_event import DomainEvent
from ..value_objects.approval_id import ApprovalId
from ..value_objects.approval_type import ApprovalType
from ..value_objects.policy_action import PolicyAction


class ApprovalRequested(DomainEvent):
    """
    Событие: Запрошено утверждение.
    
    Публикуется когда создается новый запрос на утверждение.
    
    Attributes:
        approval_id: ID запроса на утверждение
        approval_type: Тип утверждения
        session_id: ID сессии
        subject: Предмет утверждения (имя инструмента, название плана)
        reason: Причина, почему требуется утверждение
        requested_at: Время создания запроса
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        approval_type: ApprovalType,
        session_id: str,
        subject: str,
        reason: Optional[str] = None,
        requested_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._approval_type = approval_type
        self._session_id = session_id
        self._subject = subject
        self._reason = reason
        self._requested_at = requested_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def approval_type(self) -> ApprovalType:
        return self._approval_type
    
    @property
    def session_id(self) -> str:
        return self._session_id
    
    @property
    def subject(self) -> str:
        return self._subject
    
    @property
    def reason(self) -> Optional[str]:
        return self._reason
    
    @property
    def requested_at(self) -> datetime:
        return self._requested_at


class ApprovalGranted(DomainEvent):
    """
    Событие: Утверждение одобрено.
    
    Публикуется когда пользователь одобряет запрос.
    
    Attributes:
        approval_id: ID запроса на утверждение
        decision: Решение пользователя
        approved_at: Время одобрения
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        decision: str,
        approved_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._decision = decision
        self._approved_at = approved_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def decision(self) -> str:
        return self._decision
    
    @property
    def approved_at(self) -> datetime:
        return self._approved_at


class ApprovalRejected(DomainEvent):
    """
    Событие: Утверждение отклонено.
    
    Публикуется когда пользователь отклоняет запрос.
    
    Attributes:
        approval_id: ID запроса на утверждение
        reason: Причина отклонения
        rejected_at: Время отклонения
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        reason: str,
        rejected_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._reason = reason
        self._rejected_at = rejected_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def reason(self) -> str:
        return self._reason
    
    @property
    def rejected_at(self) -> datetime:
        return self._rejected_at


class ApprovalExpired(DomainEvent):
    """
    Событие: Утверждение истекло.
    
    Публикуется когда истекает таймаут ожидания решения пользователя.
    
    Attributes:
        approval_id: ID запроса на утверждение
        expired_at: Время истечения
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        expired_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._expired_at = expired_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def expired_at(self) -> datetime:
        return self._expired_at


class PolicyEvaluated(DomainEvent):
    """
    Событие: Политика оценена.
    
    Публикуется когда политика HITL оценивает запрос.
    
    Attributes:
        approval_id: ID запроса на утверждение
        policy_id: ID политики
        action: Действие, определенное политикой
        evaluated_at: Время оценки
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        policy_id: str,
        action: PolicyAction,
        evaluated_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._policy_id = policy_id
        self._action = action
        self._evaluated_at = evaluated_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def policy_id(self) -> str:
        return self._policy_id
    
    @property
    def action(self) -> PolicyAction:
        return self._action
    
    @property
    def evaluated_at(self) -> datetime:
        return self._evaluated_at


class PolicyRuleMatched(DomainEvent):
    """
    Событие: Правило политики сработало.
    
    Публикуется когда правило политики соответствует запросу.
    
    Attributes:
        approval_id: ID запроса на утверждение
        rule_condition: Условие правила, которое сработало
        action: Действие, определенное правилом
        matched_at: Время срабатывания
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        rule_condition: str,
        action: PolicyAction,
        matched_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._rule_condition = rule_condition
        self._action = action
        self._matched_at = matched_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def rule_condition(self) -> str:
        return self._rule_condition
    
    @property
    def action(self) -> PolicyAction:
        return self._action
    
    @property
    def matched_at(self) -> datetime:
        return self._matched_at


class AutoApprovalGranted(DomainEvent):
    """
    Событие: Автоматическое утверждение одобрено.
    
    Публикуется когда политика автоматически одобряет запрос.
    
    Attributes:
        approval_id: ID запроса на утверждение
        policy_id: ID политики, которая одобрила
        auto_approved_at: Время автоматического одобрения
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        policy_id: str,
        auto_approved_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._policy_id = policy_id
        self._auto_approved_at = auto_approved_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def policy_id(self) -> str:
        return self._policy_id
    
    @property
    def auto_approved_at(self) -> datetime:
        return self._auto_approved_at


class UserDecisionRequired(DomainEvent):
    """
    Событие: Требуется решение пользователя.
    
    Публикуется когда политика определяет, что нужно запросить пользователя.
    
    Attributes:
        approval_id: ID запроса на утверждение
        reason: Причина, почему требуется решение пользователя
        requested_at: Время запроса
    """
    
    def __init__(
        self,
        approval_id: ApprovalId,
        reason: str,
        requested_at: Optional[datetime] = None,
    ):
        super().__init__()
        self._approval_id = approval_id
        self._reason = reason
        self._requested_at = requested_at or datetime.utcnow()
    
    @property
    def approval_id(self) -> ApprovalId:
        return self._approval_id
    
    @property
    def reason(self) -> str:
        return self._reason
    
    @property
    def requested_at(self) -> datetime:
        return self._requested_at

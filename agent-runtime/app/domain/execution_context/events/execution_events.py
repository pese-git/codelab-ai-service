"""
Domain Events для Execution Context.

События, связанные с выполнением планов и подзадач.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import Field

from app.domain.shared.domain_event import DomainEvent
from app.domain.execution_context.value_objects import PlanId, SubtaskId


class PlanCreated(DomainEvent):
    """
    Событие: План создан.
    
    Публикуется когда создается новый план выполнения.
    
    Attributes:
        plan_id: ID созданного плана
        conversation_id: ID диалога
        goal: Цель плана
        subtask_count: Количество подзадач
    """
    
    plan_id: PlanId = Field(..., description="ID созданного плана")
    conversation_id: str = Field(..., description="ID диалога")
    goal: str = Field(..., description="Цель плана")
    subtask_count: int = Field(..., description="Количество подзадач")
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "plan_created"


class PlanApproved(DomainEvent):
    """
    Событие: План утвержден.
    
    Публикуется когда план утверждается пользователем.
    
    Attributes:
        plan_id: ID утвержденного плана
        conversation_id: ID диалога
        approved_at: Время утверждения
    """
    
    plan_id: PlanId = Field(..., description="ID утвержденного плана")
    conversation_id: str = Field(..., description="ID диалога")
    approved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время утверждения"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "plan_approved"


class PlanExecutionStarted(DomainEvent):
    """
    Событие: Начато выполнение плана.
    
    Публикуется когда план переходит в статус IN_PROGRESS.
    
    Attributes:
        plan_id: ID плана
        conversation_id: ID диалога
        started_at: Время начала
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    conversation_id: str = Field(..., description="ID диалога")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время начала"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "plan_execution_started"


class PlanCompleted(DomainEvent):
    """
    Событие: План успешно завершен.
    
    Публикуется когда все подзадачи плана выполнены.
    
    Attributes:
        plan_id: ID плана
        conversation_id: ID диалога
        completed_at: Время завершения
        duration_seconds: Длительность выполнения в секундах
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    conversation_id: str = Field(..., description="ID диалога")
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время завершения"
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Длительность выполнения в секундах"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "plan_completed"


class PlanFailed(DomainEvent):
    """
    Событие: План завершен с ошибкой.
    
    Публикуется когда план не может быть выполнен.
    
    Attributes:
        plan_id: ID плана
        conversation_id: ID диалога
        reason: Причина ошибки
        failed_at: Время ошибки
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    conversation_id: str = Field(..., description="ID диалога")
    reason: str = Field(..., description="Причина ошибки")
    failed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время ошибки"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "plan_failed"


class PlanCancelled(DomainEvent):
    """
    Событие: План отменен.
    
    Публикуется когда план отменяется пользователем.
    
    Attributes:
        plan_id: ID плана
        conversation_id: ID диалога
        reason: Причина отмены
        cancelled_at: Время отмены
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    conversation_id: str = Field(..., description="ID диалога")
    reason: str = Field(..., description="Причина отмены")
    cancelled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время отмены"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "plan_cancelled"


class SubtaskStarted(DomainEvent):
    """
    Событие: Начато выполнение подзадачи.
    
    Публикуется когда подзадача переходит в статус RUNNING.
    
    Attributes:
        plan_id: ID плана
        subtask_id: ID подзадачи
        conversation_id: ID диалога
        agent_id: ID агента, выполняющего подзадачу
        started_at: Время начала
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    subtask_id: SubtaskId = Field(..., description="ID подзадачи")
    conversation_id: str = Field(..., description="ID диалога")
    agent_id: str = Field(..., description="ID агента")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время начала"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "subtask_started"


class SubtaskCompleted(DomainEvent):
    """
    Событие: Подзадача успешно завершена.
    
    Публикуется когда подзадача переходит в статус DONE.
    
    Attributes:
        plan_id: ID плана
        subtask_id: ID подзадачи
        conversation_id: ID диалога
        agent_id: ID агента
        result: Результат выполнения
        completed_at: Время завершения
        duration_seconds: Длительность выполнения в секундах
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    subtask_id: SubtaskId = Field(..., description="ID подзадачи")
    conversation_id: str = Field(..., description="ID диалога")
    agent_id: str = Field(..., description="ID агента")
    result: str = Field(..., description="Результат выполнения")
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время завершения"
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Длительность выполнения в секундах"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "subtask_completed"


class SubtaskFailed(DomainEvent):
    """
    Событие: Подзадача завершена с ошибкой.
    
    Публикуется когда подзадача переходит в статус FAILED.
    
    Attributes:
        plan_id: ID плана
        subtask_id: ID подзадачи
        conversation_id: ID диалога
        agent_id: ID агента
        error: Описание ошибки
        failed_at: Время ошибки
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    subtask_id: SubtaskId = Field(..., description="ID подзадачи")
    conversation_id: str = Field(..., description="ID диалога")
    agent_id: str = Field(..., description="ID агента")
    error: str = Field(..., description="Описание ошибки")
    failed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время ошибки"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "subtask_failed"


class SubtaskRetried(DomainEvent):
    """
    Событие: Подзадача повторно запущена после ошибки.
    
    Публикуется когда подзадача переходит из FAILED обратно в PENDING для retry.
    
    Attributes:
        plan_id: ID плана
        subtask_id: ID подзадачи
        retry_count: Номер попытки
        retried_at: Время повторного запуска
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    subtask_id: SubtaskId = Field(..., description="ID подзадачи")
    retry_count: int = Field(..., description="Номер попытки")
    retried_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время повторного запуска"
    )
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "subtask_retried"


class SubtaskBlocked(DomainEvent):
    """
    Событие: Подзадача заблокирована.
    
    Публикуется когда подзадача не может быть выполнена из-за невыполненных зависимостей.
    
    Attributes:
        plan_id: ID плана
        subtask_id: ID подзадачи
        conversation_id: ID диалога
        blocked_by: Список ID подзадач-зависимостей
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    subtask_id: SubtaskId = Field(..., description="ID подзадачи")
    conversation_id: str = Field(..., description="ID диалога")
    blocked_by: list[SubtaskId] = Field(..., description="Список ID подзадач-зависимостей")
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "subtask_blocked"


class SubtaskUnblocked(DomainEvent):
    """
    Событие: Подзадача разблокирована.
    
    Публикуется когда все зависимости подзадачи выполнены.
    
    Attributes:
        plan_id: ID плана
        subtask_id: ID подзадачи
        conversation_id: ID диалога
    """
    
    plan_id: PlanId = Field(..., description="ID плана")
    subtask_id: SubtaskId = Field(..., description="ID подзадачи")
    conversation_id: str = Field(..., description="ID диалога")
    
    @property
    def event_type(self) -> str:
        """Тип события."""
        return "subtask_unblocked"

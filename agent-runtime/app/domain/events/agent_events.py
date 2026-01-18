"""
Доменные события для агентов.

События описывают важные бизнес-события, связанные с работой агентов.
"""

from typing import Optional
from .base import DomainEvent


class AgentAssigned(DomainEvent):
    """
    Событие: агент назначен на задачу.
    
    Публикуется когда агент начинает работу с сессией.
    
    Атрибуты:
        session_id: ID сессии
        agent_type: Тип назначенного агента
        reason: Причина назначения
        confidence: Уверенность в выборе агента (для LLM-based routing)
    
    Пример:
        >>> event = AgentAssigned(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     agent_type="coder",
        ...     reason="Coding task detected",
        ...     confidence="high"
        ... )
    """
    
    session_id: str
    agent_type: str
    reason: str
    confidence: Optional[str] = None


class AgentSwitchRequested(DomainEvent):
    """
    Событие: запрошено переключение агента.
    
    Публикуется когда система или пользователь запрашивает
    переключение на другого агента.
    
    Атрибуты:
        session_id: ID сессии
        from_agent: Текущий агент
        to_agent: Целевой агент
        reason: Причина переключения
        requested_by: Кто запросил (user, system, agent)
    
    Пример:
        >>> event = AgentSwitchRequested(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     from_agent="orchestrator",
        ...     to_agent="coder",
        ...     reason="User requested code changes",
        ...     requested_by="user"
        ... )
    """
    
    session_id: str
    from_agent: str
    to_agent: str
    reason: str
    requested_by: str = "system"


class AgentSwitched(DomainEvent):
    """
    Событие: агент переключен.
    
    Публикуется когда переключение агента успешно выполнено.
    
    Атрибуты:
        session_id: ID сессии
        from_agent: Предыдущий агент
        to_agent: Новый агент
        reason: Причина переключения
        switch_count: Общее количество переключений в сессии
    
    Пример:
        >>> event = AgentSwitched(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     from_agent="orchestrator",
        ...     to_agent="coder",
        ...     reason="Coding task detected",
        ...     switch_count=1
        ... )
    """
    
    session_id: str
    from_agent: str
    to_agent: str
    reason: str
    switch_count: int


class TaskStarted(DomainEvent):
    """
    Событие: задача начата.
    
    Публикуется когда агент начинает обработку задачи.
    
    Атрибуты:
        session_id: ID сессии
        agent_type: Тип агента, обрабатывающего задачу
        task_description: Описание задачи
    
    Пример:
        >>> event = TaskStarted(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     agent_type="coder",
        ...     task_description="Create new Flutter widget"
        ... )
    """
    
    session_id: str
    agent_type: str
    task_description: str


class TaskCompleted(DomainEvent):
    """
    Событие: задача выполнена.
    
    Публикуется когда агент успешно завершает обработку задачи.
    
    Атрибуты:
        session_id: ID сессии
        agent_type: Тип агента, выполнившего задачу
        success: Успешность выполнения
        result_summary: Краткое описание результата
        duration_seconds: Длительность выполнения в секундах
    
    Пример:
        >>> event = TaskCompleted(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     agent_type="coder",
        ...     success=True,
        ...     result_summary="Created user_profile.dart widget",
        ...     duration_seconds=15.3
        ... )
    """
    
    session_id: str
    agent_type: str
    success: bool
    result_summary: str
    duration_seconds: float


class TaskFailed(DomainEvent):
    """
    Событие: задача не выполнена.
    
    Публикуется когда агент не смог выполнить задачу.
    
    Атрибуты:
        session_id: ID сессии
        agent_type: Тип агента
        error_message: Сообщение об ошибке
        error_type: Тип ошибки
    
    Пример:
        >>> event = TaskFailed(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     agent_type="coder",
        ...     error_message="File not found",
        ...     error_type="FileNotFoundError"
        ... )
    """
    
    session_id: str
    agent_type: str
    error_message: str
    error_type: str

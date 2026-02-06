"""
Domain Events для Agent Context.

События, которые происходят в жизненном цикле агента.
"""

from datetime import datetime, timezone
from typing import Optional, Any

from ...shared.domain_event import DomainEvent
from ..value_objects.agent_id import AgentId
from ..value_objects.agent_capabilities import AgentType


class AgentCreated(DomainEvent):
    """
    Событие: Агент создан.
    
    Публикуется когда создается новый агент для сессии.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        agent_type: Тип агента
    """
    
    agent_id: AgentId
    session_id: str
    agent_type: AgentType


class AgentSwitched(DomainEvent):
    """
    Событие: Агент переключен на другой тип.
    
    Публикуется когда агент меняет свой тип.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        from_type: Предыдущий тип агента
        to_type: Новый тип агента
        reason: Причина переключения
        confidence: Уверенность в переключении
    """
    
    agent_id: AgentId
    session_id: str
    from_type: AgentType
    to_type: AgentType
    reason: str
    confidence: Optional[str] = None


class AgentResetToOrchestrator(DomainEvent):
    """
    Событие: Агент сброшен к Orchestrator.
    
    Публикуется когда агент возвращается к Orchestrator типу.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        previous_type: Предыдущий тип агента
        reason: Причина сброса
    """
    
    agent_id: AgentId
    session_id: str
    previous_type: AgentType
    reason: str


class AgentMetadataUpdated(DomainEvent):
    """
    Событие: Метаданные агента обновлены.
    
    Публикуется когда изменяются метаданные агента.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        key: Ключ метаданных
        value: Новое значение
    """
    
    agent_id: AgentId
    session_id: str
    key: str
    value: Any


class AgentSwitchLimitReached(DomainEvent):
    """
    Событие: Достигнут лимит переключений агента.
    
    Публикуется когда агент достигает максимального количества переключений.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        switch_count: Текущее количество переключений
        max_switches: Максимальное количество переключений
    """
    
    agent_id: AgentId
    session_id: str
    switch_count: int
    max_switches: int

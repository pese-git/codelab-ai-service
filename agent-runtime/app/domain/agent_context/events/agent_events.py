"""
Domain Events для Agent Context.

События, которые происходят в жизненном цикле агента.
"""

from datetime import datetime, timezone
from typing import Optional

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
        timestamp: Время создания
    """
    
    def __init__(
        self,
        agent_id: AgentId,
        session_id: str,
        agent_type: AgentType,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Создать событие AgentCreated.
        
        Args:
            agent_id: ID агента
            session_id: ID сессии
            agent_type: Тип агента
            timestamp: Время события
        """
        super().__init__(
            event_type="agent.created",
            timestamp=timestamp or datetime.now(timezone.utc)
        )
        self.agent_id = agent_id
        self.session_id = session_id
        self.agent_type = agent_type
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id.value,
            "session_id": self.session_id,
            "agent_type": self.agent_type.value
        }


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
        timestamp: Время переключения
    """
    
    def __init__(
        self,
        agent_id: AgentId,
        session_id: str,
        from_type: AgentType,
        to_type: AgentType,
        reason: str,
        confidence: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Создать событие AgentSwitched.
        
        Args:
            agent_id: ID агента
            session_id: ID сессии
            from_type: Предыдущий тип
            to_type: Новый тип
            reason: Причина переключения
            confidence: Уверенность
            timestamp: Время события
        """
        super().__init__(
            event_type="agent.switched",
            timestamp=timestamp or datetime.now(timezone.utc)
        )
        self.agent_id = agent_id
        self.session_id = session_id
        self.from_type = from_type
        self.to_type = to_type
        self.reason = reason
        self.confidence = confidence
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id.value,
            "session_id": self.session_id,
            "from_type": self.from_type.value,
            "to_type": self.to_type.value,
            "reason": self.reason,
            "confidence": self.confidence
        }


class AgentResetToOrchestrator(DomainEvent):
    """
    Событие: Агент сброшен к Orchestrator.
    
    Публикуется когда агент возвращается к Orchestrator типу.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        previous_type: Предыдущий тип агента
        reason: Причина сброса
        timestamp: Время сброса
    """
    
    def __init__(
        self,
        agent_id: AgentId,
        session_id: str,
        previous_type: AgentType,
        reason: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Создать событие AgentResetToOrchestrator.
        
        Args:
            agent_id: ID агента
            session_id: ID сессии
            previous_type: Предыдущий тип
            reason: Причина сброса
            timestamp: Время события
        """
        super().__init__(
            event_type="agent.reset_to_orchestrator",
            timestamp=timestamp or datetime.now(timezone.utc)
        )
        self.agent_id = agent_id
        self.session_id = session_id
        self.previous_type = previous_type
        self.reason = reason
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id.value,
            "session_id": self.session_id,
            "previous_type": self.previous_type.value,
            "reason": self.reason
        }


class AgentMetadataUpdated(DomainEvent):
    """
    Событие: Метаданные агента обновлены.
    
    Публикуется когда изменяются метаданные агента.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        key: Ключ метаданных
        value: Новое значение
        timestamp: Время обновления
    """
    
    def __init__(
        self,
        agent_id: AgentId,
        session_id: str,
        key: str,
        value: any,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Создать событие AgentMetadataUpdated.
        
        Args:
            agent_id: ID агента
            session_id: ID сессии
            key: Ключ метаданных
            value: Новое значение
            timestamp: Время события
        """
        super().__init__(
            event_type="agent.metadata_updated",
            timestamp=timestamp or datetime.now(timezone.utc)
        )
        self.agent_id = agent_id
        self.session_id = session_id
        self.key = key
        self.value = value
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id.value,
            "session_id": self.session_id,
            "key": self.key,
            "value": str(self.value)
        }


class AgentSwitchLimitReached(DomainEvent):
    """
    Событие: Достигнут лимит переключений агента.
    
    Публикуется когда агент достигает максимального количества переключений.
    
    Атрибуты:
        agent_id: ID агента
        session_id: ID сессии
        switch_count: Текущее количество переключений
        max_switches: Максимальное количество переключений
        timestamp: Время события
    """
    
    def __init__(
        self,
        agent_id: AgentId,
        session_id: str,
        switch_count: int,
        max_switches: int,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Создать событие AgentSwitchLimitReached.
        
        Args:
            agent_id: ID агента
            session_id: ID сессии
            switch_count: Текущее количество переключений
            max_switches: Максимальное количество
            timestamp: Время события
        """
        super().__init__(
            event_type="agent.switch_limit_reached",
            timestamp=timestamp or datetime.now(timezone.utc)
        )
        self.agent_id = agent_id
        self.session_id = session_id
        self.switch_count = switch_count
        self.max_switches = max_switches
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id.value,
            "session_id": self.session_id,
            "switch_count": self.switch_count,
            "max_switches": self.max_switches
        }

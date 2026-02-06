"""
Agent Entity.

Упрощенная версия AgentContext с четким разделением ответственностей.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import Field, field_validator

from ...shared.base_entity import Entity
from ..value_objects.agent_id import AgentId
from ..value_objects.agent_capabilities import AgentCapabilities, AgentType


class AgentSwitchRecord(Entity):
    """
    Запись о переключении агента.
    
    Value Object для хранения информации о переключении.
    
    Атрибуты:
        from_agent: Агент, с которого переключились
        to_agent: Агент, на который переключились
        reason: Причина переключения
        switched_at: Время переключения
        confidence: Уверенность в переключении
    """
    
    from_agent: Optional[AgentType] = Field(
        default=None,
        description="Агент, с которого переключились"
    )
    to_agent: AgentType = Field(
        ...,
        description="Агент, на который переключились"
    )
    reason: str = Field(
        ...,
        description="Причина переключения"
    )
    switched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время переключения"
    )
    confidence: Optional[str] = Field(
        default=None,
        description="Уверенность в переключении"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь.
        
        Returns:
            Словарь с данными записи
        """
        return {
            "id": self.id,
            "from": self.from_agent.value if self.from_agent else None,
            "to": self.to_agent.value,
            "reason": self.reason,
            "timestamp": self.switched_at.isoformat(),
            "confidence": self.confidence
        }


class Agent(Entity):
    """
    Доменная сущность Agent (упрощенная версия AgentContext).
    
    Представляет агента в контексте сессии с его возможностями
    и историей переключений.
    
    Атрибуты:
        id: Уникальный ID агента
        session_id: ID сессии, к которой относится агент
        capabilities: Возможности агента
        switch_history: История переключений
        metadata: Дополнительные метаданные
        last_switch_at: Время последнего переключения
        switch_count: Количество переключений
    
    Бизнес-правила:
        - Нельзя переключиться на того же агента
        - Нельзя превысить max_switches из capabilities
        - История переключений сохраняется в хронологическом порядке
    
    Пример:
        >>> agent = Agent.create(
        ...     session_id="session-123",
        ...     capabilities=AgentCapabilities.for_orchestrator()
        ... )
        >>> agent.switch_to(
        ...     target_type=AgentType.CODER,
        ...     reason="Coding task detected"
        ... )
    """
    
    session_id: str = Field(
        ...,
        description="ID сессии, к которой относится агент"
    )
    capabilities: AgentCapabilities = Field(
        ...,
        description="Возможности агента"
    )
    switch_history: List[AgentSwitchRecord] = Field(
        default_factory=list,
        description="История переключений"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные"
    )
    last_switch_at: Optional[datetime] = Field(
        default=None,
        description="Время последнего переключения"
    )
    switch_count: int = Field(
        default=0,
        description="Количество переключений"
    )
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Валидация session_id."""
        if not v:
            raise ValueError("session_id не может быть пустым")
        return v
    
    @field_validator('capabilities')
    @classmethod
    def validate_capabilities(cls, v: Any) -> AgentCapabilities:
        """Валидация capabilities."""
        if not isinstance(v, AgentCapabilities):
            raise ValueError("capabilities должен быть AgentCapabilities")
        return v
    
    @property
    def current_type(self) -> AgentType:
        """Получить текущий тип агента."""
        return self.capabilities.agent_type
    
    @staticmethod
    def create(
        session_id: str,
        capabilities: AgentCapabilities,
        agent_id: Optional[AgentId] = None
    ) -> "Agent":
        """
        Создать нового Agent.
        
        Args:
            session_id: ID сессии
            capabilities: Возможности агента
            agent_id: ID агента (опционально, будет сгенерирован)
            
        Returns:
            Новый Agent
            
        Пример:
            >>> agent = Agent.create(
            ...     session_id="session-123",
            ...     capabilities=AgentCapabilities.for_coder()
            ... )
        """
        if agent_id is None:
            agent_id = AgentId.from_session_id(session_id)
        
        return Agent(
            id=agent_id.value,
            session_id=session_id,
            capabilities=capabilities
        )
    
    def can_switch_to(self, target_type: AgentType) -> bool:
        """
        Проверить возможность переключения на другой тип агента.
        
        Args:
            target_type: Целевой тип агента
            
        Returns:
            True если переключение возможно
            
        Пример:
            >>> if agent.can_switch_to(AgentType.CODER):
            ...     agent.switch_to(AgentType.CODER, "Need to code")
        """
        # Нельзя переключиться на тот же тип
        if self.current_type == target_type:
            return False
        
        # Нельзя превысить лимит переключений
        if self.switch_count >= self.capabilities.max_switches:
            return False
        
        return True
    
    def switch_to(
        self,
        target_type: AgentType,
        reason: str,
        confidence: Optional[str] = None
    ) -> AgentSwitchRecord:
        """
        Переключиться на другой тип агента.
        
        Args:
            target_type: Целевой тип агента
            reason: Причина переключения
            confidence: Уверенность в переключении
            
        Returns:
            Запись о переключении
            
        Raises:
            ValueError: Если переключение невозможно
            
        Пример:
            >>> record = agent.switch_to(
            ...     target_type=AgentType.CODER,
            ...     reason="User requested code changes"
            ... )
        """
        if not self.can_switch_to(target_type):
            if self.current_type == target_type:
                raise ValueError(f"Агент уже имеет тип {target_type.value}")
            else:
                raise ValueError(
                    f"Превышен лимит переключений: "
                    f"{self.switch_count}/{self.capabilities.max_switches}"
                )
        
        # Создать запись о переключении
        import uuid
        record = AgentSwitchRecord(
            id=str(uuid.uuid4()),
            from_agent=self.current_type,
            to_agent=target_type,
            reason=reason,
            confidence=confidence
        )
        
        # Добавить в историю
        self.switch_history.append(record)
        
        # Обновить состояние
        new_capabilities = AgentCapabilities.for_agent_type(target_type)
        self.capabilities = new_capabilities
        self.last_switch_at = datetime.now(timezone.utc)
        self.switch_count += 1
        self.mark_updated()
        
        return record
    
    def get_last_switch(self) -> Optional[AgentSwitchRecord]:
        """
        Получить последнее переключение.
        
        Returns:
            Последняя запись о переключении или None
            
        Пример:
            >>> last = agent.get_last_switch()
            >>> if last:
            ...     print(f"Last switch to: {last.to_agent.value}")
        """
        return self.switch_history[-1] if self.switch_history else None
    
    def get_switch_history_dict(self) -> List[Dict[str, Any]]:
        """
        Получить историю переключений в виде словарей.
        
        Returns:
            Список словарей с данными переключений
            
        Пример:
            >>> history = agent.get_switch_history_dict()
            >>> history[0]['to']
            'coder'
        """
        return [record.to_dict() for record in self.switch_history]
    
    def reset_to_orchestrator(self, reason: str = "Session reset") -> None:
        """
        Сбросить агента к Orchestrator типу.
        
        Args:
            reason: Причина сброса
            
        Пример:
            >>> agent.reset_to_orchestrator("Starting new task")
        """
        if self.current_type != AgentType.ORCHESTRATOR:
            self.switch_to(
                target_type=AgentType.ORCHESTRATOR,
                reason=reason
            )
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Добавить метаданные.
        
        Args:
            key: Ключ метаданных
            value: Значение метаданных
            
        Пример:
            >>> agent.add_metadata("user_preference", "verbose")
        """
        self.metadata[key] = value
        self.mark_updated()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Получить значение метаданных.
        
        Args:
            key: Ключ метаданных
            default: Значение по умолчанию
            
        Returns:
            Значение метаданных или default
            
        Пример:
            >>> pref = agent.get_metadata("user_preference", "normal")
        """
        return self.metadata.get(key, default)
    
    def supports_tool(self, tool_name: str) -> bool:
        """
        Проверить поддержку инструмента.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            True если инструмент поддерживается
            
        Пример:
            >>> if agent.supports_tool("write_file"):
            ...     # Выполнить операцию с файлом
            ...     pass
        """
        return self.capabilities.supports_tool(tool_name)
    
    def __repr__(self) -> str:
        """Строковое представление агента."""
        return (
            f"<Agent(id='{self.id}', "
            f"session_id='{self.session_id}', "
            f"type='{self.current_type.value}', "
            f"switches={self.switch_count})>"
        )

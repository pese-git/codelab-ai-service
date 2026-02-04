"""
Agent Entity.

Упрощенная версия AgentContext с четким разделением ответственностей.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

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
    
    from_agent: Optional[AgentType]
    to_agent: AgentType
    reason: str
    switched_at: datetime
    confidence: Optional[str] = None
    
    def __init__(
        self,
        id: str,
        from_agent: Optional[AgentType],
        to_agent: AgentType,
        reason: str,
        switched_at: Optional[datetime] = None,
        confidence: Optional[str] = None
    ) -> None:
        """
        Создать запись о переключении.
        
        Args:
            id: Уникальный ID записи
            from_agent: Агент, с которого переключились
            to_agent: Агент, на который переключились
            reason: Причина переключения
            switched_at: Время переключения
            confidence: Уверенность в переключении
        """
        super().__init__(id=id)
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.reason = reason
        self.switched_at = switched_at or datetime.now(timezone.utc)
        self.confidence = confidence
    
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
    
    def __init__(
        self,
        id: str,
        session_id: str,
        capabilities: AgentCapabilities,
        switch_history: Optional[List[AgentSwitchRecord]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        last_switch_at: Optional[datetime] = None,
        switch_count: int = 0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ) -> None:
        """
        Создать Agent.
        
        Args:
            id: Уникальный ID агента
            session_id: ID сессии
            capabilities: Возможности агента
            switch_history: История переключений
            metadata: Дополнительные метаданные
            last_switch_at: Время последнего переключения
            switch_count: Количество переключений
            created_at: Время создания
            updated_at: Время последнего обновления
        """
        super().__init__(
            id=id,
            created_at=created_at,
            updated_at=updated_at
        )
        
        if not session_id:
            raise ValueError("session_id не может быть пустым")
        
        if not isinstance(capabilities, AgentCapabilities):
            raise ValueError("capabilities должен быть AgentCapabilities")
        
        self._session_id = session_id
        self._capabilities = capabilities
        self._switch_history = switch_history or []
        self._metadata = metadata or {}
        self._last_switch_at = last_switch_at
        self._switch_count = switch_count
    
    @property
    def session_id(self) -> str:
        """Получить ID сессии."""
        return self._session_id
    
    @property
    def capabilities(self) -> AgentCapabilities:
        """Получить возможности агента."""
        return self._capabilities
    
    @property
    def current_type(self) -> AgentType:
        """Получить текущий тип агента."""
        return self._capabilities.agent_type
    
    @property
    def switch_history(self) -> List[AgentSwitchRecord]:
        """Получить историю переключений."""
        return self._switch_history.copy()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Получить метаданные."""
        return self._metadata.copy()
    
    @property
    def last_switch_at(self) -> Optional[datetime]:
        """Получить время последнего переключения."""
        return self._last_switch_at
    
    @property
    def switch_count(self) -> int:
        """Получить количество переключений."""
        return self._switch_count
    
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
        if self._switch_count >= self._capabilities.max_switches:
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
                    f"{self._switch_count}/{self._capabilities.max_switches}"
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
        self._switch_history.append(record)
        
        # Обновить состояние
        new_capabilities = AgentCapabilities.for_agent_type(target_type)
        self._capabilities = new_capabilities
        self._last_switch_at = datetime.now(timezone.utc)
        self._switch_count += 1
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
        return self._switch_history[-1] if self._switch_history else None
    
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
        return [record.to_dict() for record in self._switch_history]
    
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
        self._metadata[key] = value
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
        return self._metadata.get(key, default)
    
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
        return self._capabilities.supports_tool(tool_name)
    
    def __repr__(self) -> str:
        """Строковое представление агента."""
        return (
            f"<Agent(id='{self.id}', "
            f"session_id='{self._session_id}', "
            f"type='{self.current_type.value}', "
            f"switches={self._switch_count})>"
        )

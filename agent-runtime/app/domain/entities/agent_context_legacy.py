"""
Доменная сущность AgentContext (Контекст агента).

Представляет контекст работы агента в рамках сессии.
Отслеживает текущего агента, историю переключений и метаданные.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import Field

from .base import Entity
from ...core.errors import AgentSwitchError


class AgentType(str, Enum):
    """
    Типы агентов в системе.
    
    Каждый агент имеет свою специализацию и набор инструментов.
    """
    ORCHESTRATOR = "orchestrator"  # Маршрутизация задач
    CODER = "coder"                # Написание кода
    ARCHITECT = "architect"        # Проектирование архитектуры
    DEBUG = "debug"                # Отладка и исследование
    ASK = "ask"                    # Ответы на вопросы
    UNIVERSAL = "universal"        # Универсальный агент


class AgentSwitch(Entity):
    """
    Запись о переключении агента.
    
    Хранит информацию о том, когда и почему произошло
    переключение между агентами.
    
    Атрибуты:
        from_agent: Агент, с которого переключились
        to_agent: Агент, на который переключились
        reason: Причина переключения
        switched_at: Время переключения
        confidence: Уверенность в переключении (для LLM-based routing)
        metadata: Дополнительные метаданные
    """
    
    from_agent: Optional[AgentType] = Field(
        default=None,
        description="Агент, с которого переключились (None для первого агента)"
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
        description="Уверенность в переключении (low, medium, high)"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные переключения"
    )


class AgentContext(Entity):
    """
    Доменная сущность контекста агента.
    
    Контекст агента отслеживает, какой агент в данный момент
    работает с сессией, и хранит историю всех переключений.
    
    Атрибуты:
        session_id: ID сессии, к которой относится контекст
        current_agent: Текущий активный агент
        switch_history: История переключений агентов
        metadata: Дополнительные метаданные контекста
        last_switch_at: Время последнего переключения
        switch_count: Количество переключений
        max_switches: Максимальное количество переключений (защита от циклов)
    
    Бизнес-правила:
        - Нельзя переключиться на того же агента
        - Нельзя превысить max_switches переключений
        - История переключений сохраняется в хронологическом порядке
        - При переключении обновляется last_switch_at
    
    Пример:
        >>> context = AgentContext(
        ...     id="ctx-1",
        ...     session_id="session-1",
        ...     current_agent=AgentType.ORCHESTRATOR
        ... )
        >>> context.switch_to(
        ...     target_agent=AgentType.CODER,
        ...     reason="Coding task detected"
        ... )
        >>> context.current_agent
        <AgentType.CODER: 'coder'>
    """
    
    session_id: str = Field(
        ...,
        description="ID сессии, к которой относится контекст"
    )
    
    current_agent: AgentType = Field(
        default=AgentType.ORCHESTRATOR,
        description="Текущий активный агент"
    )
    
    switch_history: List[AgentSwitch] = Field(
        default_factory=list,
        description="История переключений агентов"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные контекста"
    )
    
    last_switch_at: Optional[datetime] = Field(
        default=None,
        description="Время последнего переключения агента"
    )
    
    switch_count: int = Field(
        default=0,
        description="Количество переключений агентов"
    )
    
    max_switches: int = Field(
        default=50,
        description="Максимальное количество переключений (защита от циклов)"
    )
    
    def switch_to(
        self,
        target_agent: AgentType,
        reason: str,
        confidence: Optional[str] = None
    ) -> AgentSwitch:
        """
        Переключиться на другого агента.
        
        Создает запись о переключении и обновляет текущего агента.
        
        Args:
            target_agent: Агент, на который нужно переключиться
            reason: Причина переключения
            confidence: Уверенность в переключении (опционально)
            
        Returns:
            Созданная запись о переключении
            
        Raises:
            AgentSwitchError: Если переключение невозможно
            
        Пример:
            >>> switch = context.switch_to(
            ...     target_agent=AgentType.CODER,
            ...     reason="User requested code changes",
            ...     confidence="high"
            ... )
            >>> context.current_agent
            <AgentType.CODER: 'coder'>
        """
        # Проверка: нельзя переключиться на того же агента
        if self.current_agent == target_agent:
            raise AgentSwitchError(
                from_agent=self.current_agent.value,
                to_agent=target_agent.value,
                reason="Агент уже активен",
                details={"session_id": self.session_id}
            )
        
        # Проверка: не превышен лимит переключений
        if self.switch_count >= self.max_switches:
            raise AgentSwitchError(
                from_agent=self.current_agent.value,
                to_agent=target_agent.value,
                reason=f"Превышен лимит переключений ({self.max_switches})",
                details={
                    "session_id": self.session_id,
                    "switch_count": self.switch_count
                }
            )
        
        # Создать запись о переключении
        import uuid
        switch = AgentSwitch(
            id=str(uuid.uuid4()),
            from_agent=self.current_agent,
            to_agent=target_agent,
            reason=reason,
            confidence=confidence
        )
        
        # Добавить в историю
        self.switch_history.append(switch)
        
        # Обновить состояние
        self.current_agent = target_agent
        self.last_switch_at = datetime.now(timezone.utc)
        self.switch_count += 1
        self.mark_updated()
        
        return switch
    
    def can_switch_to(self, target_agent: AgentType) -> bool:
        """
        Проверить возможность переключения на агента.
        
        Args:
            target_agent: Агент для проверки
            
        Returns:
            True если переключение возможно
            
        Пример:
            >>> if context.can_switch_to(AgentType.CODER):
            ...     context.switch_to(AgentType.CODER, "Need to write code")
        """
        # Нельзя переключиться на того же агента
        if self.current_agent == target_agent:
            return False
        
        # Нельзя превысить лимит переключений
        if self.switch_count >= self.max_switches:
            return False
        
        return True
    
    def get_switch_history(self) -> List[Dict[str, Any]]:
        """
        Получить историю переключений в виде словарей.
        
        Returns:
            Список записей о переключениях
            
        Пример:
            >>> history = context.get_switch_history()
            >>> history[0]['from_agent']
            'orchestrator'
        """
        return [
            {
                "from": switch.from_agent.value if switch.from_agent else None,
                "to": switch.to_agent.value,
                "reason": switch.reason,
                "timestamp": switch.switched_at.isoformat(),
                "confidence": switch.confidence
            }
            for switch in self.switch_history
        ]
    
    def get_last_switch(self) -> Optional[AgentSwitch]:
        """
        Получить последнее переключение агента.
        
        Returns:
            Последняя запись о переключении или None
            
        Пример:
            >>> last = context.get_last_switch()
            >>> if last:
            ...     print(f"Last switch: {last.to_agent.value}")
        """
        return self.switch_history[-1] if self.switch_history else None
    
    def get_switches_count(self) -> int:
        """
        Получить количество переключений.
        
        Returns:
            Количество переключений агентов
        """
        return self.switch_count
    
    def reset_to_orchestrator(self, reason: str = "Session reset") -> None:
        """
        Сбросить контекст к Orchestrator агенту.
        
        Полезно для начала новой задачи в рамках той же сессии.
        
        Args:
            reason: Причина сброса
            
        Пример:
            >>> context.reset_to_orchestrator(reason="User started new task")
            >>> context.current_agent
            <AgentType.ORCHESTRATOR: 'orchestrator'>
        """
        if self.current_agent != AgentType.ORCHESTRATOR:
            self.switch_to(
                target_agent=AgentType.ORCHESTRATOR,
                reason=reason
            )
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Добавить метаданные в контекст.
        
        Args:
            key: Ключ метаданных
            value: Значение метаданных
            
        Пример:
            >>> context.add_metadata("user_preference", "verbose")
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
            >>> pref = context.get_metadata("user_preference", "normal")
        """
        return self.metadata.get(key, default)
    
    def __repr__(self) -> str:
        """Строковое представление контекста агента"""
        return (
            f"<AgentContext(id='{self.id}', "
            f"session_id='{self.session_id}', "
            f"current_agent='{self.current_agent.value}', "
            f"switches={self.switch_count})>"
        )

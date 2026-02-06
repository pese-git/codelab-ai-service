"""
Data Transfer Objects для контекстов агентов.

DTO для передачи данных контекстов агентов между слоями.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from ...domain.agent_context.entities.agent import Agent as AgentContext, AgentSwitchRecord as AgentSwitch


class AgentSwitchDTO(BaseModel):
    """
    DTO для записи о переключении агента.
    
    Атрибуты:
        from_agent: Агент, с которого переключились
        to_agent: Агент, на который переключились
        reason: Причина переключения
        switched_at: Время переключения
        confidence: Уверенность в переключении
    
    Пример:
        >>> dto = AgentSwitchDTO(
        ...     from_agent="orchestrator",
        ...     to_agent="coder",
        ...     reason="Coding task",
        ...     switched_at=datetime.now()
        ... )
    """
    
    from_agent: Optional[str] = Field(
        default=None,
        description="Агент, с которого переключились"
    )
    to_agent: str = Field(description="Агент, на который переключились")
    reason: str = Field(description="Причина переключения")
    switched_at: datetime = Field(description="Время переключения")
    confidence: Optional[str] = Field(
        default=None,
        description="Уверенность в переключении"
    )
    
    @classmethod
    def from_entity(cls, switch: AgentSwitch) -> "AgentSwitchDTO":
        """
        Создать DTO из доменной сущности.
        
        Args:
            switch: Доменная сущность переключения
            
        Returns:
            DTO переключения
        """
        return cls(
            from_agent=switch.from_agent.value if switch.from_agent else None,
            to_agent=switch.to_agent.value,
            reason=switch.reason,
            switched_at=switch.switched_at,
            confidence=switch.confidence
        )


class AgentContextDTO(BaseModel):
    """
    DTO для контекста агента.
    
    Используется для передачи данных контекста между слоями.
    
    Атрибуты:
        id: ID контекста
        session_id: ID сессии
        current_agent: Текущий агент
        switch_count: Количество переключений
        switch_history: История переключений (опционально)
        last_switch_at: Время последнего переключения
        created_at: Время создания контекста
    
    Пример:
        >>> dto = AgentContextDTO(
        ...     id="ctx-1",
        ...     session_id="session-1",
        ...     current_agent="coder",
        ...     switch_count=2,
        ...     created_at=datetime.now()
        ... )
    """
    
    id: str = Field(description="ID контекста")
    session_id: str = Field(description="ID сессии")
    current_agent: str = Field(description="Текущий агент")
    switch_count: int = Field(description="Количество переключений")
    switch_history: Optional[List[AgentSwitchDTO]] = Field(
        default=None,
        description="История переключений"
    )
    last_switch_at: Optional[datetime] = Field(
        default=None,
        description="Время последнего переключения"
    )
    created_at: datetime = Field(description="Время создания контекста")
    
    @classmethod
    def from_entity(
        cls,
        context: AgentContext,
        include_history: bool = False
    ) -> "AgentContextDTO":
        """
        Создать DTO из доменной сущности.
        
        Args:
            context: Доменная сущность контекста
            include_history: Включить ли историю переключений
            
        Returns:
            DTO контекста
            
        Пример:
            >>> context = AgentContext(id="ctx-1", session_id="session-1", ...)
            >>> dto = AgentContextDTO.from_entity(context, include_history=True)
        """
        history_dto = None
        if include_history:
            history_dto = [
                AgentSwitchDTO.from_entity(switch)
                for switch in context.switch_history
            ]
        
        return cls(
            id=str(context.id) if hasattr(context.id, 'value') else context.id,
            session_id=context.session_id,
            current_agent=context.current_type.value if hasattr(context, 'current_type') else context.current_agent.value,
            switch_count=context.switch_count,
            switch_history=history_dto,
            last_switch_at=context.last_switch_at,
            created_at=context.created_at
        )

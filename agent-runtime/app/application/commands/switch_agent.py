"""
Команда переключения агента.

Переключает текущего агента для сессии на другого.
"""

from typing import Optional
from pydantic import Field

from .base import Command, CommandHandler
from ...domain.agent_context.services.agent_coordination_service import AgentCoordinationService
from ...domain.agent_context.value_objects.agent_capabilities import AgentType
from ..dto.agent_context_dto import AgentContextDTO


class SwitchAgentCommand(Command):
    """
    Команда переключения агента.
    
    Атрибуты:
        session_id: ID сессии
        target_agent: Целевой агент
        reason: Причина переключения
        confidence: Уверенность в переключении (опционально)
    
    Пример:
        >>> command = SwitchAgentCommand(
        ...     session_id="session-1",
        ...     target_agent="coder",
        ...     reason="User requested code changes",
        ...     confidence="high"
        ... )
    """
    
    session_id: str = Field(description="ID сессии")
    target_agent: str = Field(description="Целевой агент (orchestrator, coder, etc.)")
    reason: str = Field(description="Причина переключения")
    confidence: Optional[str] = Field(
        default=None,
        description="Уверенность в переключении (low, medium, high)"
    )


class SwitchAgentHandler(CommandHandler[AgentContextDTO]):
    """
    Обработчик команды переключения агента.
    
    Переключает агента через доменный сервис и
    возвращает DTO обновленного агента.
    
    Атрибуты:
        _coordination_service: Доменный сервис координации агентов
    
    Пример:
        >>> handler = SwitchAgentHandler(coordination_service)
        >>> command = SwitchAgentCommand(
        ...     session_id="session-1",
        ...     target_agent="coder",
        ...     reason="Coding task"
        ... )
        >>> dto = await handler.handle(command)
        >>> dto.current_agent
        'coder'
    """
    
    def __init__(self, coordination_service: AgentCoordinationService):
        """
        Инициализация обработчика.
        
        Args:
            coordination_service: Доменный сервис координации агентов
        """
        self._coordination_service = coordination_service
    
    async def handle(self, command: SwitchAgentCommand) -> AgentContextDTO:
        """
        Обработать команду переключения агента.
        
        Args:
            command: Команда переключения агента
            
        Returns:
            DTO обновленного контекста агента
            
        Raises:
            AgentSwitchError: Если переключение невозможно
            ValueError: Если указан неверный тип агента
            
        Пример:
            >>> command = SwitchAgentCommand(
            ...     session_id="session-1",
            ...     target_agent="coder",
            ...     reason="Coding task"
            ... )
            >>> dto = await handler.handle(command)
        """
        # Преобразовать строку в AgentType
        try:
            target_agent_type = AgentType(command.target_agent)
        except ValueError:
            raise ValueError(
                f"Неверный тип агента: '{command.target_agent}'. "
                f"Допустимые значения: {[t.value for t in AgentType]}"
            )
        
        # Переключить агента через доменный сервис
        agent = await self._coordination_service.switch_agent(
            session_id=command.session_id,
            target_type=target_agent_type,
            reason=command.reason,
            confidence=command.confidence
        )
        
        # Преобразовать в DTO
        return AgentContextDTO.from_entity(agent, include_history=True)

"""
Agent Orchestration Adapter.

Адаптер для обратной совместимости между новым AgentCoordinationService
и старым AgentOrchestrationService API.

Позволяет постепенно мигрировать код, сохраняя работоспособность.
"""

import logging
from typing import Optional

from ..agent_context.services.agent_coordination_service import AgentCoordinationService
from ..agent_context.entities.agent import Agent, Agent as AgentContext
from ..agent_context.value_objects.agent_capabilities import AgentType

logger = logging.getLogger("agent-runtime.adapters.agent_orchestration")


class AgentOrchestrationAdapter:
    """
    Адаптер между AgentCoordinationService и AgentOrchestrationService API.
    
    Предоставляет старый API AgentOrchestrationService, но использует
    новый AgentCoordinationService внутри.
    
    Это позволяет:
    1. Постепенно мигрировать код
    2. Сохранить работоспособность существующего кода
    3. Тестировать новую архитектуру без breaking changes
    
    Атрибуты:
        _coordination_service: Новый сервис для координации агентов
    
    Пример:
        >>> adapter = AgentOrchestrationAdapter(coordination_service)
        >>> context = await adapter.get_or_create_context("session-1")
        >>> # Внутри использует AgentCoordinationService
    """
    
    def __init__(self, coordination_service: AgentCoordinationService):
        """
        Инициализация адаптера.
        
        Args:
            coordination_service: Новый сервис для координации агентов
        """
        self._coordination_service = coordination_service
    
    async def get_or_create_context(
        self,
        session_id: str,
        initial_agent: AgentType = AgentType.ORCHESTRATOR
    ) -> AgentContext:
        """
        Получить или создать контекст агента (адаптирует get_or_create_agent).
        
        Args:
            session_id: ID сессии
            initial_agent: Начальный агент
            
        Returns:
            AgentContext (адаптированный из Agent)
        """
        agent = await self._coordination_service.get_or_create_agent(
            session_id=session_id,
            initial_type=initial_agent
        )
        return self._agent_to_context(agent)
    
    async def switch_agent(
        self,
        session_id: str,
        target_agent: AgentType,
        reason: str,
        confidence: Optional[str] = None
    ) -> AgentContext:
        """
        Переключить агента (адаптирует switch_agent).
        
        Args:
            session_id: ID сессии
            target_agent: Целевой агент
            reason: Причина переключения
            confidence: Уверенность
            
        Returns:
            AgentContext (адаптированный из Agent)
        """
        agent = await self._coordination_service.switch_agent(
            session_id=session_id,
            target_type=target_agent,
            reason=reason,
            confidence=confidence
        )
        return self._agent_to_context(agent)
    
    async def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Получить текущего агента (делегирует в coordination_service).
        
        Args:
            session_id: ID сессии
            
        Returns:
            Тип текущего агента или None
        """
        return await self._coordination_service.get_current_agent_type(session_id)
    
    async def get_agent_usage_stats(self) -> dict:
        """
        Получить статистику использования агентов (делегирует).
        
        Returns:
            Словарь с количеством сессий для каждого агента
        """
        return await self._coordination_service.get_agent_usage_stats()
    
    def _agent_to_context(self, agent: Agent) -> AgentContext:
        """
        Конвертировать Agent в AgentContext для обратной совместимости.
        
        Args:
            agent: Agent entity
            
        Returns:
            AgentContext entity (legacy)
        """
        from ..agent_context.entities.agent import AgentSwitchRecord as AgentSwitch
        import uuid
        
        # Создать AgentContext с теми же данными
        context = AgentContext(
            id=agent.id,
            session_id=agent.session_id,
            current_agent=agent.current_type,
            switch_count=agent.switch_count,
            last_switch_at=agent.last_switch_at,
            metadata=agent.metadata.copy(),
            created_at=agent.created_at,
            updated_at=agent.updated_at
        )
        
        # Конвертировать историю переключений в объекты AgentSwitch
        for record in agent.switch_history:
            switch = AgentSwitch(
                id=record.id if hasattr(record, 'id') and record.id else str(uuid.uuid4()),
                from_agent=record.from_agent,
                to_agent=record.to_agent,
                reason=record.reason,
                switched_at=record.switched_at,
                confidence=record.confidence
            )
            context.switch_history.append(switch)
        
        return context

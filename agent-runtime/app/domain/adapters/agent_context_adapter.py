"""
AgentContext Adapter - адаптер обратной совместимости.

Преобразует между старой моделью AgentContext и новой моделью Agent.
Обеспечивает плавную миграцию без breaking changes.
"""

from typing import Optional, List
from datetime import datetime

from ..agent_context.entities.agent import Agent as AgentContext, AgentSwitchRecord as AgentSwitch
from ..agent_context.value_objects.agent_capabilities import AgentType
from ..agent_context.entities.agent import Agent, AgentSwitchRecord
from ..agent_context.value_objects import AgentId, AgentCapabilities


class AgentContextAdapter:
    """
    Адаптер для преобразования AgentContext ↔ Agent.
    
    Обеспечивает обратную совместимость при миграции на новую архитектуру.
    Позволяет использовать новые repositories с существующим кодом.
    
    Методы:
        to_agent: AgentContext → Agent
        from_agent: Agent → AgentContext
        
    Пример:
        >>> context = AgentContext(id="ctx-1", session_id="s1")
        >>> agent = AgentContextAdapter.to_agent(context)
        >>> restored_context = AgentContextAdapter.from_agent(agent)
    """
    
    @staticmethod
    def to_agent(agent_context: AgentContext) -> Agent:
        """
        Преобразовать AgentContext в Agent.
        
        Args:
            agent_context: Старая модель AgentContext
            
        Returns:
            Новая модель Agent
            
        Пример:
            >>> context = AgentContext(
            ...     id="ctx-1",
            ...     session_id="s1",
            ...     current_agent=AgentType.ORCHESTRATOR
            ... )
            >>> agent = AgentContextAdapter.to_agent(context)
            >>> agent.current_type
            <AgentType.ORCHESTRATOR: 'orchestrator'>
        """
        # Создать AgentCapabilities из current_agent
        # AgentCapabilities использует factory methods для каждого типа
        agent_type = agent_context.current_agent
        
        # Создаем capabilities с правильными параметрами
        capabilities = AgentCapabilities(
            agent_type=agent_type,
            max_switches=agent_context.max_switches
        )
        
        # Преобразовать switch_history
        switch_history = [
            AgentSwitchRecord(
                id=switch.id,
                from_agent=switch.from_agent,
                to_agent=switch.to_agent,
                reason=switch.reason,
                switched_at=switch.switched_at,
                confidence=switch.confidence
            )
            for switch in agent_context.switch_history
        ]
        
        # Создать Agent с данными из AgentContext
        # Agent не Pydantic модель, использует обычный __init__
        agent = Agent(
            id=agent_context.id,
            session_id=agent_context.session_id,
            capabilities=capabilities,
            switch_history=switch_history,
            metadata=agent_context.metadata.copy(),
            last_switch_at=agent_context.last_switch_at,
            switch_count=agent_context.switch_count,
            created_at=agent_context.created_at,
            updated_at=agent_context.updated_at
        )
        
        return agent
    
    @staticmethod
    def from_agent(agent: Agent) -> AgentContext:
        """
        Преобразовать Agent в AgentContext.
        
        Args:
            agent: Новая модель Agent
            
        Returns:
            Старая модель AgentContext
            
        Пример:
            >>> agent = Agent.create(
            ...     session_id="s1",
            ...     capabilities=AgentCapabilities.for_orchestrator()
            ... )
            >>> context = AgentContextAdapter.from_agent(agent)
            >>> context.current_agent
            <AgentType.ORCHESTRATOR: 'orchestrator'>
        """
        # Преобразовать switch_history (используем properties)
        switch_history = [
            AgentSwitch(
                id=record.id,
                from_agent=record.from_agent,
                to_agent=record.to_agent,
                reason=record.reason,
                switched_at=record.switched_at,
                confidence=record.confidence,
                created_at=record.created_at,
                updated_at=record.updated_at
            )
            for record in agent.switch_history  # switch_history - это property
        ]
        
        # Создать AgentContext с данными из Agent (используем properties)
        agent_context = AgentContext(
            id=agent.id,
            session_id=agent.session_id,
            current_agent=agent.current_type,  # current_type - это property
            switch_history=switch_history,
            metadata=agent.metadata,  # metadata - это property, возвращает copy
            last_switch_at=agent.last_switch_at,
            switch_count=agent.switch_count,
            max_switches=agent.capabilities.max_switches,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        )
        
        return agent_context
    
    @staticmethod
    def to_agent_list(contexts: List[AgentContext]) -> List[Agent]:
        """
        Преобразовать список AgentContext в список Agent.
        
        Args:
            contexts: Список старых моделей AgentContext
            
        Returns:
            Список новых моделей Agent
            
        Пример:
            >>> contexts = [
            ...     AgentContext(id="c1", session_id="s1"),
            ...     AgentContext(id="c2", session_id="s2")
            ... ]
            >>> agents = AgentContextAdapter.to_agent_list(contexts)
            >>> len(agents)
            2
        """
        return [AgentContextAdapter.to_agent(context) for context in contexts]
    
    @staticmethod
    def from_agent_list(agents: List[Agent]) -> List[AgentContext]:
        """
        Преобразовать список Agent в список AgentContext.
        
        Args:
            agents: Список новых моделей Agent
            
        Returns:
            Список старых моделей AgentContext
            
        Пример:
            >>> agent1 = Agent.create("s1", AgentCapabilities.for_orchestrator())
            >>> agent2 = Agent.create("s2", AgentCapabilities.for_coder())
            >>> contexts = AgentContextAdapter.from_agent_list([agent1, agent2])
            >>> len(contexts)
            2
        """
        return [AgentContextAdapter.from_agent(agent) for agent in agents]
    
    @staticmethod
    def sync_state(agent_context: AgentContext, agent: Agent) -> None:
        """
        Синхронизировать состояние между AgentContext и Agent.
        
        Полезно для обновления существующего объекта без создания нового.
        
        Args:
            agent_context: AgentContext для обновления
            agent: Agent с актуальными данными
            
        Пример:
            >>> context = AgentContext(id="c1", session_id="s1")
            >>> agent = Agent.create("s1", AgentCapabilities.for_orchestrator())
            >>> agent.switch_to(AgentType.CODER, "Coding task")
            >>> AgentContextAdapter.sync_state(context, agent)
            >>> context.current_agent
            <AgentType.CODER: 'coder'>
        """
        agent_context.current_agent = agent.current_type  # property
        agent_context.last_switch_at = agent.last_switch_at  # property
        agent_context.switch_count = agent.switch_count  # property
        agent_context.metadata = agent.metadata  # property возвращает copy
        agent_context.updated_at = agent.updated_at
        
        # Синхронизировать switch_history (используем property)
        agent_context.switch_history = [
            AgentSwitch(
                id=record.id,
                from_agent=record.from_agent,
                to_agent=record.to_agent,
                reason=record.reason,
                switched_at=record.switched_at,
                confidence=record.confidence,
                created_at=record.created_at,
                updated_at=record.updated_at
            )
            for record in agent.switch_history  # property
        ]

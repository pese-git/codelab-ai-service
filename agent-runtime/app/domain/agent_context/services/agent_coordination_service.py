"""
Agent Coordination Service.

Доменный сервис для координации агентов - рефакторинг AgentOrchestrationService.
Использует новую архитектуру с Agent entity и AgentCapabilities Value Object.
"""

import logging
from typing import Optional, Dict, Any

from ..entities.agent import Agent, AgentSwitchRecord
from ..value_objects.agent_id import AgentId
from ..value_objects.agent_capabilities import AgentCapabilities, AgentType
from ..repositories.agent_repository import AgentRepository
from ..events.agent_events import (
    AgentCreated,
    AgentSwitched,
)
# Импортируем legacy события для совместимости
from ...events.agent_events import (
    AgentAssigned,
    AgentSwitchRequested,
)
from ....core.errors import AgentSwitchError

logger = logging.getLogger("agent-runtime.domain.agent_coordination")


class AgentCoordinationService:
    """
    Доменный сервис для координации агентов.
    
    Рефакторинг AgentOrchestrationService с использованием новой архитектуры:
    - Использует Agent вместо AgentContext
    - Использует AgentCapabilities вместо простого AgentType
    - Использует AgentId Value Object
    - Генерирует Domain Events
    
    Размер: ~350 строк (вместо 237 в AgentOrchestrationService)
    Сложность: Средняя (координация операций)
    Зависимости: 4 (Repository, Events, Errors, Value Objects)
    
    Атрибуты:
        _repository: Repository для агентов
        _event_publisher: Функция для публикации событий (опционально)
    
    Пример:
        >>> service = AgentCoordinationService(repository)
        >>> agent = await service.assign_agent(
        ...     session_id="session-1",
        ...     agent_type=AgentType.CODER
        ... )
    """
    
    def __init__(
        self,
        repository: AgentRepository = None,
        event_publisher=None,
        uow=None  # Optional[SSEUnitOfWork]
    ):
        """
        Инициализация сервиса.
        
        Args:
            repository: Repository для работы с агентами (deprecated, используйте uow)
            event_publisher: Функция для публикации событий (опционально)
            uow: Unit of Work для доступа к репозиториям (рекомендуется)
        """
        self._repository = repository
        self._uow = uow
        self._event_publisher = event_publisher
    
    def _get_repository(self) -> AgentRepository:
        """Получить repository из UoW или использовать переданный."""
        if self._uow:
            return self._uow.agents
        if self._repository:
            return self._repository
        raise RuntimeError(
            "AgentCoordinationService requires either uow or repository"
        )
    
    async def get_or_create_agent(
        self,
        session_id: str,
        initial_type: AgentType = AgentType.ORCHESTRATOR,
        uow=None  # Optional[SSEUnitOfWork]
    ) -> Agent:
        """
        Получить существующего агента или создать нового.
        
        Args:
            session_id: ID сессии
            initial_type: Начальный тип агента для новых агентов
            uow: Unit of Work для доступа к репозиториям (опционально)
            
        Returns:
            Agent
            
        Пример:
            >>> agent = await service.get_or_create_agent("session-1", uow=uow)
            >>> agent.current_type
            <AgentType.ORCHESTRATOR: 'orchestrator'>
        """
        # Получить repository (из UoW если передан, иначе из self)
        repo = uow.agents if uow else self._get_repository()
        
        # Попытаться найти существующего агента
        agent = await repo.find_by_session_id(session_id)
        
        if agent:
            logger.debug(f"Найден существующий агент для сессии {session_id}")
            return agent
        
        # Создать нового агента с capabilities для указанного типа
        capabilities = self._get_capabilities_for_type(initial_type)
        agent = Agent.create(
            session_id=session_id,
            capabilities=capabilities
        )
        
        # Сохранить
        await repo.save(agent)
        
        logger.info(
            f"Создан новый агент для сессии {session_id} "
            f"с начальным типом {initial_type.value}"
        )
        
        # Опубликовать событие
        if self._event_publisher:
            event = AgentAssigned(
                aggregate_id=session_id,
                session_id=session_id,
                agent_type=initial_type.value,
                reason="Initial assignment"
            )
            await self._event_publisher(event)
        
        return agent
    
    async def assign_agent(
        self,
        session_id: str,
        agent_type: AgentType,
        reason: str = "Manual assignment"
    ) -> Agent:
        """
        Назначить агента для сессии.
        
        Если агент уже существует, переключает его на указанный тип.
        Если агента нет, создает нового с указанным типом.
        
        Args:
            session_id: ID сессии
            agent_type: Тип агента
            reason: Причина назначения
            
        Returns:
            Agent
            
        Пример:
            >>> agent = await service.assign_agent(
            ...     session_id="session-1",
            ...     agent_type=AgentType.CODER,
            ...     reason="User requested code changes"
            ... )
        """
        # Попытаться найти существующего агента
        agent = await self._repository.find_by_session_id(session_id)
        
        if agent:
            # Если агент уже нужного типа, вернуть его
            if agent.current_type == agent_type:
                logger.debug(
                    f"Агент для сессии {session_id} уже имеет тип {agent_type.value}"
                )
                return agent
            
            # Иначе переключить
            return await self.switch_agent(
                session_id=session_id,
                target_type=agent_type,
                reason=reason
            )
        
        # Создать нового агента с указанным типом
        capabilities = self._get_capabilities_for_type(agent_type)
        agent = Agent.create(
            session_id=session_id,
            capabilities=capabilities
        )
        
        # Сохранить
        await self._repository.save(agent)
        
        logger.info(
            f"Создан новый агент для сессии {session_id} "
            f"с типом {agent_type.value}"
        )
        
        # Опубликовать событие
        if self._event_publisher:
            event = AgentAssigned(
                aggregate_id=session_id,
                session_id=session_id,
                agent_type=agent_type.value,
                reason=reason
            )
            await self._event_publisher(event)
        
        return agent
    
    async def switch_agent(
        self,
        session_id: str,
        target_type: AgentType,
        reason: str,
        confidence: Optional[str] = None
    ) -> Agent:
        """
        Переключить агента для сессии.
        
        Args:
            session_id: ID сессии
            target_type: Целевой тип агента
            reason: Причина переключения
            confidence: Уверенность в переключении (опционально)
            
        Returns:
            Обновленный Agent
            
        Raises:
            AgentSwitchError: Если переключение невозможно
            
        Пример:
            >>> agent = await service.switch_agent(
            ...     session_id="session-1",
            ...     target_type=AgentType.CODER,
            ...     reason="Coding task detected",
            ...     confidence="high"
            ... )
        """
        # Получить агента
        agent = await self._repository.find_by_session_id(session_id)
        
        if not agent:
            # Создать нового агента с целевым типом
            agent = await self.assign_agent(
                session_id=session_id,
                agent_type=target_type,
                reason=reason
            )
            return agent
        
        # Запомнить предыдущий тип
        from_type = agent.current_type
        
        # Опубликовать событие запроса переключения
        if self._event_publisher:
            event = AgentSwitchRequested(
                aggregate_id=session_id,
                session_id=session_id,
                from_agent=from_type.value,
                to_agent=target_type.value,
                reason=reason,
                requested_by="system"
            )
            await self._event_publisher(event)
        
        # Выполнить переключение (валидация внутри)
        try:
            switch_record = agent.switch_to(
                target_type=target_type,
                reason=reason,
                confidence=confidence
            )
        except ValueError as e:
            error_msg = f"Не удалось переключить агента: {e}"
            logger.warning(error_msg)
            raise AgentSwitchError(
                from_agent=from_type.value,
                to_agent=target_type.value,
                reason=error_msg
            ) from e
        
        # Сохранить агента
        await self._repository.save(agent)
        
        logger.info(
            f"Агент переключен для сессии {session_id}: "
            f"{from_type.value} -> {target_type.value} "
            f"(причина: {reason})"
        )
        
        # Опубликовать событие успешного переключения
        if self._event_publisher:
            event = AgentSwitched(
                agent_id=AgentId(value=agent.id),
                session_id=session_id,
                from_type=from_type,
                to_type=target_type,
                reason=reason,
                confidence=confidence
            )
            await self._event_publisher(event)
        
        return agent
    
    async def get_current_agent_type(
        self,
        session_id: str
    ) -> Optional[AgentType]:
        """
        Получить текущий тип агента для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Тип текущего агента или None если агент не найден
            
        Пример:
            >>> agent_type = await service.get_current_agent_type("session-1")
            >>> if agent_type:
            ...     print(f"Current agent: {agent_type.value}")
        """
        agent = await self._repository.find_by_session_id(session_id)
        return agent.current_type if agent else None
    
    async def get_agent(self, session_id: str) -> Optional[Agent]:
        """
        Получить агента для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Agent или None если не найден
            
        Пример:
            >>> agent = await service.get_agent("session-1")
            >>> if agent:
            ...     print(f"Switches: {agent.switch_count}")
        """
        return await self._repository.find_by_session_id(session_id)
    
    async def get_switch_history(
        self,
        session_id: str
    ) -> list[AgentSwitchRecord]:
        """
        Получить историю переключений агента.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список записей о переключениях
            
        Пример:
            >>> history = await service.get_switch_history("session-1")
            >>> for record in history:
            ...     print(f"{record.from_agent} -> {record.to_agent}: {record.reason}")
        """
        agent = await self._repository.find_by_session_id(session_id)
        return agent.switch_history if agent else []
    
    async def get_agent_usage_stats(self) -> Dict[str, int]:
        """
        Получить статистику использования агентов.
        
        Returns:
            Словарь с количеством сессий для каждого типа агента
            
        Пример:
            >>> stats = await service.get_agent_usage_stats()
            >>> print(f"Coder используется в {stats['coder']} сессиях")
        """
        stats = {}
        
        for agent_type in AgentType:
            agents = await self._repository.find_by_agent_type(
                agent_type=agent_type,
                limit=10000  # Большой лимит для статистики
            )
            stats[agent_type.value] = len(agents)
        
        return stats
    
    async def get_problematic_sessions(
        self,
        min_switches: int = 5
    ) -> list[Agent]:
        """
        Получить сессии с большим количеством переключений.
        
        Полезно для выявления проблемных сессий или
        анализа паттернов использования.
        
        Args:
            min_switches: Минимальное количество переключений
            
        Returns:
            Список агентов с >= min_switches переключений
            
        Пример:
            >>> problematic = await service.get_problematic_sessions(min_switches=10)
            >>> for agent in problematic:
            ...     print(f"Session {agent.session_id}: {agent.switch_count} switches")
        """
        return await self._repository.find_with_many_switches(
            min_switches=min_switches,
            limit=100
        )
    
    async def can_switch_to(
        self,
        session_id: str,
        target_type: AgentType
    ) -> bool:
        """
        Проверить возможность переключения на указанный тип.
        
        Args:
            session_id: ID сессии
            target_type: Целевой тип агента
            
        Returns:
            True если переключение возможно
            
        Пример:
            >>> if await service.can_switch_to("session-1", AgentType.CODER):
            ...     await service.switch_agent("session-1", AgentType.CODER, "Need to code")
        """
        agent = await self._repository.find_by_session_id(session_id)
        
        if not agent:
            # Если агента нет, можно создать нового
            return True
        
        return agent.can_switch_to(target_type)
    
    async def get_capabilities(self, session_id: str) -> Optional[AgentCapabilities]:
        """
        Получить возможности агента для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            AgentCapabilities или None если агент не найден
            
        Пример:
            >>> capabilities = await service.get_capabilities("session-1")
            >>> if capabilities:
            ...     print(f"Max switches: {capabilities.max_switches}")
        """
        agent = await self._repository.find_by_session_id(session_id)
        return agent.capabilities if agent else None
    
    def _get_capabilities_for_type(self, agent_type: AgentType) -> AgentCapabilities:
        """
        Получить capabilities для указанного типа агента.
        
        Args:
            agent_type: Тип агента
            
        Returns:
            AgentCapabilities для указанного типа
            
        Пример:
            >>> caps = service._get_capabilities_for_type(AgentType.CODER)
            >>> caps.agent_type
            <AgentType.CODER: 'coder'>
        """
        # Маппинг типов на фабричные методы
        type_to_factory = {
            AgentType.ORCHESTRATOR: AgentCapabilities.for_orchestrator,
            AgentType.CODER: AgentCapabilities.for_coder,
            AgentType.ARCHITECT: AgentCapabilities.for_architect,
            AgentType.DEBUG: AgentCapabilities.for_debug,
            AgentType.ASK: AgentCapabilities.for_ask,
            AgentType.UNIVERSAL: AgentCapabilities.for_universal,
        }
        
        factory = type_to_factory.get(agent_type)
        if not factory:
            # Fallback: создать базовые capabilities
            return AgentCapabilities(
                agent_type=agent_type,
                supported_tools=set(),
                max_switches=50
            )
        
        return factory()

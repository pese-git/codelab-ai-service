"""
Доменный сервис оркестрации агентов.

Инкапсулирует бизнес-логику переключения и управления агентами.
"""

import uuid
import logging
from typing import Optional

from ..agent_context.entities.agent import Agent as AgentContext
from ..agent_context.value_objects.agent_capabilities import AgentType, AgentCapabilities
from ..agent_context.repositories.agent_repository import AgentRepository as AgentContextRepository
from ..events.agent_events import (
    AgentAssigned,
    AgentSwitchRequested,
    AgentSwitched,
    TaskStarted,
    TaskCompleted,
    TaskFailed
)
from ...core.errors import AgentSwitchError

logger = logging.getLogger("agent-runtime.domain.agent_orchestration")


class AgentOrchestrationService:
    """
    Доменный сервис для оркестрации агентов.
    
    Координирует переключение между агентами и публикует
    соответствующие доменные события.
    
    Атрибуты:
        _repository: Репозиторий контекстов агентов
        _event_publisher: Функция для публикации событий (опционально)
    
    Пример:
        >>> service = AgentOrchestrationService(repository)
        >>> context = await service.assign_agent(
        ...     session_id="session-1",
        ...     agent_type=AgentType.CODER
        ... )
    """
    
    def __init__(
        self,
        repository: AgentContextRepository,
        event_publisher=None
    ):
        """
        Инициализация сервиса.
        
        Args:
            repository: Репозиторий для работы с контекстами агентов
            event_publisher: Функция для публикации событий (опционально)
        """
        self._repository = repository
        self._event_publisher = event_publisher
    
    async def get_or_create_context(
        self,
        session_id: str,
        initial_agent: AgentType = AgentType.ORCHESTRATOR
    ) -> AgentContext:
        """
        Получить существующий контекст или создать новый.
        
        Args:
            session_id: ID сессии
            initial_agent: Начальный агент для новых контекстов
            
        Returns:
            Контекст агента
            
        Пример:
            >>> context = await service.get_or_create_context("session-1")
            >>> context.current_agent
            <AgentType.ORCHESTRATOR: 'orchestrator'>
        """
        # Попытаться найти существующий контекст
        context = await self._repository.find_by_session_id(session_id)
        
        if context:
            logger.debug(f"Найден существующий контекст для сессии {session_id}")
            return context
        
        # Создать новый контекст с capabilities для указанного типа агента
        capabilities = AgentCapabilities.for_agent_type(initial_agent)
        context = AgentContext(
            id=str(uuid.uuid4()),
            session_id=session_id,
            capabilities=capabilities
        )
        
        # Сохранить
        await self._repository.save(context)
        
        logger.info(
            f"Создан новый контекст агента для сессии {session_id} "
            f"с начальным агентом {initial_agent.value}"
        )
        
        # Опубликовать событие
        if self._event_publisher:
            await self._event_publisher(
                AgentAssigned(
                    aggregate_id=session_id,
                    session_id=session_id,
                    agent_type=initial_agent.value,
                    reason="Initial assignment"
                )
            )
        
        return context
    
    async def switch_agent(
        self,
        session_id: str,
        target_agent: AgentType,
        reason: str,
        confidence: Optional[str] = None
    ) -> AgentContext:
        """
        Переключить агента для сессии.
        
        Args:
            session_id: ID сессии
            target_agent: Целевой агент
            reason: Причина переключения
            confidence: Уверенность в переключении (опционально)
            
        Returns:
            Обновленный контекст агента
            
        Raises:
            AgentSwitchError: Если переключение невозможно
            
        Пример:
            >>> context = await service.switch_agent(
            ...     session_id="session-1",
            ...     target_agent=AgentType.CODER,
            ...     reason="Coding task detected",
            ...     confidence="high"
            ... )
        """
        # Получить контекст
        context = await self._repository.find_by_session_id(session_id)
        
        if not context:
            # Создать новый контекст с целевым агентом
            context = await self.get_or_create_context(
                session_id=session_id,
                initial_agent=target_agent
            )
            return context
        
        # Запомнить предыдущего агента
        from_agent = context.current_agent
        
        # Опубликовать событие запроса переключения
        if self._event_publisher:
            await self._event_publisher(
                AgentSwitchRequested(
                    aggregate_id=session_id,
                    session_id=session_id,
                    from_agent=from_agent.value,
                    to_agent=target_agent.value,
                    reason=reason,
                    requested_by="system"
                )
            )
        
        # Выполнить переключение (валидация внутри)
        try:
            switch = context.switch_to(
                target_agent=target_agent,
                reason=reason,
                confidence=confidence
            )
        except AgentSwitchError as e:
            logger.warning(f"Не удалось переключить агента: {e}")
            raise
        
        # Сохранить контекст
        await self._repository.save(context)
        
        logger.info(
            f"Агент переключен для сессии {session_id}: "
            f"{from_agent.value} -> {target_agent.value} "
            f"(причина: {reason})"
        )
        
        # Опубликовать событие успешного переключения
        if self._event_publisher:
            await self._event_publisher(
                AgentSwitched(
                    aggregate_id=session_id,
                    session_id=session_id,
                    from_agent=from_agent.value,
                    to_agent=target_agent.value,
                    reason=reason,
                    switch_count=context.switch_count
                )
            )
        
        return context
    
    async def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Получить текущего агента для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Тип текущего агента или None если контекст не найден
            
        Пример:
            >>> agent = await service.get_current_agent("session-1")
            >>> if agent:
            ...     print(f"Current agent: {agent.value}")
        """
        context = await self._repository.find_by_session_id(session_id)
        return context.current_agent if context else None
    
    async def get_agent_usage_stats(self) -> dict:
        """
        Получить статистику использования агентов.
        
        Returns:
            Словарь с количеством сессий для каждого агента
            
        Пример:
            >>> stats = await service.get_agent_usage_stats()
            >>> print(f"Coder используется в {stats['coder']} сессиях")
        """
        return await self._repository.get_agent_usage_stats()

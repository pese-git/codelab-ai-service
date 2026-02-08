"""
DI Module для Agent Context.

Предоставляет зависимости для работы с агентами.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agent_context.services import (
    AgentCoordinationService,
    AgentRouterService
)
from app.domain.agent_context.repositories import AgentRepository
from app.infrastructure.persistence.repositories import AgentRepositoryImpl
from app.domain.services import (
    AgentRegistry,
    AgentSwitcher
)

logger = logging.getLogger("agent-runtime.di.agent_module")


class AgentModule:
    """
    DI модуль для Agent Context.
    
    Предоставляет:
    - AgentRepository
    - AgentCoordinationService
    - AgentRouterService
    - AgentRegistry
    - AgentSwitcher
    """
    
    def __init__(self):
        """Инициализация модуля."""
        self._agent_repository: Optional[AgentRepository] = None
        self._coordination_service: Optional[AgentCoordinationService] = None
        self._router_service: Optional[AgentRouterService] = None
        self._agent_registry: Optional[AgentRegistry] = None
        self._agent_switcher: Optional[AgentSwitcher] = None
        
        logger.debug("AgentModule инициализирован")
    
    def provide_agent_repository(
        self,
        db: AsyncSession
    ) -> AgentRepository:
        """
        Предоставить репозиторий агентов.
        
        Args:
            db: Сессия БД
            
        Returns:
            AgentRepository: Реализация репозитория
        """
        return AgentRepositoryImpl(db)
    
    def provide_coordination_service(
        self,
        agent_repository: AgentRepository
    ) -> AgentCoordinationService:
        """
        Предоставить сервис координации агентов.
        
        Args:
            agent_repository: Репозиторий агентов
            
        Returns:
            AgentCoordinationService: Сервис координации
        """
        if self._coordination_service is None:
            self._coordination_service = AgentCoordinationService(
                repository=agent_repository
            )
        return self._coordination_service
    
    def provide_router_service(
        self,
        agent_registry: AgentRegistry
    ) -> AgentRouterService:
        """
        Предоставить сервис маршрутизации агентов.
        
        Args:
            agent_registry: Реестр агентов
            
        Returns:
            AgentRouterService: Сервис маршрутизации
        """
        if self._router_service is None:
            self._router_service = AgentRouterService(
                agent_registry=agent_registry
            )
        return self._router_service
    
    def provide_agent_registry(self) -> AgentRegistry:
        """
        Предоставить реестр агентов.
        
        Returns:
            AgentRegistry: Глобальный singleton реестр агентов
        """
        from app.domain.services.agent_registry import agent_registry
        return agent_registry
    
    def provide_agent_switcher(
        self,
        session_service,
        agent_coordination_service: AgentCoordinationService,
        event_publisher=None
    ) -> AgentSwitcher:
        """
        Предоставить сервис переключения агентов.
        
        Args:
            session_service: Сервис управления сессиями
            agent_coordination_service: Сервис координации агентов
            event_publisher: Publisher событий (опционально)
            
        Returns:
            AgentSwitcher: Сервис переключения
        """
        if self._agent_switcher is None:
            from app.domain.services.helpers.agent_switch_helper import AgentSwitchHelper
            
            switch_helper = AgentSwitchHelper(
                session_service=session_service,
                agent_service=agent_coordination_service
            )
            
            self._agent_switcher = AgentSwitcher(
                agent_service=agent_coordination_service,
                switch_helper=switch_helper
            )
        return self._agent_switcher
    

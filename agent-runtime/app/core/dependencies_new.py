"""
Dependency Injection провайдеры для новой архитектуры.

Этот модуль содержит провайдеры для инжекции зависимостей
в новые Command/Query handlers и роутеры.
"""

import logging
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.database import get_db
from ..infrastructure.persistence.repositories import (
    SessionRepositoryImpl,
    AgentContextRepositoryImpl
)
from ..infrastructure.adapters import EventPublisherAdapter
from ..domain.services import (
    SessionManagementService,
    AgentOrchestrationService
)
from ..application.commands import (
    CreateSessionHandler,
    AddMessageHandler,
    SwitchAgentHandler
)
from ..application.queries import (
    GetSessionHandler,
    ListSessionsHandler,
    GetAgentContextHandler
)

logger = logging.getLogger("agent-runtime.dependencies")


# ==================== Database Dependencies ====================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Получить сессию БД.
    
    Yields:
        AsyncSession: Сессия БД
    """
    async for session in get_db():
        yield session


# ==================== Repository Dependencies ====================

async def get_session_repository(
    db: AsyncSession = Depends(get_db_session)
) -> SessionRepositoryImpl:
    """
    Получить репозиторий сессий.
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        SessionRepositoryImpl: Реализация репозитория сессий
    """
    return SessionRepositoryImpl(db)


async def get_agent_context_repository(
    db: AsyncSession = Depends(get_db_session)
) -> AgentContextRepositoryImpl:
    """
    Получить репозиторий контекстов агентов.
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        AgentContextRepositoryImpl: Реализация репозитория контекстов
    """
    return AgentContextRepositoryImpl(db)


# ==================== Event Publisher Dependencies ====================

async def get_event_publisher() -> EventPublisherAdapter:
    """
    Получить адаптер для публикации событий.
    
    Returns:
        EventPublisherAdapter: Адаптер для публикации доменных событий
    """
    return EventPublisherAdapter()


# ==================== Domain Service Dependencies ====================

async def get_session_management_service(
    repository: SessionRepositoryImpl = Depends(get_session_repository),
    event_publisher: EventPublisherAdapter = Depends(get_event_publisher)
) -> SessionManagementService:
    """
    Получить доменный сервис управления сессиями.
    
    Args:
        repository: Репозиторий сессий (инжектируется)
        event_publisher: Адаптер для публикации событий (инжектируется)
        
    Returns:
        SessionManagementService: Доменный сервис
    """
    return SessionManagementService(
        repository=repository,
        event_publisher=event_publisher.publish
    )


async def get_agent_orchestration_service(
    repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository),
    event_publisher: EventPublisherAdapter = Depends(get_event_publisher)
) -> AgentOrchestrationService:
    """
    Получить доменный сервис оркестрации агентов.
    
    Args:
        repository: Репозиторий контекстов (инжектируется)
        event_publisher: Адаптер для публикации событий (инжектируется)
        
    Returns:
        AgentOrchestrationService: Доменный сервис
    """
    return AgentOrchestrationService(
        repository=repository,
        event_publisher=event_publisher.publish
    )


# ==================== Command Handler Dependencies ====================

async def get_create_session_handler(
    service: SessionManagementService = Depends(get_session_management_service)
) -> CreateSessionHandler:
    """
    Получить обработчик команды создания сессии.
    
    Args:
        service: Доменный сервис (инжектируется)
        
    Returns:
        CreateSessionHandler: Command handler
    """
    return CreateSessionHandler(service)


async def get_add_message_handler(
    service: SessionManagementService = Depends(get_session_management_service)
) -> AddMessageHandler:
    """
    Получить обработчик команды добавления сообщения.
    
    Args:
        service: Доменный сервис (инжектируется)
        
    Returns:
        AddMessageHandler: Command handler
    """
    return AddMessageHandler(service)


async def get_switch_agent_handler(
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service)
) -> SwitchAgentHandler:
    """
    Получить обработчик команды переключения агента.
    
    Args:
        service: Доменный сервис (инжектируется)
        
    Returns:
        SwitchAgentHandler: Command handler
    """
    return SwitchAgentHandler(service)


# ==================== Query Handler Dependencies ====================

async def get_get_session_handler(
    repository: SessionRepositoryImpl = Depends(get_session_repository)
) -> GetSessionHandler:
    """
    Получить обработчик запроса получения сессии.
    
    Args:
        repository: Репозиторий сессий (инжектируется)
        
    Returns:
        GetSessionHandler: Query handler
    """
    return GetSessionHandler(repository)


async def get_list_sessions_handler(
    session_repository: SessionRepositoryImpl = Depends(get_session_repository),
    context_repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository)
) -> ListSessionsHandler:
    """
    Получить обработчик запроса списка сессий.
    
    Args:
        session_repository: Репозиторий сессий (инжектируется)
        context_repository: Репозиторий контекстов (инжектируется)
        
    Returns:
        ListSessionsHandler: Query handler
    """
    return ListSessionsHandler(session_repository, context_repository)


async def get_get_agent_context_handler(
    repository: AgentContextRepositoryImpl = Depends(get_agent_context_repository)
) -> GetAgentContextHandler:
    """
    Получить обработчик запроса получения контекста агента.
    
    Args:
        repository: Репозиторий контекстов (инжектируется)
        
    Returns:
        GetAgentContextHandler: Query handler
    """
    return GetAgentContextHandler(repository)

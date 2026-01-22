"""
FastAPI dependencies для agent runtime service.

Provides dependency injection for:
- Database sessions and services
- Repositories
- Domain services
- Command and Query handlers
"""

import logging
from typing import Annotated, AsyncGenerator, Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db, get_database_service, DatabaseService
from app.infrastructure.persistence.repositories import (
    SessionRepositoryImpl,
    AgentContextRepositoryImpl
)
from app.infrastructure.adapters import EventPublisherAdapter
from app.domain.services import (
    SessionManagementService,
    AgentOrchestrationService
)
from app.application.commands import (
    CreateSessionHandler,
    AddMessageHandler,
    SwitchAgentHandler
)
from app.application.queries import (
    GetSessionHandler,
    ListSessionsHandler,
    GetAgentContextHandler
)

logger = logging.getLogger("agent-runtime.dependencies")

# ==================== Database Dependencies ====================

# Database session dependency (Annotated type)
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Database service dependency (Annotated type)
DBService = Annotated[DatabaseService, Depends(get_database_service)]


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

# Singleton instance of EventPublisherAdapter
_event_publisher_adapter: Optional[EventPublisherAdapter] = None


def get_event_publisher() -> EventPublisherAdapter:
    """
    Получить адаптер для публикации событий (singleton).
    
    Returns:
        EventPublisherAdapter: Адаптер для публикации доменных событий
    """
    global _event_publisher_adapter
    if _event_publisher_adapter is None:
        _event_publisher_adapter = EventPublisherAdapter()
    return _event_publisher_adapter


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


async def get_session_manager_adapter(
    session_service: SessionManagementService = Depends(get_session_management_service)
):
    """
    Получить адаптер для управления сессиями.
    
    Args:
        session_service: Сервис управления сессиями (инжектируется)
        
    Returns:
        SessionManagerAdapter: Адаптер для управления сессиями
    """
    from ..infrastructure.adapters import SessionManagerAdapter
    return SessionManagerAdapter(session_service)


async def get_agent_context_manager_adapter(
    agent_service: AgentOrchestrationService = Depends(get_agent_orchestration_service)
):
    """
    Получить адаптер для управления контекстом агентов.
    
    Args:
        agent_service: Сервис оркестрации агентов (инжектируется)
        
    Returns:
        AgentContextManagerAdapter: Адаптер для управления контекстом
    """
    from ..infrastructure.adapters import AgentContextManagerAdapter
    return AgentContextManagerAdapter(agent_service)


async def get_message_orchestration_service(
    session_service: SessionManagementService = Depends(get_session_management_service),
    agent_service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
    event_publisher: EventPublisherAdapter = Depends(get_event_publisher)
):
    """
    Получить доменный сервис оркестрации сообщений.
    
    Args:
        session_service: Сервис управления сессиями (инжектируется)
        agent_service: Сервис оркестрации агентов (инжектируется)
        event_publisher: Адаптер для публикации событий (инжектируется)
        
    Returns:
        MessageOrchestrationService: Доменный сервис
    """
    from ..domain.services import MessageOrchestrationService
    from ..domain.services.agent_registry import agent_router
    from ..infrastructure.concurrency import session_lock_manager
    
    return MessageOrchestrationService(
        session_service=session_service,
        agent_service=agent_service,
        agent_router=agent_router,
        lock_manager=session_lock_manager,
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

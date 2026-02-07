"""
FastAPI dependencies для agent runtime service.

Упрощенная версия с использованием модульного DI Container.
Размер: ~150 строк (вместо 893 строк в старой версии).
"""

import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db, get_database_service, DatabaseService
from app.core.di import get_container, DIContainer

# Use Cases
from app.application.use_cases import (
    ProcessMessageUseCase,
    SwitchAgentUseCase,
    ProcessToolResultUseCase,
    HandleApprovalUseCase
)

# Command and Query handlers
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

# Repositories
from app.infrastructure.persistence.repositories import (
    ConversationRepositoryImpl,
    AgentRepositoryImpl
)

logger = logging.getLogger("agent-runtime.dependencies")

# ==================== Database Dependencies ====================

# Database session dependency (Annotated type)
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Database service dependency (Annotated type)
DBService = Annotated[DatabaseService, Depends(get_database_service)]


async def get_db_session() -> AsyncSession:
    """
    Получить сессию БД.
    
    Yields:
        AsyncSession: Сессия БД
    """
    async for session in get_db():
        yield session


# ==================== DI Container ====================

def get_di_container() -> DIContainer:
    """
    Получить DI контейнер.
    
    Returns:
        DIContainer: Глобальный контейнер зависимостей
    """
    return get_container()


# ==================== Use Case Dependencies ====================

async def get_process_message_use_case(
    db: AsyncSession = Depends(get_db_session),
    container: DIContainer = Depends(get_di_container)
) -> ProcessMessageUseCase:
    """
    Получить Use Case для обработки сообщений.
    
    Args:
        db: Сессия БД (инжектируется)
        container: DI контейнер (инжектируется)
        
    Returns:
        ProcessMessageUseCase: Use Case
    """
    return container.get_process_message_use_case(db)


async def get_switch_agent_use_case(
    db: AsyncSession = Depends(get_db_session),
    container: DIContainer = Depends(get_di_container)
) -> SwitchAgentUseCase:
    """
    Получить Use Case для переключения агента.
    
    Args:
        db: Сессия БД (инжектируется)
        container: DI контейнер (инжектируется)
        
    Returns:
        SwitchAgentUseCase: Use Case
    """
    return container.get_switch_agent_use_case(db)


async def get_process_tool_result_use_case(
    db: AsyncSession = Depends(get_db_session),
    container: DIContainer = Depends(get_di_container)
) -> ProcessToolResultUseCase:
    """
    Получить Use Case для обработки результатов инструментов.
    
    Args:
        db: Сессия БД (инжектируется)
        container: DI контейнер (инжектируется)
        
    Returns:
        ProcessToolResultUseCase: Use Case
    """
    return container.get_process_tool_result_use_case(db)


async def get_handle_approval_use_case(
    db: AsyncSession = Depends(get_db_session),
    container: DIContainer = Depends(get_di_container)
) -> HandleApprovalUseCase:
    """
    Получить Use Case для обработки approval решений.
    
    Args:
        db: Сессия БД (инжектируется)
        container: DI контейнер (инжектируется)
        
    Returns:
        HandleApprovalUseCase: Use Case
    """
    return container.get_handle_approval_use_case(db)


# ==================== Repository Dependencies ====================

async def get_conversation_repository(
    db: AsyncSession = Depends(get_db_session)
) -> ConversationRepositoryImpl:
    """
    Получить репозиторий conversations.
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        ConversationRepositoryImpl: Реализация репозитория
    """
    return ConversationRepositoryImpl(db)


async def get_agent_repository(
    db: AsyncSession = Depends(get_db_session)
) -> AgentRepositoryImpl:
    """
    Получить репозиторий агентов.
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        AgentRepositoryImpl: Реализация репозитория
    """
    return AgentRepositoryImpl(db)


# ==================== Command Handler Dependencies ====================

async def get_create_session_handler(
    db: AsyncSession = Depends(get_db_session),
    container: DIContainer = Depends(get_di_container)
) -> CreateSessionHandler:
    """
    Получить обработчик команды создания сессии.
    
    Args:
        db: Сессия БД (инжектируется)
        container: DI контейнер (инжектируется)
        
    Returns:
        CreateSessionHandler: Command handler
    """
    conversation_repo = container.session_module.provide_conversation_repository(db)
    conversation_service = container.session_module.provide_conversation_service(conversation_repo)
    return CreateSessionHandler(conversation_service)


async def get_add_message_handler(
    db: AsyncSession = Depends(get_db_session),
    container: DIContainer = Depends(get_di_container)
) -> AddMessageHandler:
    """
    Получить обработчик команды добавления сообщения.
    
    Args:
        db: Сессия БД (инжектируется)
        container: DI контейнер (инжектируется)
        
    Returns:
        AddMessageHandler: Command handler
    """
    # Используем provide_session_service, который теперь возвращает ConversationManagementService
    conversation_service = container.session_module.provide_session_service(
        db=db,
        event_publisher=None
    )
    return AddMessageHandler(conversation_service)


async def get_switch_agent_handler(
    db: AsyncSession = Depends(get_db_session),
    container: DIContainer = Depends(get_di_container)
) -> SwitchAgentHandler:
    """
    Получить обработчик команды переключения агента.
    
    Args:
        db: Сессия БД (инжектируется)
        container: DI контейнер (инжектируется)
        
    Returns:
        SwitchAgentHandler: Command handler
    """
    agent_service = container.agent_module.provide_orchestration_service(db)
    return SwitchAgentHandler(agent_service)


# ==================== Query Handler Dependencies ====================

async def get_get_session_handler(
    repository: ConversationRepositoryImpl = Depends(get_conversation_repository)
) -> GetSessionHandler:
    """
    Получить обработчик запроса получения сессии.
    
    Args:
        repository: Репозиторий conversations (инжектируется)
        
    Returns:
        GetSessionHandler: Query handler
    """
    return GetSessionHandler(repository)


async def get_list_sessions_handler(
    session_repository: ConversationRepositoryImpl = Depends(get_conversation_repository),
    context_repository: AgentRepositoryImpl = Depends(get_agent_repository)
) -> ListSessionsHandler:
    """
    Получить обработчик запроса списка сессий.
    
    Args:
        session_repository: Репозиторий conversations (инжектируется)
        context_repository: Репозиторий агентов (инжектируется)
        
    Returns:
        ListSessionsHandler: Query handler
    """
    return ListSessionsHandler(session_repository, context_repository)


async def get_get_agent_context_handler(
    repository: AgentRepositoryImpl = Depends(get_agent_repository)
) -> GetAgentContextHandler:
    """
    Получить обработчик запроса получения контекста агента.
    
    Args:
        repository: Репозиторий агентов (инжектируется)
        
    Returns:
        GetAgentContextHandler: Query handler
    """
    return GetAgentContextHandler(repository)


logger.info("Dependencies модуль загружен (модульная версия с DIContainer)")

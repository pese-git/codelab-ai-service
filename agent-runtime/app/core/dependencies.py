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


async def get_plan_repository(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получить репозиторий планов.
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        PlanRepositoryImpl: Реализация репозитория планов
    """
    from ..infrastructure.persistence.repositories.plan_repository_impl import PlanRepositoryImpl
    return PlanRepositoryImpl(db)


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


# ==================== HITL Dependencies ====================

async def get_hitl_policy_service():
    """
    Получить HITL policy service.
    
    Returns:
        HITLPolicyService: Service для оценки HITL политик
    """
    from ..domain.services.hitl_policy import HITLPolicyService
    return HITLPolicyService()


# ==================== Unified Approval System Dependencies ====================

async def get_approval_repository(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получить approval repository.
    
    Args:
        db: Database session (инжектируется)
        
    Returns:
        ApprovalRepository: Repository implementation для approval requests
    """
    from ..infrastructure.persistence.repositories.approval_repository_impl import ApprovalRepositoryImpl
    return ApprovalRepositoryImpl(db)


async def get_approval_manager(
    repository = Depends(get_approval_repository),
    hitl_policy_service = Depends(get_hitl_policy_service)
):
    """
    Получить ApprovalManager instance.
    
    Args:
        repository: ApprovalRepository (инжектируется)
        hitl_policy_service: HITLPolicyService (инжектируется)
        
    Returns:
        ApprovalManager: Unified approval manager для всех типов запросов
    """
    from ..domain.services.approval_management import ApprovalManager
    from ..domain.entities.approval import ApprovalPolicy
    
    # Создать unified policy из HITL policy
    # TODO: В будущем можно расширить для поддержки других типов approval
    approval_policy = ApprovalPolicy.default()
    
    return ApprovalManager(
        approval_repository=repository,
        approval_policy=approval_policy
    )


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


# ==================== Agent Switch Helper ====================

async def get_agent_switch_helper(
    session_service: SessionManagementService = Depends(get_session_management_service),
    agent_service: AgentOrchestrationService = Depends(get_agent_orchestration_service)
):
    """
    Получить helper для переключения агентов.
    
    Args:
        session_service: Сервис управления сессиями (инжектируется)
        agent_service: Сервис оркестрации агентов (инжектируется)
        
    Returns:
        AgentSwitchHelper: Helper для переключения агентов
    """
    from ..domain.services.helpers import AgentSwitchHelper
    return AgentSwitchHelper(
        session_service=session_service,
        agent_service=agent_service
    )


# ==================== Message Processor ====================

async def get_message_processor(
    session_service: SessionManagementService = Depends(get_session_management_service),
    agent_service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
    switch_helper = Depends(get_agent_switch_helper),
    approval_manager = Depends(get_approval_manager)
):
    """
    Получить процессор сообщений.
    
    Args:
        session_service: Сервис управления сессиями (инжектируется)
        agent_service: Сервис оркестрации агентов (инжектируется)
        switch_helper: Helper для переключения агентов (инжектируется)
        approval_manager: Unified approval manager (инжектируется)
        
    Returns:
        MessageProcessor: Процессор сообщений
    """
    from ..domain.services import MessageProcessor
    from ..domain.interfaces.stream_handler import IStreamHandler
    from ..domain.services.agent_registry import agent_router
    from .dependencies_llm import (
        get_llm_client,
        get_llm_event_publisher,
        get_tool_registry,
        get_tool_filter_service,
        get_llm_response_processor
    )
    from ..application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
    
    # Создать stream handler с ApprovalManager
    stream_handler: IStreamHandler = StreamLLMResponseHandler(
        llm_client=get_llm_client(),
        tool_filter=get_tool_filter_service(get_tool_registry()),
        response_processor=get_llm_response_processor(),
        event_publisher=get_llm_event_publisher(),
        session_service=session_service,
        approval_manager=approval_manager
    )
    
    return MessageProcessor(
        session_service=session_service,
        agent_service=agent_service,
        agent_router=agent_router,
        stream_handler=stream_handler,
        switch_helper=switch_helper
    )


# ==================== Agent Switcher ====================

async def get_agent_switcher(
    agent_service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
    switch_helper = Depends(get_agent_switch_helper)
):
    """
    Получить switcher агентов.
    
    Args:
        agent_service: Сервис оркестрации агентов (инжектируется)
        switch_helper: Helper для переключения агентов (инжектируется)
        
    Returns:
        AgentSwitcher: Switcher агентов
    """
    from ..domain.services import AgentSwitcher
    return AgentSwitcher(
        agent_service=agent_service,
        switch_helper=switch_helper
    )


# ==================== Tool Result Handler ====================

async def get_tool_result_handler(
    session_service: SessionManagementService = Depends(get_session_management_service),
    agent_service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
    switch_helper = Depends(get_agent_switch_helper),
    approval_manager = Depends(get_approval_manager)
):
    """
    Получить handler результатов инструментов.
    
    Args:
        session_service: Сервис управления сессиями (инжектируется)
        agent_service: Сервис оркестрации агентов (инжектируется)
        switch_helper: Helper для переключения агентов (инжектируется)
        approval_manager: Unified approval manager (инжектируется)
        
    Returns:
        ToolResultHandler: Handler результатов инструментов
    """
    from ..domain.services import ToolResultHandler
    from ..domain.interfaces.stream_handler import IStreamHandler
    from ..domain.services.agent_registry import agent_router
    from .dependencies_llm import (
        get_llm_client,
        get_llm_event_publisher,
        get_tool_registry,
        get_tool_filter_service,
        get_llm_response_processor
    )
    from ..application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
    
    # Создать stream handler с ApprovalManager
    stream_handler: IStreamHandler = StreamLLMResponseHandler(
        llm_client=get_llm_client(),
        tool_filter=get_tool_filter_service(get_tool_registry()),
        response_processor=get_llm_response_processor(),
        event_publisher=get_llm_event_publisher(),
        session_service=session_service,
        approval_manager=approval_manager
    )
    
    return ToolResultHandler(
        session_service=session_service,
        agent_service=agent_service,
        agent_router=agent_router,
        stream_handler=stream_handler,
        switch_helper=switch_helper,
        approval_manager=approval_manager  # Передаем approval_manager для удаления pending approvals
    )


# ==================== HITL Decision Handler ====================

async def get_hitl_decision_handler(
    approval_manager = Depends(get_approval_manager),
    session_service: SessionManagementService = Depends(get_session_management_service),
    message_processor = Depends(get_message_processor)
):
    """
    Получить handler HITL решений.
    
    Args:
        approval_manager: Unified approval manager (инжектируется)
        session_service: Сервис управления сессиями (инжектируется)
        message_processor: Процессор сообщений (инжектируется)
        
    Returns:
        HITLDecisionHandler: Handler HITL решений
    """
    from ..domain.services import HITLDecisionHandler
    return HITLDecisionHandler(
        approval_manager=approval_manager,
        session_service=session_service,
        message_processor=message_processor
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


# ==================== Planning System Dependencies ====================

async def get_architect_agent_for_planning(
    plan_repository = Depends(get_plan_repository)
):
    """
    Получить ArchitectAgent для создания планов.
    
    Args:
        plan_repository: Репозиторий планов (инжектируется)
        
    Returns:
        ArchitectAgent: Agent для создания планов
    """
    from ..agents.architect_agent import ArchitectAgent
    return ArchitectAgent(plan_repository=plan_repository)


async def get_execution_engine(
    plan_repository = Depends(get_plan_repository)
):
    """
    Получить ExecutionEngine для выполнения планов.
    
    Args:
        plan_repository: Репозиторий планов (инжектируется)
        
    Returns:
        ExecutionEngine: Engine для выполнения планов
    """
    from ..domain.services.execution_engine import ExecutionEngine
    from ..domain.services.subtask_executor import SubtaskExecutor
    from ..domain.services.dependency_resolver import DependencyResolver
    
    # Создать зависимости для ExecutionEngine
    subtask_executor = SubtaskExecutor(
        plan_repository=plan_repository,
        max_retries=3
    )
    
    dependency_resolver = DependencyResolver()
    
    return ExecutionEngine(
        plan_repository=plan_repository,
        subtask_executor=subtask_executor,
        dependency_resolver=dependency_resolver,
        max_parallel_tasks=1  # Временно 1 для избежания race condition
    )


async def get_execution_coordinator(
    execution_engine = Depends(get_execution_engine),
    plan_repository = Depends(get_plan_repository)
):
    """
    Получить ExecutionCoordinator для координации выполнения планов.
    
    Args:
        execution_engine: ExecutionEngine (инжектируется)
        plan_repository: Репозиторий планов (инжектируется)
        
    Returns:
        ExecutionCoordinator: Coordinator для выполнения планов
    """
    from ..application.coordinators.execution_coordinator import ExecutionCoordinator
    
    return ExecutionCoordinator(
        execution_engine=execution_engine,
        plan_repository=plan_repository
    )


async def ensure_orchestrator_option2_initialized(
    architect_agent = Depends(get_architect_agent_for_planning),
    execution_coordinator = Depends(get_execution_coordinator)
):
    """
    Ensure OrchestratorAgent has Option 2 dependencies initialized.
    
    This function injects planning capabilities into OrchestratorAgent
    on each request. If already initialized, it's a no-op.
    
    Args:
        architect_agent: ArchitectAgent (инжектируется)
        execution_coordinator: ExecutionCoordinator (инжектируется)
    """
    from ..domain.services.agent_registry import agent_router
    from ..agents.base_agent import AgentType
    
    try:
        # Get OrchestratorAgent from router using correct method
        orchestrator = agent_router.get_agent(AgentType.ORCHESTRATOR)
        
        # Check if already initialized
        if orchestrator.architect_agent is not None:
            return
        
        logger.info("Initializing OrchestratorAgent Option 2 dependencies...")
        
        # Inject dependencies into OrchestratorAgent
        orchestrator.set_planning_dependencies(
            architect_agent=architect_agent,
            execution_coordinator=execution_coordinator
        )
        
        logger.info("✓ OrchestratorAgent Option 2 dependencies initialized successfully")
        
    except ValueError as e:
        # Agent not found
        logger.warning(f"OrchestratorAgent not found in agent router: {e}")
    except Exception as e:
        logger.error(
            f"Failed to initialize OrchestratorAgent Option 2 dependencies: {e}",
            exc_info=True
        )
        logger.warning("Plan creation will not be available")


async def get_plan_approval_handler(
    approval_manager = Depends(get_approval_manager),
    session_service: SessionManagementService = Depends(get_session_management_service),
    execution_coordinator = Depends(get_execution_coordinator)
):
    """
    Получить handler Plan Approval решений.
    
    Args:
        approval_manager: Unified approval manager (инжектируется)
        session_service: Сервис управления сессиями (инжектируется)
        execution_coordinator: Execution coordinator (инжектируется)
        
    Returns:
        PlanApprovalHandler: Handler Plan Approval решений
    """
    from ..domain.services import PlanApprovalHandler
    from ..domain.services.fsm_orchestrator import FSMOrchestrator
    
    # FSM Orchestrator - singleton для всех сессий
    fsm_orchestrator = FSMOrchestrator()
    
    return PlanApprovalHandler(
        approval_manager=approval_manager,
        session_service=session_service,
        fsm_orchestrator=fsm_orchestrator,
        execution_coordinator=execution_coordinator
    )


async def get_message_orchestration_service(
    message_processor = Depends(get_message_processor),
    agent_switcher = Depends(get_agent_switcher),
    tool_result_handler = Depends(get_tool_result_handler),
    hitl_handler = Depends(get_hitl_decision_handler),
    plan_approval_handler = Depends(get_plan_approval_handler),
    _option2_init = Depends(ensure_orchestrator_option2_initialized)
):
    """
    Получить доменный сервис оркестрации сообщений (фасад).
    
    Args:
        message_processor: Процессор сообщений (инжектируется)
        agent_switcher: Switcher агентов (инжектируется)
        tool_result_handler: Handler результатов инструментов (инжектируется)
        hitl_handler: Handler HITL решений (инжектируется)
        plan_approval_handler: Handler Plan Approval решений (инжектируется)
        _option2_init: Инициализация Option 2 зависимостей (инжектируется, выполняется один раз)
        
    Returns:
        MessageOrchestrationService: Доменный сервис (фасад)
    """
    from ..domain.services import MessageOrchestrationService
    from ..infrastructure.concurrency import session_lock_manager
    
    # Note: _option2_init dependency ensures OrchestratorAgent has planning capabilities
    # before processing any messages. This runs once on first request.
    
    return MessageOrchestrationService(
        message_processor=message_processor,
        agent_switcher=agent_switcher,
        tool_result_handler=tool_result_handler,
        hitl_handler=hitl_handler,
        lock_manager=session_lock_manager,
        plan_approval_handler=plan_approval_handler
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

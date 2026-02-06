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
    ConversationRepositoryImpl,
    AgentRepositoryImpl
)
from app.infrastructure.persistence.repositories.execution_plan_repository_impl import ExecutionPlanRepositoryImpl
from app.infrastructure.adapters import EventPublisherAdapter
from app.domain.services import (
    SessionManagementService,
    AgentOrchestrationService
)
# Новые сервисы и адаптеры (Фаза 10)
from app.domain.session_context.services.conversation_management_service import (
    ConversationManagementService
)
from app.domain.agent_context.services.agent_coordination_service import (
    AgentCoordinationService
)
from app.domain.adapters.conversation_service_adapter import ConversationServiceAdapter
from app.domain.adapters.agent_orchestration_adapter import AgentOrchestrationAdapter
from app.domain.adapters.execution_engine_adapter import ExecutionEngineAdapter
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

async def get_conversation_repository(
    db: AsyncSession = Depends(get_db_session)
) -> ConversationRepositoryImpl:
    """
    Получить репозиторий разговоров (новая Clean Architecture).
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        ConversationRepositoryImpl: Реализация репозитория разговоров
    """
    return ConversationRepositoryImpl(db)


async def get_agent_repository(
    db: AsyncSession = Depends(get_db_session)
) -> AgentRepositoryImpl:
    """
    Получить репозиторий агентов (новая Clean Architecture).
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        AgentRepositoryImpl: Реализация репозитория агентов
    """
    return AgentRepositoryImpl(db)


async def get_execution_plan_repository(
    db: AsyncSession = Depends(get_db_session)
) -> ExecutionPlanRepositoryImpl:
    """
    Получить репозиторий планов выполнения (новая Clean Architecture).
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        ExecutionPlanRepositoryImpl: Реализация репозитория планов
    """
    return ExecutionPlanRepositoryImpl(db)


async def get_fsm_state_repository(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получить репозиторий FSM states.
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        FSMStateRepositoryImpl: Реализация репозитория FSM states
    """
    from ..infrastructure.persistence.repositories.fsm_state_repository_impl import FSMStateRepositoryImpl
    return FSMStateRepositoryImpl(db)


async def get_fsm_orchestrator(
    fsm_repository = Depends(get_fsm_state_repository)
):
    """
    Получить FSM Orchestrator с repository.
    
    Args:
        fsm_repository: FSM state repository (инжектируется)
        
    Returns:
        FSMOrchestrator: FSM orchestrator с персистентным хранилищем
    """
    from ..domain.services.fsm_orchestrator import FSMOrchestrator
    return FSMOrchestrator(repository=fsm_repository)


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

# Новые сервисы (Фаза 10)

async def get_conversation_management_service(
    repository: ConversationRepositoryImpl = Depends(get_conversation_repository),
    event_publisher: EventPublisherAdapter = Depends(get_event_publisher)
) -> ConversationManagementService:
    """
    Получить новый сервис управления разговорами (Фаза 10).
    
    Args:
        repository: Репозиторий разговоров (инжектируется)
        event_publisher: Адаптер для публикации событий (инжектируется)
        
    Returns:
        ConversationManagementService: Новый доменный сервис
    """
    return ConversationManagementService(
        repository=repository,
        event_publisher=event_publisher.publish
    )


async def get_agent_coordination_service(
    repository: AgentRepositoryImpl = Depends(get_agent_repository),
    event_publisher: EventPublisherAdapter = Depends(get_event_publisher)
) -> AgentCoordinationService:
    """
    Получить новый сервис координации агентов (Фаза 10).
    
    Args:
        repository: Репозиторий агентов (инжектируется)
        event_publisher: Адаптер для публикации событий (инжектируется)
        
    Returns:
        AgentCoordinationService: Новый доменный сервис
    """
    return AgentCoordinationService(
        repository=repository,
        event_publisher=event_publisher.publish
    )


# Legacy сервисы через адаптеры (Фаза 10.1.4)

async def get_session_management_service(
    conversation_service: ConversationManagementService = Depends(get_conversation_management_service)
) -> SessionManagementService:
    """
    Получить доменный сервис управления сессиями (через адаптер).
    
    ВАЖНО: Теперь возвращает ConversationServiceAdapter, который предоставляет
    старый API SessionManagementService, но использует новый ConversationManagementService.
    
    Это часть Фазы 10.1.4 - постепенная миграция на новую архитектуру.
    
    Args:
        conversation_service: Новый сервис разговоров (инжектируется)
        
    Returns:
        SessionManagementService: Адаптер с legacy API
    """
    return ConversationServiceAdapter(conversation_service)


async def get_agent_orchestration_service(
    coordination_service: AgentCoordinationService = Depends(get_agent_coordination_service)
) -> AgentOrchestrationService:
    """
    Получить доменный сервис оркестрации агентов (через адаптер).
    
    ВАЖНО: Теперь возвращает AgentOrchestrationAdapter, который предоставляет
    старый API AgentOrchestrationService, но использует новый AgentCoordinationService.
    
    Это часть Фазы 10.1.4 - постепенная миграция на новую архитектуру.
    
    Args:
        coordination_service: Новый сервис координации (инжектируется)
        
    Returns:
        AgentOrchestrationService: Адаптер с legacy API
    """
    return AgentOrchestrationAdapter(coordination_service)


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
    approval_manager = Depends(get_approval_manager),
    plan_repository = Depends(get_execution_plan_repository)
):
    """
    Получить handler результатов инструментов.
    
    Args:
        session_service: Сервис управления сессиями (инжектируется)
        agent_service: Сервис оркестрации агентов (инжектируется)
        switch_helper: Helper для переключения агентов (инжектируется)
        approval_manager: Unified approval manager (инжектируется)
        plan_repository: Plan repository для проверки активных планов (инжектируется)
        
    Returns:
        ToolResultHandler: Handler результатов инструментов с resumable execution
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
        approval_manager=approval_manager,  # Передаем approval_manager для удаления pending approvals
        plan_repository=plan_repository  # ✅ НОВОЕ: Для проверки активных планов (resumable execution)
    )


# ==================== HITL Decision Handler ====================

async def get_hitl_decision_handler(
    approval_manager = Depends(get_approval_manager),
    session_service: SessionManagementService = Depends(get_session_management_service),
    message_processor = Depends(get_message_processor),
    tool_result_handler = Depends(get_tool_result_handler)
):
    """
    Получить handler HITL решений.
    
    Args:
        approval_manager: Unified approval manager (инжектируется)
        session_service: Сервис управления сессиями (инжектируется)
        message_processor: Процессор сообщений (инжектируется)
        tool_result_handler: Handler результатов инструментов (инжектируется)
        
    Returns:
        HITLDecisionHandler: Handler HITL решений
    """
    from ..domain.services import HITLDecisionHandler
    return HITLDecisionHandler(
        approval_manager=approval_manager,
        session_service=session_service,
        message_processor=message_processor,
        tool_result_handler=tool_result_handler
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
    plan_repository = Depends(get_execution_plan_repository)
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


async def get_execution_plan_repository(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получить типобезопасный ExecutionPlanRepository.
    
    Фаза 10.3: Новый репозиторий для работы с ExecutionPlan entities.
    
    Args:
        db: Сессия БД (инжектируется)
        
    Returns:
        ExecutionPlanRepositoryImpl: Типобезопасный репозиторий планов
    """
    from ..infrastructure.persistence.repositories.execution_plan_repository_impl import (
        ExecutionPlanRepositoryImpl
    )
    return ExecutionPlanRepositoryImpl(db)


async def get_execution_engine(
    execution_plan_repository = Depends(get_execution_plan_repository),
    approval_manager = Depends(get_approval_manager)
):
    """
    Получить ExecutionEngineAdapter для выполнения планов.
    
    Фаза 10.3: Обновлено для использования ExecutionEngineAdapter,
    который делегирует вызовы в PlanExecutionService из новой DDD-архитектуры.
    
    Args:
        execution_plan_repository: Типобезопасный репозиторий планов (инжектируется)
        approval_manager: Approval manager для HITL (инжектируется)
        
    Returns:
        ExecutionEngineAdapter: Адаптер для выполнения планов
    """
    from ..domain.execution_context.services.plan_execution_service import PlanExecutionService
    from ..domain.execution_context.services.subtask_executor import SubtaskExecutor
    from ..domain.execution_context.services.dependency_resolver import DependencyResolver
    
    # Создать зависимости для PlanExecutionService
    subtask_executor = SubtaskExecutor(
        plan_repository=execution_plan_repository,
        max_retries=3
    )
    
    dependency_resolver = DependencyResolver()
    
    # Создать PlanExecutionService с типобезопасным репозиторием
    plan_execution_service = PlanExecutionService(
        plan_repository=execution_plan_repository,
        subtask_executor=subtask_executor,
        dependency_resolver=dependency_resolver
    )
    
    # Вернуть адаптер для обратной совместимости
    return ExecutionEngineAdapter(plan_execution_service)


async def get_execution_coordinator(
    execution_engine = Depends(get_execution_engine),
    plan_repository = Depends(get_execution_plan_repository)
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
    execution_coordinator = Depends(get_execution_coordinator),
    approval_manager = Depends(get_approval_manager),
    fsm_orchestrator = Depends(get_fsm_orchestrator)
):
    """
    Ensure OrchestratorAgent has Option 2 dependencies initialized.
    
    This function injects planning capabilities into OrchestratorAgent
    on each request. If already initialized, it's a no-op.
    
    Args:
        architect_agent: ArchitectAgent (инжектируется)
        execution_coordinator: ExecutionCoordinator (инжектируется)
        approval_manager: ApprovalManager (инжектируется)
        fsm_orchestrator: FSMOrchestrator (инжектируется)
    """
    from ..domain.services.agent_registry import agent_router
    from ..agents.base_agent import AgentType
    
    try:
        # Get OrchestratorAgent from router using correct method
        orchestrator = agent_router.get_agent(AgentType.ORCHESTRATOR)
        
        # Always update FSM orchestrator to use the one with repository
        orchestrator.fsm_orchestrator = fsm_orchestrator
        
        # Check if already initialized
        if orchestrator.architect_agent is not None:
            return
        
        logger.info("Initializing OrchestratorAgent Option 2 dependencies...")
        
        # Inject dependencies into OrchestratorAgent
        orchestrator.set_planning_dependencies(
            architect_agent=architect_agent,
            execution_coordinator=execution_coordinator,
            approval_manager=approval_manager
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
    execution_coordinator = Depends(get_execution_coordinator),
    fsm_orchestrator = Depends(get_fsm_orchestrator),
    plan_repository = Depends(get_execution_plan_repository)
):
    """
    Получить handler Plan Approval решений.
    
    Args:
        approval_manager: Unified approval manager (инжектируется)
        session_service: Сервис управления сессиями (инжектируется)
        execution_coordinator: Execution coordinator (инжектируется)
        fsm_orchestrator: FSM orchestrator (инжектируется)
        plan_repository: Plan repository (инжектируется)
        
    Returns:
        PlanApprovalHandler: Handler Plan Approval решений
    """
    from ..domain.services import PlanApprovalHandler
    from ..domain.interfaces.stream_handler import IStreamHandler
    from .dependencies_llm import (
        get_llm_client,
        get_llm_event_publisher,
        get_tool_registry,
        get_tool_filter_service,
        get_llm_response_processor
    )
    from ..application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
    
    # Создать stream handler для выполнения подзадач
    stream_handler: IStreamHandler = StreamLLMResponseHandler(
        llm_client=get_llm_client(),
        tool_filter=get_tool_filter_service(get_tool_registry()),
        response_processor=get_llm_response_processor(),
        event_publisher=get_llm_event_publisher(),
        session_service=session_service,
        approval_manager=approval_manager
    )
    
    return PlanApprovalHandler(
        approval_manager=approval_manager,
        session_service=session_service,
        fsm_orchestrator=fsm_orchestrator,
        execution_coordinator=execution_coordinator,
        plan_repository=plan_repository,
        stream_handler=stream_handler
    )


async def get_message_orchestration_service(
    message_processor = Depends(get_message_processor),
    agent_switcher = Depends(get_agent_switcher),
    tool_result_handler = Depends(get_tool_result_handler),
    hitl_handler = Depends(get_hitl_decision_handler),
    plan_approval_handler = Depends(get_plan_approval_handler),
    plan_repository = Depends(get_execution_plan_repository),
    execution_coordinator = Depends(get_execution_coordinator),
    session_service = Depends(get_session_management_service),
    approval_manager = Depends(get_approval_manager),
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
        plan_repository: Repository планов для resumable execution (инжектируется)
        execution_coordinator: Coordinator для resumable execution (инжектируется)
        session_service: Session service для execution (инжектируется)
        approval_manager: Approval manager для stream handler (инжектируется)
        _option2_init: Инициализация Option 2 зависимостей (инжектируется, выполняется один раз)
        
    Returns:
        MessageOrchestrationService: Доменный сервис (фасад) с resumable execution
    """
    from ..domain.services import MessageOrchestrationService
    from ..infrastructure.concurrency import session_lock_manager
    from ..domain.interfaces.stream_handler import IStreamHandler
    from .dependencies_llm import (
        get_llm_client,
        get_llm_event_publisher,
        get_tool_registry,
        get_tool_filter_service,
        get_llm_response_processor
    )
    from ..application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
    
    # Note: _option2_init dependency ensures OrchestratorAgent has planning capabilities
    # before processing any messages. This runs once on first request.
    
    # Создать stream handler для resumable execution
    stream_handler: IStreamHandler = StreamLLMResponseHandler(
        llm_client=get_llm_client(),
        tool_filter=get_tool_filter_service(get_tool_registry()),
        response_processor=get_llm_response_processor(),
        event_publisher=get_llm_event_publisher(),
        session_service=session_service,
        approval_manager=approval_manager
    )
    
    return MessageOrchestrationService(
        message_processor=message_processor,
        agent_switcher=agent_switcher,
        tool_result_handler=tool_result_handler,
        hitl_handler=hitl_handler,
        lock_manager=session_lock_manager,
        plan_approval_handler=plan_approval_handler,
        plan_repository=plan_repository,  # ✅ НОВОЕ: Для resumable execution
        execution_coordinator=execution_coordinator,  # ✅ НОВОЕ: Для resumable execution
        session_service=session_service,  # ✅ НОВОЕ: Для execution
        stream_handler=stream_handler  # ✅ НОВОЕ: Для execution
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
    repository: ConversationRepositoryImpl = Depends(get_conversation_repository)
) -> GetSessionHandler:
    """
    Получить обработчик запроса получения сессии.
    
    Args:
        repository: Репозиторий разговоров (инжектируется)
        
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
        session_repository: Репозиторий разговоров (инжектируется)
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
        repository: Репозиторий контекстов (инжектируется)
        
    Returns:
        GetAgentContextHandler: Query handler
    """
    return GetAgentContextHandler(repository)

"""
Центральный DI Container для Agent Runtime.

Координирует все DI модули и предоставляет единую точку доступа к зависимостям.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .session_module import SessionModule
from .agent_module import AgentModule
from .execution_module import ExecutionModule
from .infrastructure_module import InfrastructureModule

from app.application.use_cases import (
    ProcessMessageUseCase,
    SwitchAgentUseCase,
    ProcessToolResultUseCase,
    HandleApprovalUseCase
)
from app.domain.services import (
    MessageProcessor,
    ToolResultHandler,
    HITLDecisionHandler,
    PlanApprovalHandler
)
from app.infrastructure.concurrency.session_lock import SessionLockManager

logger = logging.getLogger("agent-runtime.di.container")


class DIContainer:
    """
    Центральный DI Container.
    
    Координирует все DI модули и предоставляет Use Cases.
    """
    
    def __init__(self):
        """Инициализация контейнера."""
        self.session_module = SessionModule()
        self.agent_module = AgentModule()
        self.execution_module = ExecutionModule()
        self.infrastructure_module = InfrastructureModule()
        self._lock_manager: Optional[SessionLockManager] = None
        logger.info("DIContainer инициализирован")
    
    # ==================== Use Cases ====================
    
    def get_process_message_use_case(self, db: AsyncSession) -> ProcessMessageUseCase:
        """Получить Use Case для обработки сообщений."""
        return ProcessMessageUseCase(
            message_processor=self._create_message_processor(db),
            lock_manager=self._get_lock_manager()
        )
    
    def get_switch_agent_use_case(self, db: AsyncSession) -> SwitchAgentUseCase:
        """Получить Use Case для переключения агента."""
        return SwitchAgentUseCase(
            agent_switcher=self._create_agent_switcher(db),
            lock_manager=self._get_lock_manager()
        )
    
    def get_process_tool_result_use_case(self, db: AsyncSession) -> ProcessToolResultUseCase:
        """Получить Use Case для обработки результатов инструментов."""
        return ProcessToolResultUseCase(
            tool_result_handler=self._create_tool_result_handler(db),
            lock_manager=self._get_lock_manager()
        )
    
    def get_handle_approval_use_case(self, db: AsyncSession) -> HandleApprovalUseCase:
        """Получить Use Case для обработки approval решений."""
        return HandleApprovalUseCase(
            hitl_handler=self._create_hitl_handler(db),
            plan_approval_handler=self._create_plan_approval_handler(db),
            lock_manager=self._get_lock_manager()
        )
    
    # ==================== Private Helpers ====================
    
    def _get_session_service(self, db: AsyncSession):
        """Получить session service."""
        return self.session_module.provide_session_service(
            db=db,
            event_publisher=self.infrastructure_module.provide_event_publisher()
        )
    
    def _get_agent_coordination_service(self, db: AsyncSession):
        """Получить agent coordination service."""
        agent_repository = self.agent_module.provide_agent_repository(db)
        return self.agent_module.provide_coordination_service(agent_repository)
    
    def _create_stream_handler(self, db: AsyncSession, session_service, llm_client):
        """Создать StreamLLMResponseHandler."""
        from app.application.handlers import StreamLLMResponseHandler
        from app.domain.services.tool_filter_service import ToolFilterService
        from app.domain.services.llm_response_processor import LLMResponseProcessor
        from app.domain.services.hitl_policy import HITLPolicyService
        from app.domain.services.approval_management import ApprovalManager
        from app.domain.services.tool_registry import ToolRegistry
        from app.infrastructure.persistence.repositories.approval_repository_impl import ApprovalRepositoryImpl
        
        tool_registry = ToolRegistry()
        tool_filter = ToolFilterService(tool_registry=tool_registry)
        hitl_policy = HITLPolicyService()
        response_processor = LLMResponseProcessor(hitl_policy=hitl_policy)
        approval_repository = ApprovalRepositoryImpl(db)
        approval_manager = ApprovalManager(
            approval_repository=approval_repository,
            approval_policy=None
        )
        
        # Используем LLMEventPublisher вместо EventPublisherAdapter
        llm_event_publisher = self.infrastructure_module.provide_llm_event_publisher()
        
        return StreamLLMResponseHandler(
            llm_client=llm_client,
            tool_filter=tool_filter,
            response_processor=response_processor,
            event_publisher=llm_event_publisher,
            session_service=session_service,
            approval_manager=approval_manager,
            db=db  # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: передаем db для commit'ов
        )
    
    def _create_switch_helper(self, db: AsyncSession):
        """Создать AgentSwitchHelper."""
        from app.domain.services.helpers.agent_switch_helper import AgentSwitchHelper
        return AgentSwitchHelper(
            session_service=self._get_session_service(db),
            agent_service=self._get_agent_coordination_service(db)
        )
    
    def _create_message_processor(self, db: AsyncSession) -> MessageProcessor:
        """Создать MessageProcessor."""
        session_service = self._get_session_service(db)
        agent_coordination_service = self._get_agent_coordination_service(db)
        agent_registry = self.agent_module.provide_agent_registry()
        llm_client = self.infrastructure_module.provide_llm_client()
        stream_handler = self._create_stream_handler(db, session_service, llm_client)
        switch_helper = self._create_switch_helper(db)
        
        return MessageProcessor(
            session_service=session_service,
            agent_service=agent_coordination_service,
            agent_router=agent_registry,
            stream_handler=stream_handler,
            switch_helper=switch_helper,
            db=db  # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: передаем db для commit'ов
        )
    
    def _create_agent_switcher(self, db: AsyncSession):
        """Создать AgentSwitcher."""
        return self.agent_module.provide_agent_switcher(
            session_service=self._get_session_service(db),
            agent_coordination_service=self._get_agent_coordination_service(db),
            event_publisher=self.infrastructure_module.provide_event_publisher()
        )
    
    def _create_tool_result_handler(self, db: AsyncSession) -> ToolResultHandler:
        """Создать ToolResultHandler."""
        session_service = self._get_session_service(db)
        agent_coordination_service = self._get_agent_coordination_service(db)
        agent_registry = self.agent_module.provide_agent_registry()
        llm_client = self.infrastructure_module.provide_llm_client()
        stream_handler = self._create_stream_handler(db, session_service, llm_client)
        switch_helper = self._create_switch_helper(db)
        
        return ToolResultHandler(
            session_service=session_service,
            agent_service=agent_coordination_service,
            agent_router=agent_registry,
            stream_handler=stream_handler,
            switch_helper=switch_helper
        )
    
    def _create_hitl_handler(self, db: AsyncSession) -> HITLDecisionHandler:
        """Создать HITLDecisionHandler."""
        from app.domain.services.approval_management import ApprovalManager
        from app.infrastructure.persistence.repositories.approval_repository_impl import ApprovalRepositoryImpl
        
        session_service = self._get_session_service(db)
        approval_repository = ApprovalRepositoryImpl(db)
        approval_manager = ApprovalManager(
            approval_repository=approval_repository,
            approval_policy=None
        )
        message_processor = self._create_message_processor(db)
        tool_result_handler = self._create_tool_result_handler(db)
        
        return HITLDecisionHandler(
            approval_manager=approval_manager,
            session_service=session_service,
            message_processor=message_processor,
            tool_result_handler=tool_result_handler
        )
    
    def _create_plan_approval_handler(self, db: AsyncSession) -> PlanApprovalHandler:
        """Создать PlanApprovalHandler."""
        from app.application.coordinators.execution_coordinator import ExecutionCoordinator
        from app.domain.services.approval_management import ApprovalManager
        from app.domain.services.fsm_orchestrator import FSMOrchestrator
        from app.infrastructure.persistence.repositories.approval_repository_impl import ApprovalRepositoryImpl
        from app.infrastructure.persistence.repositories.execution_plan_repository_impl import ExecutionPlanRepositoryImpl
        
        session_service = self._get_session_service(db)
        agent_registry = self.agent_module.provide_agent_registry()
        
        # Создать зависимости для PlanExecutionService
        plan_repository = ExecutionPlanRepositoryImpl(db)
        subtask_executor = self.execution_module.provide_subtask_executor(
            agent_registry=agent_registry,
            session_service=session_service
        )
        dependency_resolver = self.execution_module.provide_dependency_resolver()
        
        # Создать PlanExecutionService
        plan_execution_service = self.execution_module.provide_execution_service(
            plan_repository=plan_repository,
            subtask_executor=subtask_executor,
            dependency_resolver=dependency_resolver
        )
        
        # Создать ExecutionCoordinator с PlanExecutionService
        execution_coordinator = ExecutionCoordinator(
            plan_execution_service=plan_execution_service,
            plan_repository=plan_repository
        )
        
        approval_repository = ApprovalRepositoryImpl(db)
        approval_manager = ApprovalManager(
            approval_repository=approval_repository,
            approval_policy=None
        )
        
        fsm_orchestrator = FSMOrchestrator()
        llm_client = self.infrastructure_module.provide_llm_client()
        stream_handler = self._create_stream_handler(db, session_service, llm_client)
        
        return PlanApprovalHandler(
            approval_manager=approval_manager,
            session_service=session_service,
            fsm_orchestrator=fsm_orchestrator,
            execution_coordinator=execution_coordinator,
            plan_repository=plan_repository,
            stream_handler=stream_handler
        )
    
    def _get_lock_manager(self) -> SessionLockManager:
        """Получить SessionLockManager (singleton)."""
        if self._lock_manager is None:
            self._lock_manager = SessionLockManager()
        return self._lock_manager


# Глобальный экземпляр контейнера
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """
    Получить глобальный экземпляр DI контейнера.
    
    Returns:
        DIContainer: Глобальный контейнер
    """
    global _container
    if _container is None:
        _container = DIContainer()
    return _container

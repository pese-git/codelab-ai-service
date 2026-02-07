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
    
    Координирует все DI модули:
    - SessionModule - для Session Context
    - AgentModule - для Agent Context
    - ExecutionModule - для Execution Context
    - InfrastructureModule - для Infrastructure Layer
    
    Предоставляет Use Cases и Domain Services.
    
    Пример:
        >>> container = DIContainer()
        >>> use_case = container.get_process_message_use_case(db)
        >>> async for chunk in use_case.execute(request):
        ...     print(chunk)
    """
    
    def __init__(self):
        """Инициализация контейнера."""
        # Инициализация модулей
        self.session_module = SessionModule()
        self.agent_module = AgentModule()
        self.execution_module = ExecutionModule()
        self.infrastructure_module = InfrastructureModule()
        
        # Singleton компоненты
        self._lock_manager: Optional[SessionLockManager] = None
        self._message_processor: Optional[MessageProcessor] = None
        self._tool_result_handler: Optional[ToolResultHandler] = None
        self._hitl_handler: Optional[HITLDecisionHandler] = None
        self._plan_approval_handler: Optional[PlanApprovalHandler] = None
        
        logger.info("DIContainer инициализирован")
    
    # ==================== Use Cases ====================
    
    def get_process_message_use_case(
        self,
        db: AsyncSession
    ) -> ProcessMessageUseCase:
        """
        Получить Use Case для обработки сообщений.
        
        Args:
            db: Сессия БД
            
        Returns:
            ProcessMessageUseCase: Use Case
        """
        message_processor = self._get_message_processor(db)
        lock_manager = self._get_lock_manager()
        
        return ProcessMessageUseCase(
            message_processor=message_processor,
            lock_manager=lock_manager
        )
    
    def get_switch_agent_use_case(
        self,
        db: AsyncSession
    ) -> SwitchAgentUseCase:
        """
        Получить Use Case для переключения агента.
        
        Args:
            db: Сессия БД
            
        Returns:
            SwitchAgentUseCase: Use Case
        """
        agent_switcher = self._get_agent_switcher(db)
        lock_manager = self._get_lock_manager()
        
        return SwitchAgentUseCase(
            agent_switcher=agent_switcher,
            lock_manager=lock_manager
        )
    
    def get_process_tool_result_use_case(
        self,
        db: AsyncSession
    ) -> ProcessToolResultUseCase:
        """
        Получить Use Case для обработки результатов инструментов.
        
        Args:
            db: Сессия БД
            
        Returns:
            ProcessToolResultUseCase: Use Case
        """
        tool_result_handler = self._get_tool_result_handler(db)
        lock_manager = self._get_lock_manager()
        
        return ProcessToolResultUseCase(
            tool_result_handler=tool_result_handler,
            lock_manager=lock_manager
        )
    
    def get_handle_approval_use_case(
        self,
        db: AsyncSession
    ) -> HandleApprovalUseCase:
        """
        Получить Use Case для обработки approval решений.
        
        Args:
            db: Сессия БД
            
        Returns:
            HandleApprovalUseCase: Use Case
        """
        hitl_handler = self._get_hitl_handler(db)
        plan_approval_handler = self._get_plan_approval_handler(db)
        lock_manager = self._get_lock_manager()
        
        return HandleApprovalUseCase(
            hitl_handler=hitl_handler,
            plan_approval_handler=plan_approval_handler,
            lock_manager=lock_manager
        )
    
    # ==================== Domain Services ====================
    
    def _get_message_processor(self, db: AsyncSession) -> MessageProcessor:
        """Получить MessageProcessor (singleton)."""
        if self._message_processor is None:
            session_service = self.session_module.provide_session_service(
                db=db,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            agent_context_service = self.agent_module.provide_orchestration_service(
                db=db,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            agent_registry = self.agent_module.provide_agent_registry()
            llm_client = self.infrastructure_module.provide_llm_client()
            
            from app.application.handlers import StreamLLMResponseHandler
            from app.domain.services.tool_filter_service import ToolFilterService
            from app.domain.services.llm_response_processor import LLMResponseProcessor
            from app.domain.services.hitl_policy import HITLPolicyService
            from app.domain.services.approval_management import ApprovalManager
            from app.infrastructure.tool_registry import ToolRegistry
            
            # Create dependencies for StreamLLMResponseHandler
            tool_registry = ToolRegistry()
            tool_filter = ToolFilterService(tool_registry=tool_registry)
            hitl_policy = HITLPolicyService()
            response_processor = LLMResponseProcessor(hitl_policy=hitl_policy)
            approval_manager = ApprovalManager(
                approval_repository=self.session_module.provide_approval_repository(db),
                approval_policy=None
            )
            
            stream_handler = StreamLLMResponseHandler(
                llm_client=llm_client,
                tool_filter=tool_filter,
                response_processor=response_processor,
                event_publisher=self.infrastructure_module.provide_event_publisher(),
                session_service=session_service,
                approval_manager=approval_manager
            )
            
            self._message_processor = MessageProcessor(
                session_service=session_service,
                agent_context_service=agent_context_service,
                agent_registry=agent_registry,
                stream_handler=stream_handler,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
        
        return self._message_processor
    
    def _get_agent_switcher(self, db: AsyncSession):
        """Получить AgentSwitcher."""
        session_service = self.session_module.provide_session_service(
            db=db,
            event_publisher=self.infrastructure_module.provide_event_publisher()
        )
        agent_context_service = self.agent_module.provide_orchestration_service(
            db=db,
            event_publisher=self.infrastructure_module.provide_event_publisher()
        )
        
        return self.agent_module.provide_agent_switcher(
            session_service=session_service,
            agent_context_service=agent_context_service,
            event_publisher=self.infrastructure_module.provide_event_publisher()
        )
    
    def _get_tool_result_handler(self, db: AsyncSession) -> ToolResultHandler:
        """Получить ToolResultHandler (singleton)."""
        if self._tool_result_handler is None:
            session_service = self.session_module.provide_session_service(
                db=db,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            agent_context_service = self.agent_module.provide_orchestration_service(
                db=db,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            agent_registry = self.agent_module.provide_agent_registry()
            llm_client = self.infrastructure_module.provide_llm_client()
            
            from app.application.handlers import StreamLLMResponseHandler
            stream_handler = StreamLLMResponseHandler(
                llm_client=llm_client,
                session_service=session_service,
                agent_context_service=agent_context_service,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            
            self._tool_result_handler = ToolResultHandler(
                session_service=session_service,
                agent_context_service=agent_context_service,
                agent_registry=agent_registry,
                stream_handler=stream_handler,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
        
        return self._tool_result_handler
    
    def _get_hitl_handler(self, db: AsyncSession) -> HITLDecisionHandler:
        """Получить HITLDecisionHandler (singleton)."""
        if self._hitl_handler is None:
            session_service = self.session_module.provide_session_service(
                db=db,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            agent_context_service = self.agent_module.provide_orchestration_service(
                db=db,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            agent_registry = self.agent_module.provide_agent_registry()
            llm_client = self.infrastructure_module.provide_llm_client()
            
            from app.application.handlers import StreamLLMResponseHandler
            stream_handler = StreamLLMResponseHandler(
                llm_client=llm_client,
                session_service=session_service,
                agent_context_service=agent_context_service,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            
            self._hitl_handler = HITLDecisionHandler(
                session_service=session_service,
                agent_context_service=agent_context_service,
                agent_registry=agent_registry,
                stream_handler=stream_handler,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
        
        return self._hitl_handler
    
    def _get_plan_approval_handler(self, db: AsyncSession) -> PlanApprovalHandler:
        """Получить PlanApprovalHandler (singleton)."""
        if self._plan_approval_handler is None:
            execution_engine = self.execution_module.provide_execution_engine(
                db=db,
                agent_registry=self.agent_module.provide_agent_registry(),
                session_service=self.session_module.provide_session_service(
                    db=db,
                    event_publisher=self.infrastructure_module.provide_event_publisher()
                ),
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
            
            self._plan_approval_handler = PlanApprovalHandler(
                execution_engine=execution_engine,
                event_publisher=self.infrastructure_module.provide_event_publisher()
            )
        
        return self._plan_approval_handler
    
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

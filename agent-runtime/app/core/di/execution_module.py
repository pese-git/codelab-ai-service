"""
DI Module для Execution Context.

Предоставляет зависимости для выполнения планов и subtasks.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.execution_context.services import (
    PlanExecutionService,
    SubtaskExecutor,
    DependencyResolver
)
from app.domain.execution_context.repositories import ExecutionPlanRepository
from app.infrastructure.persistence.repositories import ExecutionPlanRepositoryImpl
from app.domain.services import ExecutionEngine

logger = logging.getLogger("agent-runtime.di.execution_module")


class ExecutionModule:
    """
    DI модуль для Execution Context.
    
    Предоставляет:
    - ExecutionPlanRepository
    - PlanExecutionService
    - SubtaskExecutor
    - DependencyResolver
    - ExecutionEngine (legacy)
    """
    
    def __init__(self):
        """Инициализация модуля."""
        self._plan_repository: Optional[ExecutionPlanRepository] = None
        self._execution_service: Optional[PlanExecutionService] = None
        self._subtask_executor: Optional[SubtaskExecutor] = None
        self._dependency_resolver: Optional[DependencyResolver] = None
        self._execution_engine: Optional[ExecutionEngine] = None
        
        logger.debug("ExecutionModule инициализирован")
    
    def provide_plan_repository(
        self,
        db: AsyncSession
    ) -> ExecutionPlanRepository:
        """
        Предоставить репозиторий планов выполнения.
        
        Args:
            db: Сессия БД
            
        Returns:
            ExecutionPlanRepository: Реализация репозитория
        """
        return ExecutionPlanRepositoryImpl(db)
    
    def provide_execution_service(
        self,
        plan_repository: ExecutionPlanRepository,
        subtask_executor: SubtaskExecutor,
        dependency_resolver: DependencyResolver
    ) -> PlanExecutionService:
        """
        Предоставить сервис выполнения планов.
        
        Args:
            plan_repository: Репозиторий планов
            subtask_executor: Executor subtasks
            dependency_resolver: Resolver зависимостей
            
        Returns:
            PlanExecutionService: Сервис выполнения
        """
        if self._execution_service is None:
            self._execution_service = PlanExecutionService(
                repository=plan_repository,
                subtask_executor=subtask_executor,
                dependency_resolver=dependency_resolver
            )
        return self._execution_service
    
    def provide_subtask_executor(
        self,
        agent_registry,
        session_service,
        stream_handler=None
    ) -> SubtaskExecutor:
        """
        Предоставить executor subtasks.
        
        Args:
            agent_registry: Реестр агентов
            session_service: Сервис управления сессиями
            stream_handler: Handler для streaming (опционально)
            
        Returns:
            SubtaskExecutor: Executor subtasks
        """
        if self._subtask_executor is None:
            self._subtask_executor = SubtaskExecutor(
                agent_registry=agent_registry,
                session_service=session_service,
                stream_handler=stream_handler
            )
        return self._subtask_executor
    
    def provide_dependency_resolver(self) -> DependencyResolver:
        """
        Предоставить resolver зависимостей.
        
        Returns:
            DependencyResolver: Resolver зависимостей
        """
        if self._dependency_resolver is None:
            self._dependency_resolver = DependencyResolver()
        return self._dependency_resolver
    
    def provide_execution_engine(
        self,
        db: AsyncSession,
        agent_registry,
        session_service,
        stream_handler=None,
        event_publisher=None
    ) -> ExecutionEngine:
        """
        Предоставить legacy ExecutionEngine.
        
        Для обратной совместимости со старым кодом.
        
        Args:
            db: Сессия БД
            agent_registry: Реестр агентов
            session_service: Сервис управления сессиями
            stream_handler: Handler для streaming (опционально)
            event_publisher: Publisher событий (опционально)
            
        Returns:
            ExecutionEngine: Legacy engine
        """
        if self._execution_engine is None:
            from app.infrastructure.persistence.repositories.plan_repository_impl_legacy import (
                PlanRepositoryImplLegacy
            )
            
            plan_repo = PlanRepositoryImplLegacy(db)
            
            self._execution_engine = ExecutionEngine(
                plan_repository=plan_repo,
                agent_registry=agent_registry,
                session_service=session_service,
                stream_handler=stream_handler,
                event_publisher=event_publisher
            )
        
        return self._execution_engine

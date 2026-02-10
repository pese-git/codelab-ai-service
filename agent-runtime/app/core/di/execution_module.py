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

logger = logging.getLogger("agent-runtime.di.execution_module")


class ExecutionModule:
    """
    DI модуль для Execution Context.
    
    Предоставляет:
    - ExecutionPlanRepository
    - PlanExecutionService
    - SubtaskExecutor
    - DependencyResolver
    """
    
    def __init__(self):
        """Инициализация модуля."""
        self._plan_repository: Optional[ExecutionPlanRepository] = None
        self._execution_service: Optional[PlanExecutionService] = None
        self._subtask_executor: Optional[SubtaskExecutor] = None
        self._dependency_resolver: Optional[DependencyResolver] = None
        
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
        plan_repository: ExecutionPlanRepository,
        max_retries: int = 3
    ) -> SubtaskExecutor:
        """
        Предоставить executor subtasks.
        
        Args:
            plan_repository: Репозиторий для работы с планами
            max_retries: Максимальное количество попыток при ошибке
            
        Returns:
            SubtaskExecutor: Executor subtasks
        """
        if self._subtask_executor is None:
            self._subtask_executor = SubtaskExecutor(
                plan_repository=plan_repository,
                max_retries=max_retries
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

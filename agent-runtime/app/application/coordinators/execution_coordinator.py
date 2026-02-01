"""
ExecutionCoordinator - Application-level coordinator для выполнения планов.

Координирует взаимодействие между OrchestratorAgent и ExecutionEngine.
Управляет lifecycle выполнения плана и обрабатывает ошибки.
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

from app.domain.services.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
    ExecutionEngineError
)
from app.domain.entities.plan import PlanStatus

if TYPE_CHECKING:
    from app.domain.repositories.plan_repository import PlanRepository
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.application.execution_coordinator")


class ExecutionCoordinatorError(Exception):
    """Ошибка ExecutionCoordinator"""
    pass


class ExecutionCoordinator:
    """
    Application-level coordinator для выполнения планов.
    
    Responsibilities:
    - Координация выполнения плана через ExecutionEngine
    - Мониторинг прогресса выполнения
    - Обработка ошибок и failures
    - Поддержка cancellation
    - Предоставление статуса выполнения
    
    Attributes:
        execution_engine: Engine для выполнения планов
        plan_repository: Repository для работы с планами
    
    Example:
        >>> coordinator = ExecutionCoordinator(
        ...     execution_engine=engine,
        ...     plan_repository=repo
        ... )
        >>> result = await coordinator.execute_plan(
        ...     plan_id="plan-123",
        ...     session_id="session-456",
        ...     session_service=session_service,
        ...     stream_handler=stream_handler
        ... )
    """
    
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        plan_repository: "PlanRepository"
    ):
        """
        Initialize ExecutionCoordinator.
        
        Args:
            execution_engine: Engine для выполнения планов
            plan_repository: Repository для работы с планами
        """
        self.execution_engine = execution_engine
        self.plan_repository = plan_repository
        
        logger.info("ExecutionCoordinator initialized")
    
    async def execute_plan(
        self,
        plan_id: str,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> ExecutionResult:
        """
        Execute plan with coordination and monitoring.
        
        Coordinates:
        1. Validate plan is ready for execution
        2. Execute through ExecutionEngine
        3. Monitor progress
        4. Handle errors
        5. Return aggregated results
        
        Args:
            plan_id: ID плана для выполнения
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Returns:
            ExecutionResult с результатами выполнения
            
        Raises:
            ExecutionCoordinatorError: При ошибке координации
            ExecutionEngineError: При ошибке выполнения
            
        Example:
            >>> result = await coordinator.execute_plan(
            ...     plan_id="plan-123",
            ...     session_id="session-456",
            ...     session_service=session_service,
            ...     stream_handler=stream_handler
            ... )
            >>> print(f"Completed: {result.completed_subtasks}/{result.total_subtasks}")
        """
        logger.info(
            f"ExecutionCoordinator starting execution of plan {plan_id} "
            f"for session {session_id}"
        )
        
        try:
            # 1. Validate plan exists and is ready
            await self._validate_plan_ready(plan_id)
            
            # 2. Execute through ExecutionEngine
            result = await self.execution_engine.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            )
            
            # 3. Log results
            logger.info(
                f"Plan {plan_id} execution completed: "
                f"status={result.status}, "
                f"completed={result.completed_subtasks}/{result.total_subtasks}, "
                f"failed={result.failed_subtasks}, "
                f"duration={result.duration_seconds:.2f}s"
            )
            
            return result
            
        except ExecutionEngineError as e:
            logger.error(
                f"ExecutionEngine error for plan {plan_id}: {e}",
                exc_info=True
            )
            raise
        
        except Exception as e:
            logger.error(
                f"Unexpected error executing plan {plan_id}: {e}",
                exc_info=True
            )
            raise ExecutionCoordinatorError(
                f"Failed to coordinate execution of plan {plan_id}: {str(e)}"
            ) from e
    
    async def _validate_plan_ready(self, plan_id: str) -> None:
        """
        Validate plan is ready for execution.
        
        Args:
            plan_id: ID плана
            
        Raises:
            ExecutionCoordinatorError: If plan is not ready
        """
        plan = await self.plan_repository.find_by_id(plan_id)
        
        if not plan:
            raise ExecutionCoordinatorError(f"Plan {plan_id} not found")
        
        if plan.status != PlanStatus.APPROVED:
            raise ExecutionCoordinatorError(
                f"Plan {plan_id} is not approved (status: {plan.status.value}). "
                "Only approved plans can be executed."
            )
        
        if not plan.subtasks:
            raise ExecutionCoordinatorError(
                f"Plan {plan_id} has no subtasks"
            )
        
        logger.debug(f"Plan {plan_id} validated and ready for execution")
    
    async def get_execution_status(
        self,
        plan_id: str
    ) -> Dict[str, Any]:
        """
        Get current execution status of a plan.
        
        Args:
            plan_id: ID плана
            
        Returns:
            Status information dict:
            {
                "plan_id": str,
                "status": str,
                "progress": {...},
                "current_subtask_id": str,
                "started_at": str,
                "completed_at": str
            }
            
        Raises:
            ExecutionCoordinatorError: If plan not found
        """
        try:
            return await self.execution_engine.get_execution_status(plan_id)
        except ExecutionEngineError as e:
            raise ExecutionCoordinatorError(
                f"Failed to get status for plan {plan_id}: {str(e)}"
            ) from e
    
    async def cancel_execution(
        self,
        plan_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Cancel plan execution.
        
        Args:
            plan_id: ID плана
            reason: Причина отмены
            
        Returns:
            Cancellation information dict
            
        Raises:
            ExecutionCoordinatorError: If cancellation fails
        """
        logger.info(f"Cancelling execution of plan {plan_id}: {reason}")
        
        try:
            return await self.execution_engine.cancel_execution(
                plan_id=plan_id,
                reason=reason
            )
        except ExecutionEngineError as e:
            raise ExecutionCoordinatorError(
                f"Failed to cancel plan {plan_id}: {str(e)}"
            ) from e
    
    async def get_plan_summary(self, plan_id: str) -> Dict[str, Any]:
        """
        Get summary of plan for presentation to user.
        
        Args:
            plan_id: ID плана
            
        Returns:
            Plan summary dict with goal, subtasks, estimates
            
        Raises:
            ExecutionCoordinatorError: If plan not found
        """
        plan = await self.plan_repository.find_by_id(plan_id)
        
        if not plan:
            raise ExecutionCoordinatorError(f"Plan {plan_id} not found")
        
        return {
            "plan_id": plan.id,
            "goal": plan.goal,
            "status": plan.status.value,
            "subtasks_count": len(plan.subtasks),
            "subtasks": [
                {
                    "id": st.id,
                    "description": st.description,
                    "agent": st.agent.value,
                    "dependencies": st.dependencies,
                    "estimated_time": st.estimated_time,
                    "status": st.status.value,
                    "metadata": st.metadata  # Include metadata for dependency_indices
                }
                for st in plan.subtasks
            ],
            "total_estimated_time": self._calculate_total_time(plan),
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "approved_at": plan.approved_at.isoformat() if plan.approved_at else None
        }
    
    def _calculate_total_time(self, plan) -> str:
        """
        Calculate total estimated time for plan.
        
        Simple heuristic: sum all estimated times.
        
        Args:
            plan: Plan entity
            
        Returns:
            Total time estimate as string
        """
        # Simple implementation: just count subtasks
        # TODO: Parse time strings and sum properly
        total_subtasks = len(plan.subtasks)
        
        if total_subtasks == 0:
            return "0 min"
        elif total_subtasks <= 3:
            return f"{total_subtasks * 5} min"
        elif total_subtasks <= 10:
            return f"{total_subtasks * 3} min"
        else:
            return f"{total_subtasks // 2} min"

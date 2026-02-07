"""
ExecutionCoordinator - Application-level coordinator для выполнения планов.

Координирует взаимодействие между OrchestratorAgent и ExecutionEngine.
Управляет lifecycle выполнения плана и обрабатывает ошибки.
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING, AsyncGenerator

from app.domain.services.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
    ExecutionEngineError
)
from app.domain.entities.plan import PlanStatus
from app.models.schemas import StreamChunk

if TYPE_CHECKING:
    from app.domain.execution_context.repositories.execution_plan_repository import ExecutionPlanRepository as PlanRepository
    from app.domain.session_context.services import ConversationManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.application.execution_coordinator")


class ExecutionCoordinatorError(Exception):
    """Ошибка ExecutionCoordinator"""
    pass


class ExecutionCoordinator:
    """
    Application-level coordinator для выполнения планов.
    
    Responsibilities:
    - Координация выполнения плана через ExecutionEngine/ExecutionEngineAdapter
    - Мониторинг прогресса выполнения
    - Обработка ошибок и failures
    - Поддержка cancellation
    - Предоставление статуса выполнения
    
    Attributes:
        execution_engine: Engine или Adapter для выполнения планов
        plan_repository: Repository для работы с планами
    
    Example:
        >>> coordinator = ExecutionCoordinator(
        ...     execution_engine=engine_adapter,
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
        
        engine_type = type(execution_engine).__name__
        logger.info(f"ExecutionCoordinator initialized with {engine_type}")
    
    async def execute_plan(
        self,
        plan_id: str,
        session_id: str,
        session_service: "ConversationManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Execute plan with coordination and monitoring.
        
        ВАЖНО: Теперь возвращает AsyncGenerator для streaming выполнения.
        Пересылает все chunks от ExecutionEngine, включая tool_call события.
        
        Coordinates:
        1. Validate plan is ready for execution
        2. Execute through ExecutionEngine (streaming)
        3. Forward all chunks (including tool_call)
        4. Monitor progress
        5. Handle errors
        
        Args:
            plan_id: ID плана для выполнения
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Yields:
            StreamChunk: Chunks от ExecutionEngine (tool_call, status, etc.)
            
        Raises:
            ExecutionCoordinatorError: При ошибке координации
            ExecutionEngineError: При ошибке выполнения
        """
        logger.info(
            f"ExecutionCoordinator starting execution of plan {plan_id} "
            f"for session {session_id}"
        )
        
        try:
            # 1. Validate plan exists and is ready
            await self._validate_plan_ready(plan_id)
            
            # 2. Execute through ExecutionEngine and forward all chunks
            execution_result_metadata = None
            async for chunk in self.execution_engine.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            ):
                # Пересылать chunk дальше (включая tool_call!)
                yield chunk
                
                # Сохранить metadata из финального chunk
                if chunk.type == "execution_completed" and chunk.metadata:
                    execution_result_metadata = chunk.metadata
            
            # 3. Log results
            if execution_result_metadata:
                logger.info(
                    f"Plan {plan_id} execution completed: "
                    f"status={execution_result_metadata.get('status')}, "
                    f"completed={execution_result_metadata.get('completed_subtasks')}/"
                    f"{execution_result_metadata.get('total_subtasks')}, "
                    f"failed={execution_result_metadata.get('failed_subtasks')}, "
                    f"duration={execution_result_metadata.get('duration_seconds', 0):.2f}s"
                )
            
        except ExecutionEngineError as e:
            logger.error(
                f"ExecutionEngine error for plan {plan_id}: {e}",
                exc_info=True
            )
            # Пересылать ошибку как chunk
            yield StreamChunk(
                type="error",
                error=str(e),
                metadata={"plan_id": plan_id},
                is_final=True
            )
        
        except Exception as e:
            logger.error(
                f"Unexpected error executing plan {plan_id}: {e}",
                exc_info=True
            )
            # Пересылать ошибку как chunk
            yield StreamChunk(
                type="error",
                error=f"Failed to coordinate execution: {str(e)}",
                metadata={"plan_id": plan_id},
                is_final=True
            )
    
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
        
        # ✅ ИСПРАВЛЕНИЕ: Разрешить APPROVED и IN_PROGRESS (для resumable execution)
        if plan.status not in [PlanStatus.APPROVED, PlanStatus.IN_PROGRESS]:
            raise ExecutionCoordinatorError(
                f"Plan {plan_id} cannot be executed (status: {plan.status.value}). "
                "Only approved or in-progress plans can be executed."
            )
        
        if not plan.subtasks:
            raise ExecutionCoordinatorError(
                f"Plan {plan_id} has no subtasks"
            )
        
        logger.debug(f"Plan {plan_id} validated and ready for execution (status: {plan.status.value})")
    
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

"""
Сервис обработки Plan Approval решений пользователя.

Отвечает за обработку решений пользователя по одобрению планов
и продолжение выполнения после принятия решения.
"""

import logging
from typing import AsyncGenerator, Optional, TYPE_CHECKING, Any
from enum import Enum

from ...models.schemas import StreamChunk
from ..entities.fsm_state import FSMEvent

if TYPE_CHECKING:
    from .session_management import SessionManagementService
    from .approval_management import ApprovalManager
    from .fsm_orchestrator import FSMOrchestrator
    from ...agents.orchestrator_agent import OrchestratorAgent
    from ...application.coordinators.execution_coordinator import ExecutionCoordinator

logger = logging.getLogger("agent-runtime.domain.plan_approval_handler")


class PlanApprovalDecision(str, Enum):
    """Решения пользователя по одобрению плана"""
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


class PlanApprovalHandler:
    """
    Сервис обработки Plan Approval решений пользователя.
    
    Ответственности:
    - Валидация решения (approve/reject/modify)
    - Получение pending approval state
    - Обработка решения и FSM transitions
    - Продолжение выполнения плана или возврат к планированию
    
    Атрибуты:
        _approval_manager: Unified approval manager
        _session_service: Сервис управления сессиями
        _fsm_orchestrator: FSM orchestrator для state management
        _execution_coordinator: Coordinator для выполнения планов
    """
    
    def __init__(
        self,
        approval_manager: "ApprovalManager",
        session_service: "SessionManagementService",
        fsm_orchestrator: "FSMOrchestrator",
        execution_coordinator: "ExecutionCoordinator"
    ):
        """
        Инициализация handler.
        
        Args:
            approval_manager: Unified approval manager
            session_service: Сервис управления сессиями
            fsm_orchestrator: FSM orchestrator
            execution_coordinator: Execution coordinator
        """
        self._approval_manager = approval_manager
        self._session_service = session_service
        self._fsm_orchestrator = fsm_orchestrator
        self._execution_coordinator = execution_coordinator
        
        logger.info("PlanApprovalHandler инициализирован")
    
    async def handle(
        self,
        session_id: str,
        approval_request_id: str,
        decision: str,
        feedback: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать Plan Approval решение пользователя.
        
        Обрабатывает решение пользователя по одобрению плана:
        - approve: Выполнить план через ExecutionCoordinator
        - reject: Отклонить план, вернуться к IDLE
        - modify: Запросить модификацию плана (вернуться к ARCHITECT_PLANNING)
        
        Args:
            session_id: ID сессии
            approval_request_id: ID запроса на одобрение
            decision: Решение пользователя (approve/reject/modify)
            feedback: Обратная связь пользователя (для reject/modify)
            stream_handler: Stream handler для продолжения выполнения
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            ValueError: Если решение невалидно или pending state не найден
        """
        logger.info(
            f"Обработка Plan Approval решения для сессии {session_id}: "
            f"approval_request_id={approval_request_id}, decision={decision}"
        )
        
        # Валидация решения
        try:
            decision_enum = PlanApprovalDecision(decision)
        except ValueError:
            error_msg = f"Invalid plan approval decision: {decision}"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                is_final=True
            )
            return
        
        # Получить pending approval
        pending_approval = await self._approval_manager.get_pending(approval_request_id)
        if not pending_approval:
            error_msg = f"No pending approval found for request_id={approval_request_id}"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                is_final=True
            )
            return
        
        # Извлечь plan_id из details
        plan_id = pending_approval.details.get("plan_id")
        if not plan_id:
            error_msg = f"Plan ID not found in approval details"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                is_final=True
            )
            return
        
        # Обработать решение
        if decision_enum == PlanApprovalDecision.APPROVE:
            yield StreamChunk(
                type="status",
                content="✅ Plan approved by user. Starting execution...",
                metadata={"plan_id": plan_id}
            )
            
            # Обновить статус approval
            await self._approval_manager.approve(approval_request_id)
            
            # FSM: PLAN_REVIEW → PLAN_EXECUTION
            await self._fsm_orchestrator.transition(
                session_id=session_id,
                event=FSMEvent.PLAN_APPROVED,
                metadata={"approved_by": "user", "plan_id": plan_id}
            )
            
            logger.info(f"Plan {plan_id} approved, starting execution")
            
            # Execute plan
            yield StreamChunk(
                type="status",
                content=f"⚙️ Executing plan...",
                metadata={"fsm_state": "plan_execution"}
            )
            
            execution_result = await self._execution_coordinator.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                session_service=self._session_service,
                stream_handler=None  # TODO: Pass stream_handler for progress updates
            )
            
            logger.info(
                f"Plan {plan_id} execution completed: "
                f"{execution_result.completed_subtasks}/{execution_result.total_subtasks} successful"
            )
            
            # FSM: PLAN_EXECUTION → COMPLETED
            await self._fsm_orchestrator.transition(
                session_id=session_id,
                event=FSMEvent.PLAN_EXECUTION_COMPLETED,
                metadata={"execution_result": execution_result.to_dict()}
            )
            
            # Present results
            yield StreamChunk(
                type="execution_completed",
                content=self._format_execution_result(execution_result),
                metadata={
                    "plan_id": plan_id,
                    "fsm_state": "completed",
                    "execution_result": execution_result.to_dict()
                },
                is_final=True
            )
            
        elif decision_enum == PlanApprovalDecision.REJECT:
            yield StreamChunk(
                type="status",
                content=f"❌ Plan rejected by user: {feedback or 'No reason provided'}",
                metadata={"plan_id": plan_id}
            )
            
            # Обновить статус approval
            await self._approval_manager.reject(approval_request_id, reason=feedback)
            
            # FSM: PLAN_REVIEW → IDLE
            await self._fsm_orchestrator.transition(
                session_id=session_id,
                event=FSMEvent.PLAN_REJECTED,
                metadata={"rejected_by": "user", "reason": feedback}
            )
            
            logger.info(f"Plan {plan_id} rejected by user, returning to IDLE")
            
            yield StreamChunk(
                type="plan_rejected",
                content="Plan rejected. You can send a new message to start over.",
                metadata={"plan_id": plan_id, "fsm_state": "idle"},
                is_final=True
            )
            
        elif decision_enum == PlanApprovalDecision.MODIFY:
            yield StreamChunk(
                type="status",
                content=f"🔄 Plan modification requested: {feedback or 'No feedback provided'}",
                metadata={"plan_id": plan_id}
            )
            
            # Обновить статус approval как rejected (modification = rejection + new planning)
            await self._approval_manager.reject(
                approval_request_id,
                reason=f"Modification requested: {feedback}"
            )
            
            # FSM: PLAN_REVIEW → ARCHITECT_PLANNING
            await self._fsm_orchestrator.transition(
                session_id=session_id,
                event=FSMEvent.PLAN_MODIFICATION_REQUESTED,
                metadata={"requested_by": "user", "feedback": feedback}
            )
            
            logger.info(
                f"Plan {plan_id} modification requested, "
                f"returning to ARCHITECT_PLANNING"
            )
            
            # TODO: Implement replanning logic
            # For now, just notify user
            yield StreamChunk(
                type="plan_modification_requested",
                content=(
                    "Plan modification requested. "
                    "Replanning logic not yet implemented. "
                    "Please send a new message to create a new plan."
                ),
                metadata={
                    "plan_id": plan_id,
                    "fsm_state": "architect_planning",
                    "feedback": feedback
                },
                is_final=True
            )
    
    def _format_execution_result(self, result) -> str:
        """
        Format execution result for user presentation.
        
        Args:
            result: ExecutionResult from ExecutionCoordinator
            
        Returns:
            Formatted string for display
        """
        lines = [
            f"✅ **Plan Execution {'Completed' if result.status == 'completed' else 'Failed'}**",
            f"",
            f"**Results:**",
            f"- Completed: {result.completed_subtasks}/{result.total_subtasks}",
            f"- Failed: {result.failed_subtasks}",
            f"- Duration: {result.duration_seconds:.1f}s",
            ""
        ]
        
        if result.errors:
            lines.append("**Errors:**")
            for subtask_id, error in result.errors.items():
                lines.append(f"- {subtask_id}: {error}")
        
        return "\n".join(lines)

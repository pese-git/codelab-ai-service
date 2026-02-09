"""
ExecutionEngine - координатор исполнения планов.

Отвечает за:
- Управление жизненным циклом выполнения плана
- Координацию выполнения подзадач с учетом зависимостей
- Параллельное выполнение независимых подзадач
- Мониторинг прогресса
- Агрегацию результатов
- Обработку ошибок и rollback
"""

import logging
import asyncio
import time
from typing import Dict, Any, List, Optional, Set, TYPE_CHECKING, AsyncGenerator
from datetime import datetime, timezone

from app.domain.execution_context.entities.execution_plan import ExecutionPlan as Plan
from app.domain.execution_context.entities.subtask import Subtask
from app.domain.execution_context.value_objects import PlanStatus, SubtaskStatus
from app.domain.entities.execution_state import ExecutionState, ExecutionStateManager
from app.domain.services.dependency_resolver import DependencyResolver
from app.domain.services.subtask_executor import SubtaskExecutor, SubtaskExecutionError
from app.models.schemas import StreamChunk

if TYPE_CHECKING:
    from app.domain.execution_context.repositories.execution_plan_repository import ExecutionPlanRepository as PlanRepository
    from app.domain.session_context.services import ConversationManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler
    from app.domain.services.approval_management import ApprovalManager

logger = logging.getLogger("agent-runtime.domain.execution_engine")


class ExecutionEngineError(Exception):
    """Ошибка ExecutionEngine"""
    pass


class ExecutionResult:
    """Результат выполнения плана"""
    
    def __init__(
        self,
        plan_id: str,
        status: str,
        completed_subtasks: int,
        failed_subtasks: int,
        total_subtasks: int,
        results: Dict[str, Any],
        errors: Dict[str, str],
        duration_seconds: Optional[float] = None
    ):
        self.plan_id = plan_id
        self.status = status
        self.completed_subtasks = completed_subtasks
        self.failed_subtasks = failed_subtasks
        self.total_subtasks = total_subtasks
        self.results = results
        self.errors = errors
        self.duration_seconds = duration_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            "plan_id": self.plan_id,
            "status": self.status,
            "completed_subtasks": self.completed_subtasks,
            "failed_subtasks": self.failed_subtasks,
            "total_subtasks": self.total_subtasks,
            "success_rate": (
                self.completed_subtasks / self.total_subtasks * 100
                if self.total_subtasks > 0 else 0
            ),
            "results": self.results,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds
        }


class ExecutionEngine:
    """
    Координатор исполнения планов.
    
    Responsibilities:
    - Управление жизненным циклом выполнения плана через State Machine
    - Координация выполнения подзадач
    - Ожидание HITL approvals между subtasks
    - Параллельное выполнение независимых задач
    - Мониторинг прогресса
    - Агрегация результатов
    - Error handling и rollback
    
    Attributes:
        plan_repository: Репозиторий планов
        subtask_executor: Исполнитель подзадач
        dependency_resolver: Резолвер зависимостей
        approval_manager: Менеджер approvals для HITL
        max_parallel_tasks: Максимальное количество параллельных задач
        _state_managers: State managers для активных executions
    """
    
    def __init__(
        self,
        plan_repository: "PlanRepository",
        subtask_executor: SubtaskExecutor,
        dependency_resolver: DependencyResolver,
        approval_manager: "ApprovalManager",
        max_parallel_tasks: int = 3
    ):
        """
        Инициализация ExecutionEngine.
        
        Args:
            plan_repository: Репозиторий планов
            subtask_executor: Исполнитель подзадач
            dependency_resolver: Резолвер зависимостей
            approval_manager: Менеджер approvals для HITL
            max_parallel_tasks: Максимальное количество параллельных задач
        """
        self.plan_repository = plan_repository
        self.subtask_executor = subtask_executor
        self.dependency_resolver = dependency_resolver
        self.approval_manager = approval_manager
        self.max_parallel_tasks = max_parallel_tasks
        
        # State managers для активных executions
        self._state_managers: Dict[str, ExecutionStateManager] = {}
        
        logger.info(
            f"ExecutionEngine initialized with "
            f"max_parallel_tasks={max_parallel_tasks}, "
            f"approval_manager={approval_manager is not None}"
        )
    
    async def execute_plan(
        self,
        plan_id: str,
        session_id: str,
        session_service: "ConversationManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить план.
        
        ВАЖНО: Теперь возвращает AsyncGenerator для streaming выполнения.
        Подзадачи выполняются ПОСЛЕДОВАТЕЛЬНО (не параллельно) для поддержки
        streaming tool_call событий к клиенту.
        
        Args:
            plan_id: ID плана
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Yields:
            StreamChunk: Chunks от подзадач и статусные обновления
            
        Raises:
            ExecutionEngineError: При ошибке выполнения
        """
        logger.info(f"Starting execution of plan {plan_id}")
        start_time = datetime.now(timezone.utc)
        
        # Получить план
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise ExecutionEngineError(f"Plan {plan_id} not found")
        
        # Проверить статус плана
        # ✅ ИСПРАВЛЕНИЕ: Разрешить APPROVED и IN_PROGRESS (для resumable execution)
        if plan.status not in [PlanStatus.APPROVED, PlanStatus.IN_PROGRESS]:
            raise ExecutionEngineError(
                f"Plan {plan_id} cannot be executed (status: {plan.status.value})"
            )
        
        # Создать state manager для этого execution
        state_manager = self._get_state_manager(plan_id)
        
        # Начать выполнение (только если еще не начато)
        if plan.status == PlanStatus.APPROVED:
            plan.start_execution()
            await self.plan_repository.save(plan)
            logger.info(f"Plan {plan_id} execution started")
        else:
            logger.info(f"Plan {plan_id} execution resuming (already IN_PROGRESS)")
        
        try:
            # ✅ ВАРИАНТ 2: Выполнить только ОДНУ pending subtask
            # Получить следующую pending subtask с учетом зависимостей
            next_subtask = plan.get_next_subtask()
            
            if not next_subtask:
                # Все subtasks выполнены - завершить план
                logger.info(f"No more pending subtasks for plan {plan_id}, completing")
                
                # Проверить, что ВСЕ subtasks действительно выполнены
                progress = plan.get_progress()
                if progress['done'] == progress['total'] and progress['failed'] == 0:
                    # Все subtasks успешно выполнены
                    plan.complete()
                    state_manager.transition_to(
                        ExecutionState.COMPLETED,
                        reason="All subtasks completed successfully"
                    )
                    await self.plan_repository.save(plan)
                    self._cleanup_state_manager(plan_id)
                    
                    # Вычислить длительность
                    end_time = datetime.now(timezone.utc)
                    duration = (end_time - start_time).total_seconds()
                    
                    yield StreamChunk(
                        type="execution_completed",
                        content="Plan execution completed successfully",
                        metadata={
                            "plan_id": plan_id,
                            "status": "completed",
                            "progress": progress,
                            "duration_seconds": duration
                        },
                        is_final=True
                    )
                else:
                    # Есть failed или running subtasks - не завершать
                    logger.info(
                        f"Plan {plan_id} has no more pending subtasks, but execution not complete: "
                        f"done={progress['done']}, failed={progress['failed']}, running={progress['running']}"
                    )
                    
                    # Просто вернуться - execution продолжится через tool_result
                
                return
            
            # Выполнить ОДНУ subtask
            logger.info(
                f"Executing subtask for plan {plan_id}: "
                f"{next_subtask.description[:50]}..."
            )
            
            # Отправить статус начала подзадачи
            progress = plan.get_progress()
            yield StreamChunk(
                type="status",
                content=f"Executing subtask: {next_subtask.description}",
                metadata={
                    "subtask_id": next_subtask.id,
                    "progress": f"{progress['done'] + 1}/{progress['total']}"
                }
            )
            
            try:
                # Выполнить подзадачу и пересылать все chunks
                async for chunk in self.subtask_executor.execute_subtask(
                    plan_id=plan.id,
                    subtask_id=next_subtask.id,
                    session_id=session_id,
                    session_service=session_service,
                    stream_handler=stream_handler
                ):
                    # Пересылать chunk дальше (включая tool_call!)
                    yield chunk
                    
                    # Если tool_call с approval - execution остановится здесь
                    # HTTP request завершится
                    # Tool_result вызовет execute_plan() снова для следующей subtask
                
                logger.info(f"Subtask {next_subtask.id} execution completed")
                
                # ✅ НЕ продолжать к следующей subtask
                # Tool_result_handler вызовет execute_plan() снова
                
            except SubtaskExecutionError as e:
                logger.error(f"Subtask {next_subtask.id} failed: {e}")
                
                # Завершить план с ошибкой
                plan.fail(f"Subtask failed: {str(e)}")
                state_manager.transition_to(
                    ExecutionState.FAILED,
                    reason=f"Subtask {next_subtask.id} failed"
                )
                await self.plan_repository.save(plan)
                self._cleanup_state_manager(plan_id)
                
                # Отправить error chunk
                yield StreamChunk(
                    type="error",
                    error=f"Subtask {next_subtask.id} failed: {str(e)}",
                    metadata={"subtask_id": next_subtask.id},
                    is_final=True
                )
            
        except Exception as e:
            logger.error(f"Error executing plan {plan_id}: {e}", exc_info=True)
            
            # Получить state manager если существует
            state_manager = self._state_managers.get(plan_id)
            if state_manager and not state_manager.is_terminal():
                state_manager.transition_to(
                    ExecutionState.FAILED,
                    reason=f"Execution error: {str(e)}"
                )
            
            # Пометить план как failed
            plan.fail(f"Execution error: {str(e)}")
            await self.plan_repository.save(plan)
            
            # Cleanup state manager
            self._cleanup_state_manager(plan_id)
            
            # Отправить error chunk
            yield StreamChunk(
                type="error",
                error=f"Plan execution failed: {str(e)}",
                metadata={"plan_id": plan_id},
                is_final=True
            )
    
    def _get_state_manager(self, plan_id: str) -> ExecutionStateManager:
        """
        Получить или создать state manager для плана.
        
        Args:
            plan_id: ID плана
            
        Returns:
            ExecutionStateManager для плана
        """
        if plan_id not in self._state_managers:
            self._state_managers[plan_id] = ExecutionStateManager(plan_id)
        return self._state_managers[plan_id]
    
    def _cleanup_state_manager(self, plan_id: str) -> None:
        """
        Удалить state manager после завершения execution.
        
        Args:
            plan_id: ID плана
        """
        if plan_id in self._state_managers:
            del self._state_managers[plan_id]
            logger.debug(f"Cleaned up state manager for plan {plan_id}")
    
    async def _wait_for_approval_resolution(
        self,
        plan_id: str,
        session_id: str,
        pending_approval_ids: Set[str],
        timeout_seconds: int = 300
    ) -> None:
        """
        Ждать разрешения approvals с использованием state machine.
        
        Переводит execution в состояние WAITING_APPROVAL и ждет,
        пока все approvals не будут resolved (approved или rejected).
        
        Args:
            plan_id: ID плана
            session_id: ID сессии
            pending_approval_ids: Set ID approvals для ожидания
            timeout_seconds: Таймаут ожидания (по умолчанию 5 минут)
            
        Raises:
            ExecutionEngineError: При таймауте или ошибке
        """
        state_manager = self._get_state_manager(plan_id)
        
        # Переход в состояние WAITING_APPROVAL
        state_manager.transition_to(
            ExecutionState.WAITING_APPROVAL,
            reason=f"Waiting for {len(pending_approval_ids)} approvals",
            metadata={"approval_ids": list(pending_approval_ids)}
        )
        
        start_time = time.time()
        
        logger.info(
            f"Plan {plan_id} entered WAITING_APPROVAL state for "
            f"{len(pending_approval_ids)} approvals"
        )
        
        while state_manager.is_waiting_approval():
            # Получить текущие pending approvals
            current_pending = await self.approval_manager.get_pending_by_session(session_id)
            current_pending_ids = {a.request_id for a in current_pending}
            
            # Проверить, остались ли наши approvals в pending
            still_pending = pending_approval_ids & current_pending_ids
            
            if not still_pending:
                # Все approvals разрешены - переход в RESUMED
                elapsed = time.time() - start_time
                state_manager.transition_to(
                    ExecutionState.RESUMED,
                    reason=f"All approvals resolved after {elapsed:.1f}s"
                )
                logger.info(
                    f"Plan {plan_id} transitioned to RESUMED after {elapsed:.1f}s"
                )
                return
            
            # Проверить таймаут
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                # Timeout - переход в CANCELLED
                state_manager.transition_to(
                    ExecutionState.CANCELLED,
                    reason=f"Approval timeout after {elapsed:.1f}s",
                    metadata={"still_pending": list(still_pending)}
                )
                raise ExecutionEngineError(
                    f"Timeout waiting for approvals after {elapsed:.1f}s. "
                    f"Still pending: {list(still_pending)}"
                )
            
            # Логировать прогресс каждые 10 секунд
            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                logger.info(
                    f"Plan {plan_id} still waiting for {len(still_pending)} approvals "
                    f"({elapsed:.0f}s elapsed)"
                )
            
            # Подождать перед следующей проверкой
            await asyncio.sleep(0.5)
    
    def _get_execution_order(self, plan: Plan) -> List[List[str]]:
        """
        Получить порядок выполнения подзадач с учетом зависимостей.
        
        Возвращает список батчей, где каждый батч содержит подзадачи,
        которые могут выполняться параллельно.
        
        Args:
            plan: План
            
        Returns:
            Список батчей с ID подзадач
            
        Raises:
            ExecutionEngineError: При циклических зависимостях
        """
        try:
            # Получить порядок выполнения по уровням из DependencyResolver
            levels = self.dependency_resolver.get_execution_order(plan)
            
            # Преобразовать уровни Subtask в батчи ID с учетом max_parallel_tasks
            batches = []
            for level in levels:
                # Разбить уровень на батчи по max_parallel_tasks
                level_ids = [subtask.id for subtask in level]
                
                # Если уровень больше max_parallel_tasks, разбить на несколько батчей
                for i in range(0, len(level_ids), self.max_parallel_tasks):
                    batch = level_ids[i:i + self.max_parallel_tasks]
                    batches.append(batch)
            
            return batches
            
        except ValueError as e:
            # DependencyResolver выбрасывает ValueError при циклических зависимостях
            raise ExecutionEngineError(
                f"Plan {plan.id} has circular dependencies: {str(e)}"
            ) from e
    
    async def get_execution_status(
        self,
        plan_id: str
    ) -> Dict[str, Any]:
        """
        Получить статус выполнения плана.
        
        Args:
            plan_id: ID плана
            
        Returns:
            Информация о статусе выполнения
            
        Raises:
            ExecutionEngineError: Если план не найден
        """
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise ExecutionEngineError(f"Plan {plan_id} not found")
        
        progress = plan.get_progress()
        
        return {
            "plan_id": plan.id,
            "status": plan.status.value,
            "progress": progress,
            "current_subtask_id": plan.current_subtask_id,
            "started_at": (
                plan.started_at.isoformat() if plan.started_at else None
            ),
            "completed_at": (
                plan.completed_at.isoformat() if plan.completed_at else None
            )
        }
    
    async def cancel_execution(
        self,
        plan_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Отменить выполнение плана.
        
        Args:
            plan_id: ID плана
            reason: Причина отмены
            
        Returns:
            Информация об отмене
            
        Raises:
            ExecutionEngineError: Если план не найден или не может быть отменен
        """
        logger.info(f"Cancelling execution of plan {plan_id}: {reason}")
        
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise ExecutionEngineError(f"Plan {plan_id} not found")
        
        # Отменить план
        try:
            plan.cancel(reason)
            await self.plan_repository.save(plan)
            
            logger.info(f"Plan {plan_id} cancelled successfully")
            
            return {
                "plan_id": plan.id,
                "status": "cancelled",
                "reason": reason,
                "cancelled_at": (
                    plan.completed_at.isoformat() if plan.completed_at else None
                )
            }
        except ValueError as e:
            raise ExecutionEngineError(
                f"Cannot cancel plan {plan_id}: {str(e)}"
            ) from e

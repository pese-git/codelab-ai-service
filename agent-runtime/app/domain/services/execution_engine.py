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
from typing import Dict, Any, List, Optional, Set, TYPE_CHECKING, AsyncGenerator
from datetime import datetime, timezone

from app.domain.entities.plan import Plan, PlanStatus, Subtask, SubtaskStatus
from app.domain.services.dependency_resolver import DependencyResolver
from app.domain.services.subtask_executor import SubtaskExecutor, SubtaskExecutionError
from app.models.schemas import StreamChunk

if TYPE_CHECKING:
    from app.domain.repositories.plan_repository import PlanRepository
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

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
    - Управление жизненным циклом выполнения плана
    - Координация выполнения подзадач
    - Параллельное выполнение независимых задач
    - Мониторинг прогресса
    - Агрегация результатов
    - Error handling и rollback
    
    Attributes:
        plan_repository: Репозиторий планов
        subtask_executor: Исполнитель подзадач
        dependency_resolver: Резолвер зависимостей
        max_parallel_tasks: Максимальное количество параллельных задач
    """
    
    def __init__(
        self,
        plan_repository: "PlanRepository",
        subtask_executor: SubtaskExecutor,
        dependency_resolver: DependencyResolver,
        max_parallel_tasks: int = 3
    ):
        """
        Инициализация ExecutionEngine.
        
        Args:
            plan_repository: Репозиторий планов
            subtask_executor: Исполнитель подзадач
            dependency_resolver: Резолвер зависимостей
            max_parallel_tasks: Максимальное количество параллельных задач
        """
        self.plan_repository = plan_repository
        self.subtask_executor = subtask_executor
        self.dependency_resolver = dependency_resolver
        self.max_parallel_tasks = max_parallel_tasks
        
        logger.info(
            f"ExecutionEngine initialized with "
            f"max_parallel_tasks={max_parallel_tasks}"
        )
    
    async def execute_plan(
        self,
        plan_id: str,
        session_id: str,
        session_service: "SessionManagementService",
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
        if plan.status != PlanStatus.APPROVED:
            raise ExecutionEngineError(
                f"Plan {plan_id} is not approved (status: {plan.status.value})"
            )
        
        # Начать выполнение
        plan.start_execution()
        await self.plan_repository.save(plan)
        
        try:
            # Получить порядок выполнения с учетом зависимостей
            execution_order = self._get_execution_order(plan)
            
            logger.info(
                f"Execution order for plan {plan_id}: "
                f"{len(execution_order)} batches, executing SEQUENTIALLY for streaming support"
            )
            
            # Выполнить подзадачи ПОСЛЕДОВАТЕЛЬНО (не параллельно)
            # Это позволяет пересылать chunks (включая tool_call) через yield
            results = {}
            errors = {}
            total_count = len(plan.subtasks)
            
            # Flatten batches into sequential list
            all_subtask_ids = []
            for batch in execution_order:
                all_subtask_ids.extend(batch)
            
            for index, subtask_id in enumerate(all_subtask_ids):
                subtask = plan.get_subtask_by_id(subtask_id)
                if not subtask:
                    logger.error(f"Subtask {subtask_id} not found in plan")
                    errors[subtask_id] = "Subtask not found"
                    continue
                
                logger.info(
                    f"Executing subtask {index + 1}/{len(all_subtask_ids)}: "
                    f"{subtask.description[:50]}..."
                )
                
                # Отправить статус начала подзадачи
                yield StreamChunk(
                    type="status",
                    content=f"Executing subtask {index + 1}/{len(all_subtask_ids)}: {subtask.description}",
                    metadata={
                        "subtask_id": subtask_id,
                        "progress": f"{index + 1}/{len(all_subtask_ids)}"
                    }
                )
                
                try:
                    # Выполнить подзадачу и пересылать все chunks
                    subtask_result_metadata = None
                    async for chunk in self.subtask_executor.execute_subtask(
                        plan_id=plan.id,
                        subtask_id=subtask_id,
                        session_id=session_id,
                        session_service=session_service,
                        stream_handler=stream_handler
                    ):
                        # Пересылать chunk дальше (включая tool_call!)
                        yield chunk
                        
                        # Сохранить metadata из финального chunk
                        if chunk.is_final and chunk.metadata:
                            subtask_result_metadata = chunk.metadata
                    
                    # Собрать результат из metadata
                    if subtask_result_metadata and subtask_result_metadata.get("status") == "completed":
                        results[subtask_id] = subtask_result_metadata
                    else:
                        # Fallback: считаем успешным если нет ошибки
                        results[subtask_id] = {
                            "status": "completed",
                            "subtask_id": subtask_id
                        }
                    
                except SubtaskExecutionError as e:
                    logger.error(f"Subtask {subtask_id} failed: {e}")
                    errors[subtask_id] = str(e)
                    
                    # Отправить error chunk
                    yield StreamChunk(
                        type="error",
                        error=f"Subtask {subtask_id} failed: {str(e)}",
                        metadata={"subtask_id": subtask_id}
                    )
            
            # Проверить результаты
            completed_count = len(results)
            failed_count = len(errors)
            
            # Перезагрузить план из БД для получения актуальных статусов subtasks
            plan = await self.plan_repository.find_by_id(plan_id)
            if not plan:
                raise ExecutionEngineError(f"Plan {plan_id} not found after execution")
            
            # Обновить статус плана
            if failed_count == 0:
                plan.complete()
                final_status = "completed"
                logger.info(f"Plan {plan_id} completed successfully")
            else:
                plan.fail(f"Failed {failed_count} of {total_count} subtasks")
                final_status = "failed"
                logger.warning(
                    f"Plan {plan_id} failed: {failed_count}/{total_count} "
                    f"subtasks failed"
                )
            
            await self.plan_repository.save(plan)
            
            # Вычислить длительность
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            # Отправить финальный chunk с результатом выполнения плана
            execution_result = ExecutionResult(
                plan_id=plan_id,
                status=final_status,
                completed_subtasks=completed_count,
                failed_subtasks=failed_count,
                total_subtasks=total_count,
                results=results,
                errors=errors,
                duration_seconds=duration
            )
            
            yield StreamChunk(
                type="execution_completed",
                content=f"Plan execution {final_status}",
                metadata=execution_result.to_dict(),
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error executing plan {plan_id}: {e}", exc_info=True)
            
            # Пометить план как failed
            plan.fail(f"Execution error: {str(e)}")
            await self.plan_repository.save(plan)
            
            # Отправить error chunk
            yield StreamChunk(
                type="error",
                error=f"Plan execution failed: {str(e)}",
                metadata={"plan_id": plan_id},
                is_final=True
            )
    
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

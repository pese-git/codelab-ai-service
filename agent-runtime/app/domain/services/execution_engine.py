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
from typing import Dict, Any, List, Optional, Set, TYPE_CHECKING
from datetime import datetime, timezone

from app.domain.entities.plan import Plan, PlanStatus, Subtask, SubtaskStatus
from app.domain.services.dependency_resolver import DependencyResolver
from app.domain.services.subtask_executor import SubtaskExecutor, SubtaskExecutionError

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
    ) -> ExecutionResult:
        """
        Выполнить план.
        
        Args:
            plan_id: ID плана
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Returns:
            Результат выполнения плана
            
        Raises:
            ExecutionEngineError: При ошибке выполнения
        """
        logger.info(f"Starting execution of plan {plan_id}")
        start_time = datetime.now(timezone.utc)
        
        # Получить план
        plan = await self.plan_repository.get_by_id(plan_id)
        if not plan:
            raise ExecutionEngineError(f"Plan {plan_id} not found")
        
        # Проверить статус плана
        if plan.status != PlanStatus.APPROVED:
            raise ExecutionEngineError(
                f"Plan {plan_id} is not approved (status: {plan.status.value})"
            )
        
        # Начать выполнение
        plan.start_execution()
        await self.plan_repository.update(plan)
        
        try:
            # Получить порядок выполнения с учетом зависимостей
            execution_order = self._get_execution_order(plan)
            
            logger.info(
                f"Execution order for plan {plan_id}: "
                f"{len(execution_order)} batches"
            )
            
            # Выполнить подзадачи по батчам
            results = {}
            errors = {}
            
            for batch_index, batch in enumerate(execution_order):
                logger.info(
                    f"Executing batch {batch_index + 1}/{len(execution_order)} "
                    f"with {len(batch)} subtasks"
                )
                
                batch_results = await self._execute_batch(
                    plan=plan,
                    subtask_ids=batch,
                    session_id=session_id,
                    session_service=session_service,
                    stream_handler=stream_handler
                )
                
                # Собрать результаты и ошибки
                for subtask_id, result in batch_results.items():
                    if result["status"] == "completed":
                        results[subtask_id] = result
                    else:
                        errors[subtask_id] = result.get("error", "Unknown error")
            
            # Проверить результаты
            completed_count = len(results)
            failed_count = len(errors)
            total_count = len(plan.subtasks)
            
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
            
            await self.plan_repository.update(plan)
            
            # Вычислить длительность
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            return ExecutionResult(
                plan_id=plan_id,
                status=final_status,
                completed_subtasks=completed_count,
                failed_subtasks=failed_count,
                total_subtasks=total_count,
                results=results,
                errors=errors,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"Error executing plan {plan_id}: {e}", exc_info=True)
            
            # Пометить план как failed
            plan.fail(f"Execution error: {str(e)}")
            await self.plan_repository.update(plan)
            
            raise ExecutionEngineError(
                f"Failed to execute plan {plan_id}: {str(e)}"
            ) from e
    
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
    
    async def _execute_batch(
        self,
        plan: Plan,
        subtask_ids: List[str],
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Выполнить батч подзадач параллельно.
        
        Args:
            plan: План
            subtask_ids: ID подзадач для выполнения
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Returns:
            Словарь результатов по ID подзадач
        """
        logger.info(f"Executing batch of {len(subtask_ids)} subtasks")
        
        # Создать задачи для параллельного выполнения
        tasks = []
        for subtask_id in subtask_ids:
            task = self._execute_subtask_safe(
                plan=plan,
                subtask_id=subtask_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            )
            tasks.append(task)
        
        # Выполнить параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Собрать результаты
        batch_results = {}
        for subtask_id, result in zip(subtask_ids, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Subtask {subtask_id} failed with exception: {result}"
                )
                batch_results[subtask_id] = {
                    "status": "failed",
                    "error": str(result)
                }
            else:
                batch_results[subtask_id] = result
        
        return batch_results
    
    async def _execute_subtask_safe(
        self,
        plan: Plan,
        subtask_id: str,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> Dict[str, Any]:
        """
        Безопасно выполнить подзадачу с обработкой ошибок.
        
        Args:
            plan: План
            subtask_id: ID подзадачи
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Returns:
            Результат выполнения
        """
        subtask = plan.get_subtask_by_id(subtask_id)
        if not subtask:
            return {
                "status": "failed",
                "subtask_id": subtask_id,
                "error": f"Subtask {subtask_id} not found in plan"
            }
        
        try:
            # Начать выполнение подзадачи
            subtask.start()
            await self.plan_repository.update(plan)
            
            # Выполнить подзадачу
            result = await self.subtask_executor.execute_subtask(
                plan_id=plan.id,
                subtask_id=subtask_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            )
            
            # Обновить статус подзадачи в зависимости от результата
            if result.get("status") == "completed":
                result_content = result.get("result", {})
                result_str = str(result_content.get("content", "Completed"))
                subtask.complete(result_str)
            else:
                error_msg = result.get("error", "Unknown error")
                subtask.fail(error_msg)
            
            await self.plan_repository.update(plan)
            return result
            
        except SubtaskExecutionError as e:
            logger.error(f"Subtask {subtask_id} execution error: {e}")
            # Пометить подзадачу как failed
            try:
                if subtask.status == SubtaskStatus.RUNNING:
                    subtask.fail(str(e))
                    await self.plan_repository.update(plan)
            except Exception as update_error:
                logger.error(f"Failed to update subtask status: {update_error}")
            
            return {
                "status": "failed",
                "subtask_id": subtask_id,
                "error": str(e)
            }
        except Exception as e:
            logger.error(
                f"Unexpected error executing subtask {subtask_id}: {e}",
                exc_info=True
            )
            # Пометить подзадачу как failed
            try:
                if subtask.status == SubtaskStatus.RUNNING:
                    subtask.fail(f"Unexpected error: {str(e)}")
                    await self.plan_repository.update(plan)
            except Exception as update_error:
                logger.error(f"Failed to update subtask status: {update_error}")
            
            return {
                "status": "failed",
                "subtask_id": subtask_id,
                "error": f"Unexpected error: {str(e)}"
            }
    
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
        plan = await self.plan_repository.get_by_id(plan_id)
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
        
        plan = await self.plan_repository.get_by_id(plan_id)
        if not plan:
            raise ExecutionEngineError(f"Plan {plan_id} not found")
        
        # Отменить план
        try:
            plan.cancel(reason)
            await self.plan_repository.update(plan)
            
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

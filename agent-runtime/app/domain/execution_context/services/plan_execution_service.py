"""
PlanExecutionService - Domain Service для координации выполнения планов.

Отвечает за:
- Управление жизненным циклом плана
- Координацию выполнения подзадач
- Разрешение зависимостей
- Обработку ошибок и retry logic
- Генерацию Domain Events
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING, AsyncGenerator
from datetime import datetime, timezone

from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus
)
from app.domain.execution_context.entities import ExecutionPlan, Subtask
from app.domain.execution_context.events import (
    PlanExecutionStarted,
    PlanCompleted,
    PlanFailed,
    PlanCancelled
)
from app.domain.execution_context.services.dependency_resolver import DependencyResolver
from app.domain.execution_context.services.subtask_executor import SubtaskExecutor
from app.models.schemas import StreamChunk

if TYPE_CHECKING:
    from app.domain.execution_context.repositories import ExecutionPlanRepository
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.domain.execution_context.plan_execution_service")


class PlanExecutionError(Exception):
    """Ошибка при выполнении плана."""
    
    def __init__(self, message: str, plan_id: Optional[PlanId] = None):
        super().__init__(message)
        self.plan_id = plan_id


class PlanExecutionService:
    """
    Domain Service для координации выполнения планов.
    
    Responsibilities:
    - Управление жизненным циклом плана (start, complete, fail, cancel)
    - Координация выполнения подзадач в правильном порядке
    - Разрешение зависимостей между подзадачами
    - Обработка ошибок и retry logic
    - Генерация Domain Events для трассировки
    - Агрегация результатов выполнения
    
    Attributes:
        plan_repository: Репозиторий для работы с планами
        subtask_executor: Сервис для выполнения подзадач
        dependency_resolver: Сервис для разрешения зависимостей
    """
    
    def __init__(
        self,
        plan_repository: "ExecutionPlanRepository",
        subtask_executor: SubtaskExecutor,
        dependency_resolver: DependencyResolver
    ):
        """
        Инициализация PlanExecutionService.
        
        Args:
            plan_repository: Типобезопасный репозиторий для работы с планами
            subtask_executor: Сервис для выполнения подзадач
            dependency_resolver: Сервис для разрешения зависимостей
        """
        self.plan_repository = plan_repository
        self.subtask_executor = subtask_executor
        self.dependency_resolver = dependency_resolver
        logger.info("PlanExecutionService initialized")
    
    async def start_plan_execution(
        self,
        plan_id: PlanId,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Начать выполнение плана.
        
        Координирует выполнение всех подзадач в правильном порядке
        с учетом зависимостей.
        
        Args:
            plan_id: Typed ID плана
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Yields:
            StreamChunk: Chunks от выполнения подзадач
            
        Raises:
            PlanExecutionError: При ошибке выполнения
        """
        logger.info(f"Starting execution of plan {plan_id.value}")
        
        # Получить план
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise PlanExecutionError(
                f"Plan {plan_id.value} not found",
                plan_id=plan_id
            )
        
        # Проверить статус плана
        if plan.status != PlanStatus.PENDING:
            raise PlanExecutionError(
                f"Plan {plan_id.value} is not in PENDING status "
                f"(current: {plan.status.value})",
                plan_id=plan_id
            )
        
        # Начать выполнение плана
        plan.start()
        
        # Генерация Domain Event
        event = PlanExecutionStarted(
            plan_id=plan_id,
            conversation_id=plan.metadata.get("conversation_id", ""),
            started_at=plan.started_at or datetime.now(timezone.utc)
        )
        plan.add_domain_event(event)
        
        await self.plan_repository.save(plan)
        
        # Отправить начальный chunk
        yield StreamChunk(
            type="plan_started",
            content=f"Plan {plan_id.value} execution started",
            metadata={
                "plan_id": plan_id.value,
                "goal": plan.goal,
                "subtask_count": len(plan.subtasks),
                "status": "in_progress"
            },
            is_final=False
        )
        
        try:
            # Получить порядок выполнения подзадач
            execution_order = self.dependency_resolver.resolve_execution_order(plan)
            
            logger.info(
                f"Execution order for plan {plan_id.value}: "
                f"{[st.id.value for st in execution_order]}"
            )
            
            # Выполнить подзадачи в порядке
            for subtask in execution_order:
                logger.info(
                    f"Executing subtask {subtask.id.value} "
                    f"(agent: {subtask.agent.value})"
                )
                
                # Выполнить подзадачу и пересылать chunks
                async for chunk in self.subtask_executor.execute_subtask(
                    plan_id=plan_id,
                    subtask_id=subtask.id,
                    session_id=session_id,
                    session_service=session_service,
                    stream_handler=stream_handler
                ):
                    yield chunk
                
                # Перезагрузить план для получения актуального статуса
                plan = await self.plan_repository.find_by_id(plan_id)
                if not plan:
                    raise PlanExecutionError(
                        f"Plan {plan_id.value} not found after subtask execution",
                        plan_id=plan_id
                    )
                
                # Проверить статус подзадачи
                updated_subtask = plan.get_subtask_by_id(subtask.id)
                if not updated_subtask:
                    raise PlanExecutionError(
                        f"Subtask {subtask.id.value} not found after execution",
                        plan_id=plan_id
                    )
                
                if updated_subtask.status == SubtaskStatus.FAILED:
                    logger.error(
                        f"Subtask {subtask.id.value} failed, "
                        f"stopping plan execution"
                    )
                    # План будет помечен как failed в блоке except
                    raise PlanExecutionError(
                        f"Subtask {subtask.id.value} failed: {updated_subtask.error}",
                        plan_id=plan_id
                    )
            
            # Все подзадачи выполнены успешно
            plan.complete()
            
            # Генерация Domain Event
            event = PlanCompleted(
                plan_id=plan_id,
                completed_at=plan.completed_at or datetime.now(timezone.utc),
                total_subtasks=len(plan.subtasks),
                successful_subtasks=len([
                    st for st in plan.subtasks
                    if st.status == SubtaskStatus.DONE
                ])
            )
            plan.add_domain_event(event)
            
            await self.plan_repository.save(plan)
            
            logger.info(f"Plan {plan_id.value} completed successfully")
            
            # Отправить финальный chunk
            yield StreamChunk(
                type="plan_completed",
                content=f"Plan {plan_id.value} completed successfully",
                metadata={
                    "plan_id": plan_id.value,
                    "status": "completed",
                    "subtask_count": len(plan.subtasks),
                    "started_at": plan.started_at.isoformat() if plan.started_at else None,
                    "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
                    "duration_seconds": self._calculate_duration(plan)
                },
                is_final=True
            )
        
        except Exception as e:
            logger.error(
                f"Error executing plan {plan_id.value}: {e}",
                exc_info=True
            )
            
            # Перезагрузить план для получения актуального статуса
            plan = await self.plan_repository.find_by_id(plan_id)
            if plan and plan.status not in [PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED]:
                error_message = f"{type(e).__name__}: {str(e)}"
                plan.fail(error=error_message)
                
                # Генерация Domain Event
                event = PlanFailed(
                    plan_id=plan_id,
                    error=error_message,
                    failed_at=datetime.now(timezone.utc),
                    completed_subtasks=len([
                        st for st in plan.subtasks
                        if st.status == SubtaskStatus.DONE
                    ]),
                    total_subtasks=len(plan.subtasks)
                )
                plan.add_domain_event(event)
                
                await self.plan_repository.save(plan)
                logger.info(f"Plan {plan_id.value} marked as failed")
            
            # Отправить error chunk
            yield StreamChunk(
                type="error",
                error=f"Plan execution failed: {str(e)}",
                metadata={
                    "plan_id": plan_id.value,
                    "status": "failed"
                },
                is_final=True
            )
    
    async def cancel_plan_execution(
        self,
        plan_id: PlanId,
        reason: str = "User cancelled"
    ) -> None:
        """
        Отменить выполнение плана.
        
        Args:
            plan_id: Typed ID плана
            reason: Причина отмены
            
        Raises:
            PlanExecutionError: При ошибке
        """
        logger.info(f"Cancelling plan {plan_id.value}: {reason}")
        
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise PlanExecutionError(
                f"Plan {plan_id.value} not found",
                plan_id=plan_id
            )
        
        # Проверить, что план можно отменить
        if plan.status in [PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED]:
            raise PlanExecutionError(
                f"Cannot cancel plan {plan_id.value} in status {plan.status.value}",
                plan_id=plan_id
            )
        
        # Отменить план
        plan.cancel()
        
        # Генерация Domain Event
        event = PlanCancelled(
            plan_id=plan_id,
            reason=reason,
            cancelled_at=datetime.now(timezone.utc),
            completed_subtasks=len([
                st for st in plan.subtasks
                if st.status == SubtaskStatus.DONE
            ]),
            total_subtasks=len(plan.subtasks)
        )
        plan.add_domain_event(event)
        
        await self.plan_repository.save(plan)
        
        logger.info(f"Plan {plan_id.value} cancelled")
    
    async def get_plan_status(
        self,
        plan_id: PlanId
    ) -> Dict[str, Any]:
        """
        Получить статус выполнения плана.
        
        Args:
            plan_id: Typed ID плана
            
        Returns:
            Информация о статусе плана
            
        Raises:
            PlanExecutionError: Если план не найден
        """
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise PlanExecutionError(
                f"Plan {plan_id.value} not found",
                plan_id=plan_id
            )
        
        # Подсчитать статистику по подзадачам
        subtask_stats = {
            "total": len(plan.subtasks),
            "pending": len([st for st in plan.subtasks if st.status == SubtaskStatus.PENDING]),
            "in_progress": len([st for st in plan.subtasks if st.status == SubtaskStatus.IN_PROGRESS]),
            "done": len([st for st in plan.subtasks if st.status == SubtaskStatus.DONE]),
            "failed": len([st for st in plan.subtasks if st.status == SubtaskStatus.FAILED])
        }
        
        return {
            "plan_id": plan.id.value,
            "goal": plan.goal,
            "status": plan.status.value,
            "subtask_stats": subtask_stats,
            "started_at": plan.started_at.isoformat() if plan.started_at else None,
            "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
            "duration_seconds": self._calculate_duration(plan),
            "error": plan.error,
            "subtasks": [
                {
                    "id": st.id.value,
                    "description": st.description,
                    "agent": st.agent.value,
                    "status": st.status.value,
                    "dependencies": [dep.value for dep in st.dependencies],
                    "error": st.error
                }
                for st in plan.subtasks
            ]
        }
    
    async def get_next_executable_subtasks(
        self,
        plan_id: PlanId
    ) -> List[Subtask]:
        """
        Получить список подзадач, готовых к выполнению.
        
        Подзадача готова к выполнению, если:
        - Её статус PENDING
        - Все её зависимости выполнены (статус DONE)
        
        Args:
            plan_id: Typed ID плана
            
        Returns:
            Список подзадач, готовых к выполнению
            
        Raises:
            PlanExecutionError: Если план не найден
        """
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise PlanExecutionError(
                f"Plan {plan_id.value} not found",
                plan_id=plan_id
            )
        
        executable_subtasks = []
        
        for subtask in plan.subtasks:
            if subtask.status != SubtaskStatus.PENDING:
                continue
            
            # Проверить, что все зависимости выполнены
            all_deps_done = all(
                plan.get_subtask_by_id(dep_id).status == SubtaskStatus.DONE
                for dep_id in subtask.dependencies
                if plan.get_subtask_by_id(dep_id) is not None
            )
            
            if all_deps_done:
                executable_subtasks.append(subtask)
        
        return executable_subtasks
    
    def _calculate_duration(self, plan: ExecutionPlan) -> Optional[float]:
        """
        Вычислить длительность выполнения плана.
        
        Args:
            plan: План выполнения
            
        Returns:
            Длительность в секундах или None
        """
        if plan.started_at and plan.completed_at:
            delta = plan.completed_at - plan.started_at
            return delta.total_seconds()
        return None

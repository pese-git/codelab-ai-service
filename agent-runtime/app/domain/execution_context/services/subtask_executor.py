"""
SubtaskExecutor - Domain Service для выполнения подзадач в целевых агентах.

Рефакторенная версия с использованием Value Objects и типобезопасности.

Responsibilities:
- Маршрутизация подзадач к агентам по типу
- Выполнение подзадач через agent.process()
- Сбор результатов выполнения
- Обновление статусов через Repository
- Error handling и retry logic
- Генерация Domain Events
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING, AsyncGenerator
from datetime import datetime, timezone

from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    SubtaskStatus
)
from app.domain.execution_context.entities import Subtask, ExecutionPlan
from app.domain.execution_context.events import (
    SubtaskStarted,
    SubtaskCompleted,
    SubtaskFailed,
    SubtaskRetried
)
from app.domain.agent_context.value_objects.agent_capabilities import AgentType
from app.domain.services.agent_registry import agent_registry
from app.models.schemas import StreamChunk

if TYPE_CHECKING:
    from app.domain.execution_context.repositories import ExecutionPlanRepository
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.domain.execution_context.subtask_executor")


class SubtaskExecutionError(Exception):
    """Ошибка при выполнении подзадачи."""
    
    def __init__(self, message: str, subtask_id: Optional[SubtaskId] = None):
        super().__init__(message)
        self.subtask_id = subtask_id


class SubtaskExecutor:
    """
    Domain Service для выполнения подзадач в целевых агентах.
    
    Рефакторенная версия с использованием:
    - Value Objects (PlanId, SubtaskId, SubtaskStatus)
    - Типобезопасный Repository interface
    - Domain Events для трассировки
    - Явная семантика через типы
    
    Attributes:
        plan_repository: Репозиторий для работы с планами
        max_retries: Максимальное количество попыток при ошибке
    """
    
    def __init__(
        self,
        plan_repository: "ExecutionPlanRepository",
        max_retries: int = 3
    ):
        """
        Инициализация SubtaskExecutor.
        
        Args:
            plan_repository: Типобезопасный репозиторий для работы с планами
            max_retries: Максимальное количество попыток при ошибке
        """
        self.plan_repository = plan_repository
        self.max_retries = max_retries
        logger.info(
            f"SubtaskExecutor initialized with max_retries={max_retries}"
        )
    
    async def execute_subtask(
        self,
        plan_id: PlanId,
        subtask_id: SubtaskId,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить подзадачу в целевом агенте.
        
        Возвращает AsyncGenerator для пересылки chunks от агента.
        Это позволяет tool_call событиям доходить до клиента через SSE.
        
        Args:
            plan_id: Typed ID плана
            subtask_id: Typed ID подзадачи
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Yields:
            StreamChunk: Chunks от агента (включая tool_call, assistant_message, etc.)
            
        Raises:
            SubtaskExecutionError: При ошибке выполнения
        """
        logger.info(
            f"Starting execution of subtask {subtask_id.value} "
            f"from plan {plan_id.value}"
        )
        
        # Получить план и подзадачу
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise SubtaskExecutionError(
                f"Plan {plan_id.value} not found",
                subtask_id=subtask_id
            )
        
        subtask = plan.get_subtask_by_id(subtask_id)
        if not subtask:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id.value} not found in plan {plan_id.value}",
                subtask_id=subtask_id
            )
        
        # Проверить статус подзадачи
        if subtask.status != SubtaskStatus.PENDING:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id.value} is not in PENDING status "
                f"(current: {subtask.status.value})",
                subtask_id=subtask_id
            )
        
        # Начать выполнение
        subtask.start()
        
        # Генерация Domain Event
        event = SubtaskStarted(
            subtask_id=subtask_id,
            plan_id=plan_id,
            agent_type=subtask.agent,
            started_at=subtask.started_at or datetime.now(timezone.utc)
        )
        plan.add_domain_event(event)
        
        await self.plan_repository.save(plan)
        
        # Подготовить контекст для агента
        context = self._prepare_agent_context(subtask, plan)
        
        # Создать изолированный контекст для subtask
        # Это предотвращает дублирование tool_call_id между subtasks
        snapshot_id = await session_service.create_subtask_context(
            session_id=session_id,
            subtask_id=subtask_id.value,
            dependency_results=context.get("dependencies", {})
        )
        
        logger.info(
            f"Created isolated context for subtask {subtask_id.value} "
            f"(snapshot: {snapshot_id})"
        )
        
        try:
            # Получить целевого агента
            agent = self._get_agent_for_subtask(subtask)
            
            logger.info(
                f"Routing subtask {subtask_id.value} to {subtask.agent.value} agent"
            )
            
            # Получить сессию (уже с очищенной историей)
            session = await session_service.get_session(session_id)
            if not session:
                raise SubtaskExecutionError(
                    f"Session {session_id} not found",
                    subtask_id=subtask_id
                )
            
            # Выполнить подзадачу через агента
            result_chunks = []
            async for chunk in agent.process(
                session_id=session_id,
                message=subtask.description,
                context=context,
                session=session,
                session_service=session_service,
                stream_handler=stream_handler
            ):
                result_chunks.append(chunk)
                
                # Пересылать chunk дальше через yield
                # Это позволяет tool_call событиям доходить до клиента через SSE
                yield chunk
                
                logger.debug(
                    f"Forwarded chunk from agent: type={chunk.type}, "
                    f"is_final={chunk.is_final}"
                )
            
            # Собрать результат
            result = self._collect_result(result_chunks)
            
            # Проверить наличие ошибок в chunks
            has_error = any(
                chunk.type == "error"
                for chunk in result_chunks
                if isinstance(chunk, StreamChunk)
            )
            
            # Также проверить, содержит ли результат текст ошибки LLM
            has_llm_error = (
                "[Error]" in result.get("content", "") or
                "LiteLLM proxy unavailable" in result.get("content", "") or
                "No tool output found" in result.get("content", "")
            )
            
            if has_error or has_llm_error:
                # Найти error chunk или извлечь ошибку из content
                if has_error:
                    error_chunk = next(
                        (chunk for chunk in result_chunks
                         if isinstance(chunk, StreamChunk) and chunk.type == "error"),
                        None
                    )
                    error_message = error_chunk.error if error_chunk else "Subtask failed with error"
                else:
                    # Ошибка LLM в assistant message
                    error_message = result.get("content", "Subtask failed with LLM error")[:500]
                
                # Завершить подзадачу с ошибкой
                subtask.fail(error=error_message)
                
                # Генерация Domain Event
                event = SubtaskFailed(
                    subtask_id=subtask_id,
                    plan_id=plan_id,
                    error=error_message,
                    failed_at=subtask.completed_at or datetime.now(timezone.utc)
                )
                plan.add_domain_event(event)
                
                await self.plan_repository.save(plan)
                
                logger.error(
                    f"Subtask {subtask_id.value} failed: {error_message[:200]}..."
                )
                
                # Отправить финальный chunk с ошибкой
                yield StreamChunk(
                    type="error",
                    error=error_message,
                    metadata={
                        "subtask_id": subtask_id.value,
                        "status": "failed",
                        "agent": subtask.agent.value
                    },
                    is_final=True
                )
            else:
                # Завершить подзадачу успешно
                subtask.complete(result=result["content"])
                
                # Генерация Domain Event
                event = SubtaskCompleted(
                    subtask_id=subtask_id,
                    plan_id=plan_id,
                    result=result["content"],
                    completed_at=subtask.completed_at or datetime.now(timezone.utc)
                )
                plan.add_domain_event(event)
                
                await self.plan_repository.save(plan)
                
                logger.info(
                    f"Subtask {subtask_id.value} completed successfully "
                    f"by {subtask.agent.value} agent"
                )
                
                # Отправить финальный chunk с результатом выполнения подзадачи
                yield StreamChunk(
                    type="subtask_completed",
                    content=f"Subtask {subtask_id.value} completed",
                    metadata={
                        "subtask_id": subtask_id.value,
                        "status": "completed",
                        "result": result,
                        "agent": subtask.agent.value,
                        "started_at": subtask.started_at.isoformat() if subtask.started_at else None,
                        "completed_at": subtask.completed_at.isoformat() if subtask.completed_at else None,
                        "duration_seconds": self._calculate_duration(subtask)
                    },
                    is_final=True
                )
        
        except Exception as e:
            logger.error(
                f"Error executing subtask {subtask_id.value}: {e}",
                exc_info=True
            )
            
            # Завершить подзадачу с ошибкой только если она еще не завершена
            error_message = f"{type(e).__name__}: {str(e)}"
            
            # Перезагрузить план для получения актуального статуса
            plan = await self.plan_repository.find_by_id(plan_id)
            if plan:
                subtask = plan.get_subtask_by_id(subtask_id)
                if subtask and subtask.status not in [SubtaskStatus.DONE, SubtaskStatus.FAILED]:
                    subtask.fail(error=error_message)
                    
                    # Генерация Domain Event
                    event = SubtaskFailed(
                        subtask_id=subtask_id,
                        plan_id=plan_id,
                        error=error_message,
                        failed_at=datetime.now(timezone.utc)
                    )
                    plan.add_domain_event(event)
                    
                    await self.plan_repository.save(plan)
                    logger.info(f"Subtask {subtask_id.value} marked as failed")
                else:
                    logger.warning(
                        f"Subtask {subtask_id.value} already in terminal status "
                        f"({subtask.status.value if subtask else 'not found'}), "
                        f"skipping fail() call"
                    )
            
            # Отправить error chunk
            yield StreamChunk(
                type="error",
                error=error_message,
                metadata={
                    "subtask_id": subtask_id.value,
                    "status": "failed"
                },
                is_final=True
            )
        
        finally:
            # Восстановить сессию из snapshot
            # Это восстанавливает базовую историю и сохраняет результат subtask
            try:
                await session_service.restore_from_snapshot(
                    session_id=session_id,
                    snapshot_id=snapshot_id,
                    preserve_last_result=True
                )
                
                logger.info(
                    f"Restored session {session_id} from snapshot {snapshot_id} "
                    f"after subtask {subtask_id.value}"
                )
            except Exception as restore_error:
                logger.error(
                    f"Error restoring snapshot {snapshot_id}: {restore_error}",
                    exc_info=True
                )
                # Не прерываем выполнение, так как subtask уже завершена
    
    def _get_agent_for_subtask(self, subtask: Subtask):
        """
        Получить агента для выполнения подзадачи.
        
        Args:
            subtask: Подзадача
            
        Returns:
            Экземпляр агента
            
        Raises:
            SubtaskExecutionError: Если агент не найден
        """
        try:
            agent = agent_registry.get_agent(subtask.agent)
            return agent
        except ValueError as e:
            raise SubtaskExecutionError(
                f"Agent {subtask.agent.value} not available: {e}",
                subtask_id=subtask.id
            ) from e
    
    def _prepare_agent_context(
        self,
        subtask: Subtask,
        plan: ExecutionPlan
    ) -> Dict[str, Any]:
        """
        Подготовить контекст для агента.
        
        Args:
            subtask: Подзадача
            plan: План выполнения
            
        Returns:
            Контекст для агента
        """
        # Получить результаты зависимостей
        dependency_results = {}
        for dep_id in subtask.dependencies:
            dep_subtask = plan.get_subtask_by_id(dep_id)
            if dep_subtask and dep_subtask.status == SubtaskStatus.DONE:
                dependency_results[dep_id.value] = {
                    "description": dep_subtask.description,
                    "result": dep_subtask.result,
                    "agent": dep_subtask.agent.value
                }
        
        return {
            "subtask_id": subtask.id.value,
            "plan_id": plan.id.value,
            "plan_goal": plan.goal,
            "dependencies": dependency_results,
            "metadata": subtask.metadata,
            "execution_mode": "subtask"
        }
    
    def _collect_result(self, chunks: list) -> Dict[str, Any]:
        """
        Собрать результат из chunks.
        
        Args:
            chunks: Список StreamChunk
            
        Returns:
            Агрегированный результат
        """
        content_parts = []
        metadata = {}
        
        for chunk in chunks:
            if isinstance(chunk, StreamChunk):
                if chunk.content:
                    content_parts.append(chunk.content)
                if chunk.metadata:
                    metadata.update(chunk.metadata)
        
        return {
            "content": "\n".join(content_parts),
            "metadata": metadata,
            "chunk_count": len(chunks)
        }
    
    def _calculate_duration(self, subtask: Subtask) -> Optional[float]:
        """
        Вычислить длительность выполнения подзадачи.
        
        Args:
            subtask: Подзадача
            
        Returns:
            Длительность в секундах или None
        """
        if subtask.started_at and subtask.completed_at:
            delta = subtask.completed_at - subtask.started_at
            return delta.total_seconds()
        return None
    
    async def retry_failed_subtask(
        self,
        plan_id: PlanId,
        subtask_id: SubtaskId,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Повторить выполнение неудавшейся подзадачи.
        
        Args:
            plan_id: Typed ID плана
            subtask_id: Typed ID подзадачи
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Yields:
            StreamChunk: Chunks от агента
            
        Raises:
            SubtaskExecutionError: При ошибке
        """
        logger.info(f"Retrying failed subtask {subtask_id.value}")
        
        # Получить план и подзадачу
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise SubtaskExecutionError(
                f"Plan {plan_id.value} not found",
                subtask_id=subtask_id
            )
        
        subtask = plan.get_subtask_by_id(subtask_id)
        if not subtask:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id.value} not found in plan {plan_id.value}",
                subtask_id=subtask_id
            )
        
        # Проверить, что подзадача в статусе FAILED
        if subtask.status != SubtaskStatus.FAILED:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id.value} is not in FAILED status "
                f"(current: {subtask.status.value})",
                subtask_id=subtask_id
            )
        
        # Сбросить статус на PENDING
        subtask.reset_to_pending()
        
        # Генерация Domain Event
        event = SubtaskRetried(
            subtask_id=subtask_id,
            plan_id=plan_id,
            retry_count=subtask.metadata.get("retry_count", 0) + 1,
            retried_at=datetime.now(timezone.utc)
        )
        plan.add_domain_event(event)
        
        # Обновить счетчик попыток
        if "retry_count" not in subtask.metadata:
            subtask.metadata["retry_count"] = 0
        subtask.metadata["retry_count"] += 1
        
        await self.plan_repository.save(plan)
        
        # Выполнить заново и пересылать chunks
        async for chunk in self.execute_subtask(
            plan_id=plan_id,
            subtask_id=subtask_id,
            session_id=session_id,
            session_service=session_service,
            stream_handler=stream_handler
        ):
            yield chunk
    
    async def get_subtask_status(
        self,
        plan_id: PlanId,
        subtask_id: SubtaskId
    ) -> Dict[str, Any]:
        """
        Получить статус подзадачи.
        
        Args:
            plan_id: Typed ID плана
            subtask_id: Typed ID подзадачи
            
        Returns:
            Информация о статусе подзадачи
            
        Raises:
            SubtaskExecutionError: Если план или подзадача не найдены
        """
        plan = await self.plan_repository.find_by_id(plan_id)
        if not plan:
            raise SubtaskExecutionError(
                f"Plan {plan_id.value} not found",
                subtask_id=subtask_id
            )
        
        subtask = plan.get_subtask_by_id(subtask_id)
        if not subtask:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id.value} not found in plan {plan_id.value}",
                subtask_id=subtask_id
            )
        
        return {
            "subtask_id": subtask.id.value,
            "description": subtask.description,
            "agent": subtask.agent.value,
            "status": subtask.status.value,
            "dependencies": [dep.value for dep in subtask.dependencies],
            "result": subtask.result,
            "error": subtask.error,
            "started_at": subtask.started_at.isoformat() if subtask.started_at else None,
            "completed_at": subtask.completed_at.isoformat() if subtask.completed_at else None,
            "duration_seconds": self._calculate_duration(subtask),
            "retry_count": subtask.metadata.get("retry_count", 0)
        }

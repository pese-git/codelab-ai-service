"""
SubtaskExecutor - сервис для выполнения подзадач в целевых агентах.

Отвечает за:
- Маршрутизацию подзадач к соответствующим агентам
- Выполнение подзадач через agent.process()
- Обработку результатов и ошибок
- Обновление статусов в репозитории
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone

from app.domain.entities.plan import Subtask, SubtaskStatus
from app.domain.entities.agent_context import AgentType
from app.domain.services.agent_registry import agent_registry
from app.models.schemas import StreamChunk

if TYPE_CHECKING:
    from app.domain.repositories.plan_repository import PlanRepository
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.domain.subtask_executor")


class SubtaskExecutionError(Exception):
    """Ошибка при выполнении подзадачи"""
    pass


class SubtaskExecutor:
    """
    Сервис для выполнения подзадач в целевых агентах.
    
    Responsibilities:
    - Маршрутизация подзадач к агентам по типу
    - Выполнение подзадач через agent.process()
    - Сбор результатов выполнения
    - Обновление статусов в репозитории
    - Error handling и retry logic
    
    Attributes:
        plan_repository: Репозиторий для работы с планами
        max_retries: Максимальное количество попыток при ошибке
    """
    
    def __init__(
        self,
        plan_repository: "PlanRepository",
        max_retries: int = 3
    ):
        """
        Инициализация SubtaskExecutor.
        
        Args:
            plan_repository: Репозиторий для работы с планами
            max_retries: Максимальное количество попыток при ошибке
        """
        self.plan_repository = plan_repository
        self.max_retries = max_retries
        logger.info(
            f"SubtaskExecutor initialized with max_retries={max_retries}"
        )
    
    async def execute_subtask(
        self,
        plan_id: str,
        subtask_id: str,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> Dict[str, Any]:
        """
        Выполнить подзадачу в целевом агенте.
        
        Args:
            plan_id: ID плана
            subtask_id: ID подзадачи
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Returns:
            Результат выполнения с метаданными
            
        Raises:
            SubtaskExecutionError: При ошибке выполнения
        """
        logger.info(
            f"Starting execution of subtask {subtask_id} "
            f"from plan {plan_id}"
        )
        
        # Получить план и подзадачу
        plan = await self.plan_repository.get_by_id(plan_id)
        if not plan:
            raise SubtaskExecutionError(f"Plan {plan_id} not found")
        
        subtask = plan.get_subtask_by_id(subtask_id)
        if not subtask:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id} not found in plan {plan_id}"
            )
        
        # Проверить статус подзадачи
        if subtask.status != SubtaskStatus.PENDING:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id} is not in PENDING status "
                f"(current: {subtask.status.value})"
            )
        
        # Начать выполнение
        subtask.start()
        await self.plan_repository.update(plan)
        
        try:
            # Получить целевого агента
            agent = self._get_agent_for_subtask(subtask)
            
            logger.info(
                f"Routing subtask {subtask_id} to {subtask.agent.value} agent"
            )
            
            # Получить сессию
            session = await session_service.get_session(session_id)
            if not session:
                raise SubtaskExecutionError(f"Session {session_id} not found")
            
            # Подготовить контекст для агента
            context = self._prepare_agent_context(subtask, plan)
            
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
                # Можно стримить прогресс через stream_handler
            
            # Собрать результат
            result = self._collect_result(result_chunks)
            
            # Завершить подзадачу успешно
            subtask.complete(result=result["content"])
            await self.plan_repository.update(plan)
            
            logger.info(
                f"Subtask {subtask_id} completed successfully "
                f"by {subtask.agent.value} agent"
            )
            
            return {
                "subtask_id": subtask_id,
                "status": "completed",
                "result": result,
                "agent": subtask.agent.value,
                "started_at": subtask.started_at.isoformat() if subtask.started_at else None,
                "completed_at": subtask.completed_at.isoformat() if subtask.completed_at else None,
                "duration_seconds": self._calculate_duration(subtask)
            }
            
        except Exception as e:
            logger.error(
                f"Error executing subtask {subtask_id}: {e}",
                exc_info=True
            )
            
            # Завершить подзадачу с ошибкой
            error_message = f"{type(e).__name__}: {str(e)}"
            subtask.fail(error=error_message)
            await self.plan_repository.update(plan)
            
            raise SubtaskExecutionError(
                f"Failed to execute subtask {subtask_id}: {error_message}"
            ) from e
    
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
                f"Agent {subtask.agent.value} not available: {e}"
            ) from e
    
    def _prepare_agent_context(
        self,
        subtask: Subtask,
        plan
    ) -> Dict[str, Any]:
        """
        Подготовить контекст для агента.
        
        Args:
            subtask: Подзадача
            plan: План
            
        Returns:
            Контекст для агента
        """
        # Получить результаты зависимостей
        dependency_results = {}
        for dep_id in subtask.dependencies:
            dep_subtask = plan.get_subtask_by_id(dep_id)
            if dep_subtask and dep_subtask.status == SubtaskStatus.DONE:
                dependency_results[dep_id] = {
                    "description": dep_subtask.description,
                    "result": dep_subtask.result,
                    "agent": dep_subtask.agent.value
                }
        
        return {
            "subtask_id": subtask.id,
            "plan_id": plan.id,
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
        plan_id: str,
        subtask_id: str,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> Dict[str, Any]:
        """
        Повторить выполнение неудавшейся подзадачи.
        
        Args:
            plan_id: ID плана
            subtask_id: ID подзадачи
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Returns:
            Результат выполнения
            
        Raises:
            SubtaskExecutionError: При ошибке
        """
        logger.info(f"Retrying failed subtask {subtask_id}")
        
        # Получить план и подзадачу
        plan = await self.plan_repository.get_by_id(plan_id)
        if not plan:
            raise SubtaskExecutionError(f"Plan {plan_id} not found")
        
        subtask = plan.get_subtask_by_id(subtask_id)
        if not subtask:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id} not found in plan {plan_id}"
            )
        
        # Проверить, что подзадача в статусе FAILED
        if subtask.status != SubtaskStatus.FAILED:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id} is not in FAILED status "
                f"(current: {subtask.status.value})"
            )
        
        # Сбросить статус на PENDING
        subtask.status = SubtaskStatus.PENDING
        subtask.error = None
        subtask.started_at = None
        subtask.completed_at = None
        await self.plan_repository.update(plan)
        
        # Выполнить заново
        return await self.execute_subtask(
            plan_id=plan_id,
            subtask_id=subtask_id,
            session_id=session_id,
            session_service=session_service,
            stream_handler=stream_handler
        )
    
    async def get_subtask_status(
        self,
        plan_id: str,
        subtask_id: str
    ) -> Dict[str, Any]:
        """
        Получить статус подзадачи.
        
        Args:
            plan_id: ID плана
            subtask_id: ID подзадачи
            
        Returns:
            Информация о статусе подзадачи
            
        Raises:
            SubtaskExecutionError: Если план или подзадача не найдены
        """
        plan = await self.plan_repository.get_by_id(plan_id)
        if not plan:
            raise SubtaskExecutionError(f"Plan {plan_id} not found")
        
        subtask = plan.get_subtask_by_id(subtask_id)
        if not subtask:
            raise SubtaskExecutionError(
                f"Subtask {subtask_id} not found in plan {plan_id}"
            )
        
        return {
            "subtask_id": subtask.id,
            "description": subtask.description,
            "agent": subtask.agent.value,
            "status": subtask.status.value,
            "dependencies": subtask.dependencies,
            "result": subtask.result,
            "error": subtask.error,
            "started_at": subtask.started_at.isoformat() if subtask.started_at else None,
            "completed_at": subtask.completed_at.isoformat() if subtask.completed_at else None,
            "duration_seconds": self._calculate_duration(subtask)
        }

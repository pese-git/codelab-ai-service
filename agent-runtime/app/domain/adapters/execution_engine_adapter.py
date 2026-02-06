"""
ExecutionEngineAdapter - Адаптер для обратной совместимости с ExecutionEngine.

Делегирует вызовы в PlanExecutionService из новой архитектуры,
обеспечивая совместимость с legacy кодом.
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING, AsyncGenerator

from app.domain.execution_context.value_objects import PlanId
from app.domain.execution_context.services.plan_execution_service import (
    PlanExecutionService,
    PlanExecutionError
)
from app.models.schemas import StreamChunk

if TYPE_CHECKING:
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.domain.adapters.execution_engine_adapter")


class ExecutionEngineError(Exception):
    """Ошибка ExecutionEngine (для обратной совместимости)."""
    pass


class ExecutionResult:
    """
    Результат выполнения плана (для обратной совместимости).
    
    Attributes:
        plan_id: ID плана
        status: Статус выполнения
        completed_subtasks: Количество завершенных подзадач
        failed_subtasks: Количество проваленных подзадач
        total_subtasks: Общее количество подзадач
        results: Результаты выполнения подзадач
        errors: Ошибки выполнения
        duration_seconds: Длительность выполнения в секундах
    """
    
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
        """Преобразовать в словарь."""
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


class ExecutionEngineAdapter:
    """
    Адаптер для обратной совместимости с ExecutionEngine.
    
    Делегирует все вызовы в PlanExecutionService из новой DDD-архитектуры,
    обеспечивая совместимость с существующим кодом.
    
    Responsibilities:
    - Адаптация интерфейса ExecutionEngine к PlanExecutionService
    - Конвертация типов (str -> PlanId, legacy entities -> new entities)
    - Обработка ошибок и их преобразование
    - Поддержка streaming выполнения
    
    Attributes:
        plan_execution_service: Новый сервис выполнения планов
    
    Example:
        >>> adapter = ExecutionEngineAdapter(plan_execution_service)
        >>> async for chunk in adapter.execute_plan(
        ...     plan_id="plan-123",
        ...     session_id="session-456",
        ...     session_service=session_service,
        ...     stream_handler=stream_handler
        ... ):
        ...     print(chunk)
    """
    
    def __init__(self, plan_execution_service: PlanExecutionService):
        """
        Инициализация ExecutionEngineAdapter.
        
        Args:
            plan_execution_service: Сервис выполнения планов из новой архитектуры
        """
        self.plan_execution_service = plan_execution_service
        logger.info("ExecutionEngineAdapter initialized (delegates to PlanExecutionService)")
    
    async def execute_plan(
        self,
        plan_id: str,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить план (адаптированный метод).
        
        Делегирует выполнение в PlanExecutionService.start_plan_execution(),
        конвертируя типы и обрабатывая ошибки.
        
        Args:
            plan_id: ID плана (str)
            session_id: ID сессии
            session_service: Сервис управления сессиями
            stream_handler: Handler для стриминга
            
        Yields:
            StreamChunk: Chunks от выполнения подзадач
            
        Raises:
            ExecutionEngineError: При ошибке выполнения
        """
        logger.info(f"[Adapter] Executing plan {plan_id} via PlanExecutionService")
        
        try:
            # Конвертировать str -> PlanId
            typed_plan_id = PlanId(plan_id)
            
            # Делегировать в новый сервис
            async for chunk in self.plan_execution_service.start_plan_execution(
                plan_id=typed_plan_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            ):
                yield chunk
        
        except PlanExecutionError as e:
            # Конвертировать ошибку для обратной совместимости
            logger.error(f"[Adapter] Plan execution failed: {e}")
            raise ExecutionEngineError(str(e)) from e
        
        except Exception as e:
            logger.error(f"[Adapter] Unexpected error: {e}", exc_info=True)
            raise ExecutionEngineError(f"Unexpected error: {e}") from e
    
    async def get_execution_status(
        self,
        plan_id: str
    ) -> Dict[str, Any]:
        """
        Получить статус выполнения плана (адаптированный метод).
        
        Делегирует в PlanExecutionService.get_plan_status(),
        конвертируя типы.
        
        Args:
            plan_id: ID плана (str)
            
        Returns:
            Информация о статусе плана
            
        Raises:
            ExecutionEngineError: Если план не найден
        """
        logger.debug(f"[Adapter] Getting status for plan {plan_id}")
        
        try:
            # Конвертировать str -> PlanId
            typed_plan_id = PlanId(plan_id)
            
            # Делегировать в новый сервис
            status = await self.plan_execution_service.get_plan_status(typed_plan_id)
            
            return status
        
        except PlanExecutionError as e:
            logger.error(f"[Adapter] Failed to get plan status: {e}")
            raise ExecutionEngineError(str(e)) from e
        
        except Exception as e:
            logger.error(f"[Adapter] Unexpected error: {e}", exc_info=True)
            raise ExecutionEngineError(f"Unexpected error: {e}") from e
    
    async def cancel_execution(
        self,
        plan_id: str,
        reason: str = "User cancelled"
    ) -> None:
        """
        Отменить выполнение плана (адаптированный метод).
        
        Делегирует в PlanExecutionService.cancel_plan_execution(),
        конвертируя типы.
        
        Args:
            plan_id: ID плана (str)
            reason: Причина отмены
            
        Raises:
            ExecutionEngineError: При ошибке
        """
        logger.info(f"[Adapter] Cancelling plan {plan_id}: {reason}")
        
        try:
            # Конвертировать str -> PlanId
            typed_plan_id = PlanId(plan_id)
            
            # Делегировать в новый сервис
            await self.plan_execution_service.cancel_plan_execution(
                plan_id=typed_plan_id,
                reason=reason
            )
        
        except PlanExecutionError as e:
            logger.error(f"[Adapter] Failed to cancel plan: {e}")
            raise ExecutionEngineError(str(e)) from e
        
        except Exception as e:
            logger.error(f"[Adapter] Unexpected error: {e}", exc_info=True)
            raise ExecutionEngineError(f"Unexpected error: {e}") from e
    
    async def get_next_executable_subtasks(
        self,
        plan_id: str
    ) -> list:
        """
        Получить список подзадач, готовых к выполнению (адаптированный метод).
        
        Делегирует в PlanExecutionService.get_next_executable_subtasks(),
        конвертируя типы и результаты.
        
        Args:
            plan_id: ID плана (str)
            
        Returns:
            Список подзадач, готовых к выполнению (в legacy формате)
            
        Raises:
            ExecutionEngineError: Если план не найден
        """
        logger.debug(f"[Adapter] Getting next executable subtasks for plan {plan_id}")
        
        try:
            # Конвертировать str -> PlanId
            typed_plan_id = PlanId(plan_id)
            
            # Делегировать в новый сервис
            subtasks = await self.plan_execution_service.get_next_executable_subtasks(
                typed_plan_id
            )
            
            # Конвертировать Subtask entities в legacy формат (если нужно)
            # Пока возвращаем как есть, т.к. Subtask entity совместим
            return subtasks
        
        except PlanExecutionError as e:
            logger.error(f"[Adapter] Failed to get executable subtasks: {e}")
            raise ExecutionEngineError(str(e)) from e
        
        except Exception as e:
            logger.error(f"[Adapter] Unexpected error: {e}", exc_info=True)
            raise ExecutionEngineError(f"Unexpected error: {e}") from e

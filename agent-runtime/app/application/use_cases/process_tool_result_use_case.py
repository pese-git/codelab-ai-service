"""
Use Case для обработки результатов выполнения инструментов.

Координирует обработку результата tool call и продолжение диалога с агентом.
"""

import logging
from typing import Optional, AsyncGenerator
from dataclasses import dataclass

from .base_use_case import StreamingUseCase
from ...models.schemas import StreamChunk
from ...infrastructure.concurrency.request_deduplicator import get_request_deduplicator

logger = logging.getLogger("agent-runtime.use_cases.process_tool_result")


@dataclass
class ProcessToolResultRequest:
    """
    Запрос на обработку результата инструмента.
    
    Attributes:
        session_id: ID сессии
        call_id: ID вызова инструмента
        result: Результат выполнения (если успешно)
        error: Сообщение об ошибке (если неуспешно)
    
    Пример:
        >>> request = ProcessToolResultRequest(
        ...     session_id="session-123",
        ...     call_id="call-456",
        ...     result="File created successfully"
        ... )
    """
    session_id: str
    call_id: str
    result: Optional[str] = None
    error: Optional[str] = None


class ProcessToolResultUseCase(StreamingUseCase[ProcessToolResultRequest, StreamChunk]):
    """
    Use Case для обработки результата выполнения инструмента.
    
    Координирует:
    1. Добавление tool result в историю сообщений
    2. Продолжение диалога с агентом
    3. Проверку активного плана и resumable execution
    4. Streaming ответа клиенту
    
    Зависимости:
        - ToolResultHandler: Обработка результатов инструментов
        - SessionLockManager: Управление блокировками
        - PlanRepository: Поиск активных планов (опционально)
        - ExecutionCoordinator: Продолжение execution (опционально)
    
    Пример:
        >>> use_case = ProcessToolResultUseCase(
        ...     tool_result_handler=tool_result_handler,
        ...     lock_manager=lock_manager
        ... )
        >>> request = ProcessToolResultRequest(
        ...     session_id="session-123",
        ...     call_id="call-456",
        ...     result="Success"
        ... )
        >>> async for chunk in use_case.execute(request):
        ...     print(chunk)
    """
    
    def __init__(
        self,
        tool_result_handler,  # ToolResultHandler
        lock_manager,  # SessionLockManager
        plan_repository=None,  # PlanRepository (optional)
        execution_coordinator=None,  # ExecutionCoordinator (optional)
        session_service=None,  # SessionManagementService (optional)
        stream_handler=None,  # IStreamHandler (optional)
        uow=None  # SSEUnitOfWork (optional) - для явного commit после add_tool_result
    ):
        """
        Инициализация Use Case.
        
        Args:
            tool_result_handler: Handler результатов инструментов из Domain Layer
            lock_manager: Менеджер блокировок сессий
            plan_repository: Repository для поиска активных планов (опционально)
            execution_coordinator: Coordinator для продолжения execution (опционально)
            session_service: Session service для execution (опционально)
            stream_handler: Stream handler для execution (опционально)
            uow: Unit of Work для явного commit (опционально)
        """
        self._tool_result_handler = tool_result_handler
        self._lock_manager = lock_manager
        self._plan_repository = plan_repository
        self._execution_coordinator = execution_coordinator
        self._session_service = session_service
        self._stream_handler = stream_handler
        self._uow = uow
        
        logger.debug(
            f"ProcessToolResultUseCase инициализирован "
            f"(resumable_execution={'yes' if (plan_repository and execution_coordinator) else 'no'})"
        )
    
    async def execute(
        self,
        request: ProcessToolResultRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить обработку результата инструмента.
        
        Args:
            request: Запрос с параметрами обработки
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            ValueError: Если call_id не найден в pending state
            
        Пример потока:
            1. assistant_message (продолжение ответа агента)
            2. tool_call (если агент вызывает еще инструменты)
            3. done (завершение)
        """
        logger.info(
            f"Обработка tool result для сессии {request.session_id}, "
            f"call_id={request.call_id}, has_error={request.error is not None}"
        )
        
        # ✅ ДЕДУПЛИКАЦИЯ: Проверить, не был ли уже обработан этот tool_result
        deduplicator = get_request_deduplicator()
        if deduplicator.is_duplicate(request.session_id, request.call_id):
            logger.warning(
                f"🔄 Tool result {request.call_id} already processed for session {request.session_id}, "
                f"skipping duplicate request"
            )
            # Возвращаем пустой генератор - запрос уже обработан
            return
        
        try:
            # Отметить запрос как обрабатываемый
            deduplicator.mark_processed(request.session_id, request.call_id)
            
            # Блокировка сессии для предотвращения конкурентных запросов
            async with self._lock_manager.lock(request.session_id):
                # Делегировать обработку в ToolResultHandler (Domain Layer)
                async for chunk in self._tool_result_handler.handle(
                    session_id=request.session_id,
                    call_id=request.call_id,
                    result=request.result,
                    error=request.error
                ):
                    yield chunk
                    
                    # Логирование важных событий
                    if chunk.type == "tool_call":
                        tool_name = chunk.metadata.get('tool_name') if chunk.metadata else 'unknown'
                        call_id = chunk.metadata.get('call_id') if chunk.metadata else 'unknown'
                        logger.debug(
                            f"Новый tool call: {tool_name} "
                            f"(call_id: {call_id})"
                        )
                
                # ✅ КРИТИЧЕСКОЕ: Явный commit после обработки tool_result
                # Это гарантирует, что tool_result сохранится в БД даже если
                # последующий стрим прервется или произойдет ошибка
                if self._uow:
                    try:
                        await self._uow.commit(operation="process_tool_result")
                        logger.info(
                            f"✅ Tool result committed to DB for session {request.session_id}, "
                            f"call_id={request.call_id}"
                        )
                    except Exception as commit_error:
                        logger.error(
                            f"❌ Failed to commit tool_result: {commit_error}",
                            exc_info=True
                        )
                        # Не прерываем обработку, но логируем ошибку
                
                # Проверить активный план и продолжить execution если нужно
                if self._should_resume_execution():
                    active_plan = await self._get_active_plan(request.session_id)
                    
                    if active_plan:
                        logger.info(
                            f"Найден активный план {active_plan.id}, "
                            f"продолжение execution"
                        )
                        
                        # Продолжить execution (следующая subtask)
                        async for chunk in self._execution_coordinator.execute_plan(
                            plan_id=active_plan.id,
                            session_id=request.session_id,
                            session_service=self._session_service,
                            stream_handler=self._stream_handler
                        ):
                            yield chunk
                        
                        logger.info(f"Plan execution resumed для плана {active_plan.id}")
        
        except Exception as e:
            logger.error(
                f"Ошибка обработки tool result для сессии {request.session_id}: {e}",
                exc_info=True
            )
            # Отправить error chunk клиенту
            yield StreamChunk(
                type="error",
                error=str(e),
                is_final=True
            )
    
    def _should_resume_execution(self) -> bool:
        """
        Проверить, нужно ли продолжать execution.
        
        Returns:
            True если все зависимости для resumable execution настроены
        """
        return all([
            self._plan_repository,
            self._execution_coordinator,
            self._session_service,
            self._stream_handler
        ])
    
    async def _get_active_plan(self, session_id: str):
        """
        Получить активный план для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Plan со статусом IN_PROGRESS или None
        """
        from ...domain.entities.plan import PlanStatus
        
        try:
            # Использовать существующий метод find_by_session_id
            plan = await self._plan_repository.find_by_session_id(session_id)
            
            if plan and plan.status == PlanStatus.IN_PROGRESS:
                logger.debug(f"Найден активный план {plan.id} для сессии {session_id}")
                return plan
            else:
                logger.debug(f"Активный план (IN_PROGRESS) не найден для сессии {session_id}")
                return None
        
        except Exception as e:
            logger.warning(f"Ошибка поиска активного плана: {e}")
            return None

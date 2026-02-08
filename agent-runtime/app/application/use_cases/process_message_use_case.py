"""
Use Case для обработки входящих сообщений пользователя.

Координирует обработку сообщения через систему мульти-агентов
с поддержкой streaming ответов.
"""

import logging
from typing import Optional, AsyncGenerator
from dataclasses import dataclass

from .base_use_case import StreamingUseCase
from ...models.schemas import StreamChunk
from ...domain.agent_context.value_objects.agent_capabilities import AgentType

logger = logging.getLogger("agent-runtime.use_cases.process_message")


@dataclass
class ProcessMessageRequest:
    """
    Запрос на обработку сообщения пользователя.
    
    Attributes:
        session_id: ID сессии
        message: Текст сообщения пользователя
        agent_type: Явно запрошенный тип агента (опционально)
    
    Пример:
        >>> request = ProcessMessageRequest(
        ...     session_id="session-123",
        ...     message="Create a new file",
        ...     agent_type=AgentType.CODER
        ... )
    """
    session_id: str
    message: str
    agent_type: Optional[AgentType] = None


class ProcessMessageUseCase(StreamingUseCase[ProcessMessageRequest, StreamChunk]):
    """
    Use Case для обработки входящего сообщения пользователя.
    
    Координирует:
    1. Получение/создание сессии
    2. Маршрутизацию к нужному агенту
    3. Обработку сообщения через LLM
    4. Streaming ответа клиенту
    
    Зависимости:
        - MessageProcessor: Обработка сообщений
        - SessionLockManager: Управление блокировками
    
    Пример:
        >>> use_case = ProcessMessageUseCase(
        ...     message_processor=message_processor,
        ...     lock_manager=lock_manager
        ... )
        >>> request = ProcessMessageRequest(
        ...     session_id="session-123",
        ...     message="Write a function"
        ... )
        >>> async for chunk in use_case.execute(request):
        ...     if chunk.type == "assistant_message":
        ...         print(chunk.token, end="")
    """
    
    def __init__(
        self,
        message_processor,  # MessageProcessor
        lock_manager  # SessionLockManager
    ):
        """
        Инициализация Use Case.
        
        Args:
            message_processor: Процессор сообщений из Domain Layer
            lock_manager: Менеджер блокировок сессий
        """
        self._message_processor = message_processor
        self._lock_manager = lock_manager
        
        logger.debug("ProcessMessageUseCase инициализирован")
    
    async def execute(
        self,
        request: ProcessMessageRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить обработку сообщения.
        
        Args:
            request: Запрос с параметрами обработки
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            AgentSwitchError: Если переключение агента невозможно
            
        Пример потока:
            1. agent_switched (если нужно переключение)
            2. assistant_message (токены ответа)
            3. tool_call (если агент вызывает инструменты)
            4. done (завершение)
        """
        logger.info(
            f"Обработка сообщения для сессии {request.session_id} "
            f"(agent: {request.agent_type.value if request.agent_type else 'auto'})"
        )
        
        try:
            # Блокировка сессии для предотвращения конкурентных запросов
            async with self._lock_manager.lock(request.session_id):
                # Делегировать обработку в MessageProcessor (Domain Layer)
                async for chunk in self._message_processor.process(
                    session_id=request.session_id,
                    message=request.message,
                    agent_type=request.agent_type
                ):
                    yield chunk
                    
                    # Логирование важных событий
                    if chunk.type == "agent_switched" and chunk.metadata:
                        logger.info(
                            f"Агент переключен: {chunk.metadata.get('from_agent')} "
                            f"-> {chunk.metadata.get('to_agent')}"
                        )
                    elif chunk.type == "tool_call" and chunk.metadata:
                        logger.debug(
                            f"Tool call: {chunk.metadata.get('tool_name')} "
                            f"(call_id: {chunk.metadata.get('call_id')})"
                        )
                    elif chunk.type == "plan_approval_required" and chunk.metadata:
                        logger.info(
                            f"Plan approval required: {chunk.metadata.get('approval_request_id')}"
                        )
        
        except Exception as e:
            logger.error(
                f"Ошибка обработки сообщения для сессии {request.session_id}: {e}",
                exc_info=True
            )
            # Отправить error chunk клиенту
            yield StreamChunk(
                type="error",
                error=str(e),
                is_final=True
            )

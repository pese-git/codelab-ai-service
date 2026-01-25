"""
Application Handler для стриминга LLM ответов.

Координирует use case стриминга ответов от LLM:
- Фильтрация инструментов
- Вызов LLM
- Обработка ответа
- Публикация событий
- Сохранение результатов
- Генерация стрима
"""

import time
import logging
from typing import AsyncGenerator, List, Dict, Optional, Any

from ...domain.services.llm_response_processor import LLMResponseProcessor
from ...domain.services.tool_filter_service import ToolFilterService
from ...domain.services.session_management import SessionManagementService
from ...domain.services.hitl_service import HITLService
from ...domain.entities.llm_response import ProcessedResponse
from ...infrastructure.llm.llm_client import LLMClient
from ...infrastructure.events.llm_event_publisher import LLMEventPublisher
from ...models.schemas import StreamChunk

logger = logging.getLogger("agent-runtime.application.stream_llm_response_handler")


class StreamLLMResponseHandler:
    """
    Application Service для стриминга ответов LLM.
    
    Координирует use case стриминга:
    1. Фильтрация инструментов по разрешенным
    2. Вызов LLM через клиент
    3. Обработка ответа через доменный сервис
    4. Публикация событий
    5. Сохранение результатов через доменные сервисы
    6. Генерация стрима для API слоя
    
    НЕ содержит:
    - Бизнес-логику (делегирует в Domain)
    - Технические детали LLM API (делегирует в Infrastructure)
    - HTTP/SSE логику (делегирует в API Layer)
    
    Атрибуты:
        _llm_client: Клиент для вызова LLM
        _tool_filter: Сервис фильтрации инструментов
        _response_processor: Сервис обработки ответов
        _event_publisher: Publisher для событий
        _session_service: Сервис управления сессиями
        _hitl_service: Сервис HITL
    
    Пример:
        >>> handler = StreamLLMResponseHandler(
        ...     llm_client=llm_client,
        ...     tool_filter=tool_filter,
        ...     response_processor=response_processor,
        ...     event_publisher=event_publisher,
        ...     session_service=session_service,
        ...     hitl_service=hitl_service
        ... )
        >>> async for chunk in handler.handle(
        ...     session_id="session-1",
        ...     history=[...],
        ...     model="gpt-4"
        ... ):
        ...     print(chunk)
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        tool_filter: ToolFilterService,
        response_processor: LLMResponseProcessor,
        event_publisher: LLMEventPublisher,
        session_service: SessionManagementService,
        hitl_service: HITLService
    ):
        """
        Инициализация handler.
        
        Args:
            llm_client: Клиент для вызова LLM
            tool_filter: Сервис фильтрации инструментов
            response_processor: Сервис обработки ответов
            event_publisher: Publisher для событий
            session_service: Сервис управления сессиями
            hitl_service: Сервис HITL
        """
        self._llm_client = llm_client
        self._tool_filter = tool_filter
        self._response_processor = response_processor
        self._event_publisher = event_publisher
        self._session_service = session_service
        self._hitl_service = hitl_service
        
        logger.info("StreamLLMResponseHandler initialized")
    
    async def handle(
        self,
        session_id: str,
        history: List[Dict[str, Any]],
        model: str,
        allowed_tools: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать запрос на стриминг ответа LLM.
        
        Use Case:
        1. Фильтровать инструменты по разрешенным
        2. Опубликовать событие начала запроса
        3. Вызвать LLM через клиент
        4. Обработать ответ через доменный сервис
        5. Обработать tool calls или обычное сообщение
        6. Опубликовать событие завершения
        7. Сгенерировать стрим для клиента
        
        Args:
            session_id: ID сессии
            history: История сообщений для LLM
            model: Имя модели
            allowed_tools: Список разрешенных инструментов (None = все)
            correlation_id: ID для трассировки (опционально)
            
        Yields:
            StreamChunk: Чанки для SSE стриминга
            
        Пример:
            >>> async for chunk in handler.handle(
            ...     session_id="session-1",
            ...     history=[{"role": "user", "content": "Hello"}],
            ...     model="gpt-4",
            ...     allowed_tools=["read_file", "write_file"]
            ... ):
            ...     if chunk.type == "tool_call":
            ...         print(f"Tool call: {chunk.tool_name}")
            ...     elif chunk.type == "assistant_message":
            ...         print(f"Message: {chunk.content}")
        """
        try:
            # TEMPORARY: Явное логирование для отладки
            logger.error(
                f"🔥 NEW CODE: StreamLLMResponseHandler.handle() called for session {session_id} "
                f"with {len(history)} messages"
            )
            logger.info(
                f"Starting LLM stream for session {session_id} "
                f"with {len(history)} messages"
            )
            
            # 1. Фильтрация инструментов (Domain)
            tools = self._tool_filter.filter_tools(allowed_tools)
            
            # 2. Публикация события начала (Infrastructure)
            await self._event_publisher.publish_request_started(
                session_id=session_id,
                model=model,
                messages_count=len(history),
                tools_count=len(tools),
                correlation_id=correlation_id
            )
            
            # 3. Вызов LLM (Infrastructure)
            start_time = time.time()
            response = await self._llm_client.chat_completion(
                model=model,
                messages=history,
                tools=tools
            )
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.debug(
                f"LLM response received: content_length={len(response.content)}, "
                f"tool_calls={len(response.tool_calls)}, "
                f"duration={duration_ms}ms"
            )
            
            # 4. Обработка ответа (Domain)
            processed = self._response_processor.process_response(response)
            
            # Логирование предупреждений валидации
            if processed.validation_warnings:
                for warning in processed.validation_warnings:
                    logger.warning(f"Validation warning: {warning}")
            
            # 5. Обработка tool calls или обычного сообщения
            if processed.has_tool_calls():
                chunk = await self._handle_tool_call(
                    session_id=session_id,
                    processed=processed,
                    duration_ms=duration_ms,
                    history=history,
                    correlation_id=correlation_id
                )
            else:
                chunk = await self._handle_assistant_message(
                    session_id=session_id,
                    processed=processed,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id
                )
            
            # 6. Генерация стрима
            yield chunk
            
        except Exception as e:
            logger.error(
                f"Exception in stream_response for session {session_id}: {e}",
                exc_info=True
            )
            
            # Публикация события ошибки
            await self._event_publisher.publish_request_failed(
                session_id=session_id,
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            
            # Генерация error chunk
            yield StreamChunk(
                type="error",
                error=str(e),
                is_final=True
            )
    
    async def _handle_tool_call(
        self,
        session_id: str,
        processed: ProcessedResponse,
        duration_ms: int,
        history: List[Dict[str, Any]],
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """
        Обработать tool call.
        
        Координация:
        1. Извлечение текущего агента из истории
        2. Публикация события tool execution requested
        3. Сохранение pending approval (если требуется)
        4. Публикация события tool approval required (если требуется)
        5. Сохранение сообщения в сессию
        6. Публикация события завершения LLM запроса
        7. Создание chunk для стрима
        
        Args:
            session_id: ID сессии
            processed: Обработанный ответ LLM
            duration_ms: Длительность запроса в мс
            history: История сообщений (для извлечения агента)
            correlation_id: ID для трассировки
            
        Returns:
            StreamChunk для tool call
        """
        tool_call = processed.get_first_tool_call()
        
        if not tool_call:
            raise ValueError("No tool call found in processed response")
        
        logger.info(
            f"Tool call detected: {tool_call.tool_name} (call_id={tool_call.id})"
        )
        
        # 1. Извлечение текущего агента из истории
        current_agent = "unknown"
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("name"):
                current_agent = msg["name"]
                break
        
        # 2. Публикация события tool execution requested
        await self._event_publisher.publish_tool_execution_requested(
            session_id=session_id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            call_id=tool_call.id,
            agent=current_agent,
            correlation_id=correlation_id
        )
        
        # 3. HITL: Сохранение pending approval (если требуется)
        if processed.requires_approval:
            await self._hitl_service.add_pending(
                session_id=session_id,
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                reason=processed.approval_reason
            )
            
            logger.info(
                f"Added HITL pending state for call_id={tool_call.id}, "
                f"reason={processed.approval_reason}"
            )
            
            # 4. Публикация события tool approval required
            await self._event_publisher.publish_tool_approval_required(
                session_id=session_id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                call_id=tool_call.id,
                reason=processed.approval_reason or "Unknown",
                correlation_id=correlation_id
            )
        
        # 5. Сохранение сообщения через доменный сервис
        await self._session_service.add_message(
            session_id=session_id,
            role="assistant",
            content="",
            tool_calls=[tool_call.to_dict()]
        )
        
        logger.debug(
            f"Assistant message with tool_call persisted: {tool_call.tool_name}"
        )
        
        # 6. Публикация события завершения LLM запроса
        await self._event_publisher.publish_request_completed(
            session_id=session_id,
            model=processed.model,
            duration_ms=duration_ms,
            usage=processed.usage,
            has_tool_calls=True,
            correlation_id=correlation_id
        )
        
        # 7. Создание chunk для стрима
        return StreamChunk(
            type="tool_call",
            call_id=tool_call.id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            requires_approval=processed.requires_approval,
            is_final=True
        )
    
    async def _handle_assistant_message(
        self,
        session_id: str,
        processed: ProcessedResponse,
        duration_ms: int,
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """
        Обработать обычное сообщение ассистента.
        
        Координация:
        1. Сохранение сообщения в сессию
        2. Публикация события завершения LLM запроса
        3. Создание chunk для стрима
        
        Args:
            session_id: ID сессии
            processed: Обработанный ответ LLM
            duration_ms: Длительность запроса в мс
            correlation_id: ID для трассировки
            
        Returns:
            StreamChunk для assistant message
        """
        logger.info(
            f"Sending assistant message: {len(processed.content)} chars"
        )
        
        # 1. Сохранение сообщения через доменный сервис
        await self._session_service.add_message(
            session_id=session_id,
            role="assistant",
            content=processed.content
        )
        
        # 2. Публикация события завершения
        await self._event_publisher.publish_request_completed(
            session_id=session_id,
            model=processed.model,
            duration_ms=duration_ms,
            usage=processed.usage,
            has_tool_calls=False,
            correlation_id=correlation_id
        )
        
        # 3. Создание chunk для стрима
        return StreamChunk(
            type="assistant_message",
            content=processed.content,
            token=processed.content,
            is_final=True
        )

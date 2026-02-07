"""
Сервис обработки входящих пользовательских сообщений.

Отвечает за координацию обработки сообщений через систему агентов,
включая маршрутизацию через Orchestrator и обработку переключений агентов.
"""

import uuid
import time
import logging
from typing import AsyncGenerator, Optional, TYPE_CHECKING

from ..agent_context.value_objects.agent_capabilities import AgentType
from ...models.schemas import StreamChunk
from ...core.errors import SessionNotFoundError

if TYPE_CHECKING:
    from ..session_context.services import ConversationManagementService
    from .agent_orchestration import AgentOrchestrationService
    from .helpers.agent_switch_helper import AgentSwitchHelper
    from ..interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.domain.message_processor")


class MessageProcessor:
    """
    Сервис обработки входящих пользовательских сообщений.
    
    Ответственности:
    - Добавление user message в сессию
    - Получение/создание контекста агента
    - Маршрутизация через Orchestrator (если нужно)
    - Обработка сообщения через текущего агента
    - Обработка запросов на переключение агента
    - Публикация событий метрик
    
    Атрибуты:
        _session_service: Сервис управления сессиями
        _agent_service: Сервис оркестрации агентов
        _agent_router: Роутер для получения экземпляров агентов
        _stream_handler: Handler для стриминга LLM ответов
        _switch_helper: Helper для переключения агентов
    """
    
    def __init__(
        self,
        session_service: "ConversationManagementService",
        agent_service: "AgentOrchestrationService",
        agent_router,  # AgentRouter
        stream_handler: Optional["IStreamHandler"],
        switch_helper: "AgentSwitchHelper"
    ):
        """
        Инициализация процессора сообщений.
        
        Args:
            session_service: Сервис управления сессиями
            agent_service: Сервис оркестрации агентов
            agent_router: Роутер для получения экземпляров агентов
            stream_handler: Handler для стриминга LLM ответов
            switch_helper: Helper для переключения агентов
        """
        self._session_service = session_service
        self._agent_service = agent_service
        self._agent_router = agent_router
        self._stream_handler = stream_handler
        self._switch_helper = switch_helper
        
        logger.debug(
            f"MessageProcessor инициализирован с stream_handler={stream_handler is not None}"
        )
    
    async def process(
        self,
        session_id: str,
        message: Optional[str],
        agent_type: Optional[AgentType] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать пользовательское сообщение.
        
        Основной метод для обработки входящих сообщений. Координирует:
        - Добавление сообщения в историю
        - Явное переключение агента (если запрошено)
        - Маршрутизацию через Orchestrator
        - Обработку через текущего агента
        - Обработку запросов на переключение от агента
        
        Args:
            session_id: ID сессии
            message: Сообщение пользователя (None = продолжение после tool_result)
            agent_type: Явно запрошенный тип агента (опционально)
            correlation_id: ID для трассировки (опционально)
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
        """
        # Генерировать correlation ID для трассировки
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        logger.info(
            f"MessageProcessor обрабатывает сообщение для сессии {session_id} "
            f"(correlation_id: {correlation_id})"
        )
        
        # Добавить user message в сессию ПЕРЕД обработкой
        # ВАЖНО: message=None означает "не добавлять user message" (для tool_result)
        if message is not None and message != "":
            await self._session_service.add_message(
                session_id=session_id,
                role="user",
                content=message
            )
            logger.debug(f"User message добавлено в сессию {session_id}")
        elif message is None:
            logger.debug(
                f"Пропускаем добавление user message (message=None, "
                "продолжение после tool_result)"
            )
        
        # Получить или создать сессию (теперь с user message)
        session = await self._session_service.get_or_create_session(session_id)
        
        # Получить или создать контекст агента
        context = await self._agent_service.get_or_create_context(
            session_id=session_id,
            initial_agent=agent_type or AgentType.ORCHESTRATOR
        )
        
        # Отследить время начала обработки
        start_time = time.time()
        processing_success = True
        current_agent_for_tracking = context.current_agent
        
        try:
            # Обработать явный запрос на переключение агента
            if agent_type and context.current_agent != agent_type:
                from_agent = context.current_agent
                
                logger.info(
                    f"Явное переключение агента для сессии {session_id}: "
                    f"{from_agent.value} -> {agent_type.value}"
                )
                
                # Переключить агента
                context = await self._switch_helper.execute_agent_switch(
                    session_id=session_id,
                    target_agent=agent_type,
                    reason="User requested agent switch",
                    confidence="high"
                )
                
                # Уведомить о переключении
                yield self._switch_helper.create_agent_switched_chunk(
                    from_agent=from_agent,
                    to_agent=agent_type,
                    reason="User requested",
                    confidence="high",
                    is_final=False
                )
            
            # Если текущий агент - Orchestrator и есть сообщение,
            # позволить ему выполнить маршрутизацию
            if context.current_agent == AgentType.ORCHESTRATOR and message:
                logger.debug(
                    f"Текущий агент - Orchestrator, выполняется маршрутизация "
                    f"для сессии {session_id}"
                )
                
                # Обработать через Orchestrator для маршрутизации
                agent_switched = False
                async for chunk in self._process_with_orchestrator(
                    session_id=session_id,
                    message=message,
                    context=context,
                    session=session
                ):
                    if chunk.type == "switch_agent":
                        # Обработать переключение и получить новый контекст
                        context, notification_chunk = await self._switch_helper.handle_agent_switch_request(
                            session_id=session_id,
                            chunk=chunk,
                            current_context=context
                        )
                        yield notification_chunk
                        agent_switched = True
                        break
                    else:
                        # Переслать другие чанки
                        yield chunk
                        # Если Orchestrator вернул final chunk, он завершил обработку
                        # (например, создал план и ждет approval)
                        if chunk.is_final:
                            logger.info(
                                f"Orchestrator вернул final chunk для сессии {session_id}, "
                                f"завершаем обработку"
                            )
                            return  # Не продолжать обработку
                
                # Если произошло переключение агента, НЕ продолжать с orchestrator
                # Вместо этого, продолжить с новым агентом ниже
                if agent_switched:
                    logger.info(
                        f"Orchestrator переключил агента на {context.current_agent.value}, "
                        f"продолжаем обработку с новым агентом"
                    )
                    # Обновить сессию после переключения
                    session = await self._session_service.get_session(session_id)
                    # НЕ делать return здесь - продолжить к обработке с новым агентом
                else:
                    # Orchestrator обработал сам (не переключил) - завершаем
                    return
            
            # Получить текущего агента и обработать сообщение
            current_agent = self._agent_router.get_agent(context.current_agent)
            
            logger.info(
                f"Обработка с агентом {context.current_agent.value} "
                f"для сессии {session_id}"
            )
            
            # Обработать сообщение через текущего агента
            async for chunk in current_agent.process(
                session_id=session_id,
                message=message,
                context=self._context_to_dict(context),
                session=session,
                session_service=self._session_service,
                stream_handler=self._stream_handler
            ):
                # Проверить запросы на переключение агента от самого агента
                if chunk.type == "switch_agent":
                    # Обработать переключение через helper
                    context, notification_chunk = await self._switch_helper.handle_agent_switch_request(
                        session_id=session_id,
                        chunk=chunk,
                        current_context=context
                    )
                    
                    yield notification_chunk
                    
                    # Продолжить обработку с новым агентом
                    # Обновить сессию после переключения и добавления tool_result
                    session = await self._session_service.get_session(session_id)
                    new_agent = self._agent_router.get_agent(context.current_agent)
                    
                    async for new_chunk in new_agent.process(
                        session_id=session_id,
                        message=message,
                        context=self._context_to_dict(context),
                        session=session,
                        session_service=self._session_service,
                        stream_handler=self._stream_handler
                    ):
                        yield new_chunk
                    
                    return
                
                # Переслать чанк
                yield chunk
        
        except Exception as e:
            processing_success = False
            
            logger.error(
                f"Ошибка при обработке сообщения для сессии {session_id}: {e}",
                exc_info=True
            )
            
            # Опубликовать инфраструктурное событие ошибки для мониторинга
            await self._publish_error_event(
                session_id=session_id,
                agent_type=current_agent_for_tracking,
                error=e,
                correlation_id=correlation_id
            )
            
            raise
        
        finally:
            # Опубликовать инфраструктурное событие завершения для метрик
            duration_ms = (time.time() - start_time) * 1000
            
            await self._publish_completion_event(
                session_id=session_id,
                agent_type=current_agent_for_tracking,
                duration_ms=duration_ms,
                success=processing_success,
                correlation_id=correlation_id
            )
            
            logger.info(
                f"Обработка сообщения завершена для сессии {session_id} "
                f"(длительность: {duration_ms:.2f}ms, успех: {processing_success})"
            )
    
    async def _process_with_orchestrator(
        self,
        session_id: str,
        message: str,
        context,
        session
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение через Orchestrator для маршрутизации.
        
        Args:
            session_id: ID сессии
            message: Сообщение пользователя
            context: Контекст агента
            session: Объект сессии
            
        Yields:
            StreamChunk: Чанки от Orchestrator
        """
        orchestrator = self._agent_router.get_agent(AgentType.ORCHESTRATOR)
        
        # Orchestrator проанализирует и вернет switch_agent chunk
        async for chunk in orchestrator.process(
            session_id=session_id,
            message=message,
            context=self._context_to_dict(context),
            session=session,
            session_service=self._session_service,
            stream_handler=self._stream_handler
        ):
            yield chunk
    
    def _context_to_dict(self, context) -> dict:
        """
        Преобразовать контекст агента в словарь для передачи агентам.
        
        Args:
            context: Объект AgentContext
            
        Returns:
            Словарь с данными контекста
        """
        return {
            "session_id": context.session_id,
            "current_agent": context.current_agent.value,
            "switch_count": context.switch_count,
            "agent_history": [
                {
                    "from_agent": switch.from_agent.value if switch.from_agent else None,
                    "to_agent": switch.to_agent.value,
                    "reason": switch.reason,
                    "timestamp": switch.switched_at.isoformat(),
                    "confidence": switch.confidence
                }
                for switch in context.switch_history
            ]
        }
    
    async def _publish_error_event(
        self,
        session_id: str,
        agent_type: AgentType,
        error: Exception,
        correlation_id: str
    ) -> None:
        """
        Опубликовать событие ошибки для мониторинга.
        
        Args:
            session_id: ID сессии
            agent_type: Тип агента
            error: Исключение
            correlation_id: ID корреляции
        """
        try:
            from ...events.agent_events import AgentErrorOccurredEvent
            from ...events.event_bus import event_bus
            
            await event_bus.publish(
                AgentErrorOccurredEvent(
                    session_id=session_id,
                    agent_type=agent_type.value,
                    error_message=str(error),
                    error_type=type(error).__name__,
                    correlation_id=correlation_id
                )
            )
        except Exception as e:
            logger.error(f"Не удалось опубликовать событие ошибки: {e}")
    
    async def _publish_completion_event(
        self,
        session_id: str,
        agent_type: AgentType,
        duration_ms: float,
        success: bool,
        correlation_id: str
    ) -> None:
        """
        Опубликовать событие завершения для метрик.
        
        Args:
            session_id: ID сессии
            agent_type: Тип агента
            duration_ms: Длительность в миллисекундах
            success: Успешность обработки
            correlation_id: ID корреляции
        """
        try:
            from ...events.agent_events import AgentProcessingCompletedEvent
            from ...events.event_bus import event_bus
            
            await event_bus.publish(
                AgentProcessingCompletedEvent(
                    session_id=session_id,
                    agent_type=agent_type.value,
                    duration_ms=duration_ms,
                    success=success,
                    correlation_id=correlation_id
                )
            )
        except Exception as e:
            logger.error(f"Не удалось опубликовать событие завершения: {e}")

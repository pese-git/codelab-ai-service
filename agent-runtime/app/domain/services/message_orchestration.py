"""
Доменный сервис оркестрации сообщений.

Координирует обработку сообщений через систему мульти-агентов,
управляет переключением агентов и streaming ответов.
"""

import uuid
import time
import logging
from typing import AsyncGenerator, Optional, TYPE_CHECKING

from ..entities.agent_context import AgentType
from ..repositories.session_repository import SessionRepository
from ..repositories.agent_context_repository import AgentContextRepository
from .session_management import SessionManagementService
from .agent_orchestration import AgentOrchestrationService
from ...models.schemas import StreamChunk
from ...core.errors import SessionNotFoundError, AgentSwitchError

if TYPE_CHECKING:
    from ...domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.domain.message_orchestration")


class MessageOrchestrationService:
    """
    Доменный сервис для оркестрации обработки сообщений.
    
    Координирует:
    - Маршрутизацию сообщений к агентам
    - Переключение между агентами
    - Streaming ответов
    - Управление контекстом сессии
    
    Атрибуты:
        _session_service: Сервис управления сессиями
        _agent_service: Сервис оркестрации агентов
        _agent_router: Роутер для получения экземпляров агентов
        _lock_manager: Менеджер блокировок сессий
        _event_publisher: Функция для публикации событий (опционально)
        _hitl_service: Сервис HITL (опционально, для обратной совместимости)
    
    Пример:
        >>> service = MessageOrchestrationService(
        ...     session_service=session_service,
        ...     agent_service=agent_service,
        ...     agent_router=agent_router,
        ...     lock_manager=lock_manager,
        ...     hitl_service=hitl_service
        ... )
        >>> async for chunk in service.process_message(
        ...     session_id="session-1",
        ...     message="Hello"
        ... ):
        ...     print(chunk)
    """
    
    def __init__(
        self,
        session_service: SessionManagementService,
        agent_service: AgentOrchestrationService,
        agent_router,  # AgentRouter instance
        lock_manager,  # SessionLockManager instance
        event_publisher=None,
        stream_handler: Optional["IStreamHandler"] = None,
        hitl_service=None  # HITLService instance (optional for backward compatibility)
    ):
        """
        Инициализация сервиса.
        
        Args:
            session_service: Сервис управления сессиями
            agent_service: Сервис оркестрации агентов
            agent_router: Роутер агентов для получения экземпляров
            lock_manager: Менеджер блокировок для защиты от race conditions
            event_publisher: Функция для публикации событий (опционально)
            stream_handler: Handler для стриминга LLM ответов (интерфейс из Domain слоя)
            hitl_service: Сервис HITL (опционально, для обратной совместимости)
        """
        self._session_service = session_service
        self._agent_service = agent_service
        self._agent_router = agent_router
        self._lock_manager = lock_manager
        self._event_publisher = event_publisher
        self._stream_handler = stream_handler
        self._hitl_service = hitl_service
        
        # TEMPORARY: Явное логирование для отладки
        logger.error(
            f"🔥 MessageOrchestrationService initialized with stream_handler={stream_handler is not None}"
        )
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение через систему мульти-агентов.
        
        Основной метод для обработки пользовательских сообщений.
        Координирует работу агентов, управляет переключениями и
        обеспечивает streaming ответов.
        
        Args:
            session_id: ID сессии
            message: Сообщение пользователя
            agent_type: Явно запрошенный тип агента (опционально)
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            AgentSwitchError: Если переключение агента невозможно
            
        Пример:
            >>> async for chunk in service.process_message(
            ...     session_id="session-1",
            ...     message="Write a function to calculate fibonacci"
            ... ):
            ...     if chunk.type == "assistant_message":
            ...         print(chunk.token, end="")
            ...     elif chunk.type == "agent_switched":
            ...         print(f"\\nSwitched to {chunk.metadata['to_agent']}")
        """
        # Генерировать correlation ID для трассировки
        correlation_id = str(uuid.uuid4())
        
        logger.info(
            f"MessageOrchestrationService обрабатывает сообщение "
            f"для сессии {session_id} (correlation_id: {correlation_id})"
        )
        
        # Использовать блокировку сессии для предотвращения race conditions
        async with self._lock_manager.lock(session_id):
            # Добавить user message в сессию ПЕРЕД обработкой
            # Это гарантирует, что сообщение будет в истории для агента
            # ВАЖНО: message=None означает "не добавлять user message" (для tool_result)
            if message is not None and message != "":
                await self._session_service.add_message(
                    session_id=session_id,
                    role="user",
                    content=message
                )
                logger.debug(f"User message added to session {session_id}")
            elif message is None:
                logger.debug(f"Skipping user message addition (message=None, продолжение после tool_result)")
            
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
                    context = await self._agent_service.switch_agent(
                        session_id=session_id,
                        target_agent=agent_type,
                        reason="User requested agent switch",
                        confidence="high"
                    )
                    
                    # Уведомить о переключении
                    yield StreamChunk(
                        type="agent_switched",
                        content=f"Switched to {agent_type.value} agent",
                        metadata={
                            "from_agent": from_agent.value,
                            "to_agent": agent_type.value,
                            "reason": "User requested"
                        },
                        is_final=False
                    )
                
                # Если текущий агент - Orchestrator и есть сообщение,
                # позволить ему выполнить маршрутизацию
                if context.current_agent == AgentType.ORCHESTRATOR and message:
                    logger.debug(
                        f"Текущий агент - Orchestrator, выполняется маршрутизация "
                        f"для сессии {session_id}"
                    )
                    
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
                        if chunk.type == "switch_agent":
                            # Извлечь целевого агента из метаданных
                            target_agent_str = chunk.metadata.get("target_agent")
                            target_agent = AgentType(target_agent_str)
                            reason = chunk.metadata.get("reason", "Orchestrator routing")
                            confidence = chunk.metadata.get("confidence", "medium")
                            
                            logger.info(
                                f"Orchestrator направил к {target_agent.value} "
                                f"для сессии {session_id}"
                            )
                            
                            # Переключить агента
                            context = await self._agent_service.switch_agent(
                                session_id=session_id,
                                target_agent=target_agent,
                                reason=reason,
                                confidence=confidence
                            )
                            
                            # Уведомить о переключении
                            yield StreamChunk(
                                type="agent_switched",
                                content=f"Switched to {target_agent.value} agent",
                                metadata={
                                    "from_agent": AgentType.ORCHESTRATOR.value,
                                    "to_agent": target_agent.value,
                                    "reason": reason,
                                    "confidence": confidence
                                },
                                is_final=False
                            )
                            break
                        else:
                            # Переслать другие чанки (не должно происходить с Orchestrator)
                            yield chunk
                
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
                        target_agent_str = chunk.metadata.get("target_agent")
                        target_agent = AgentType(target_agent_str)
                        reason = chunk.metadata.get("reason", "Agent requested switch")
                        from_agent = context.current_agent
                        
                        logger.info(
                            f"Агент запросил переключение: "
                            f"{from_agent.value} -> {target_agent.value}"
                        )
                        
                        # ВАЖНО: Добавить tool_result для switch_mode в историю
                        # Это предотвращает ошибку "No tool output found" от LLM провайдера
                        # Получаем call_id из последнего assistant message с tool_calls
                        session = await self._session_service.get_session(session_id)
                        history = session.get_history_for_llm()
                        
                        # Найти последний tool_call для switch_mode
                        switch_call_id = None
                        for msg in reversed(history):
                            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                                for tc in msg["tool_calls"]:
                                    if tc.get("function", {}).get("name") == "switch_mode":
                                        switch_call_id = tc.get("id")
                                        break
                                if switch_call_id:
                                    break
                        
                        if switch_call_id:
                            logger.debug(
                                f"Добавляем tool_result для switch_mode (call_id={switch_call_id})"
                            )
                            await self._session_service.add_tool_result(
                                session_id=session_id,
                                call_id=switch_call_id,
                                result=f"Switched to {target_agent.value} agent",
                                error=None
                            )
                        else:
                            logger.warning(
                                "Не найден call_id для switch_mode tool_call, "
                                "tool_result не добавлен"
                            )
                        
                        # Переключить агента
                        context = await self._agent_service.switch_agent(
                            session_id=session_id,
                            target_agent=target_agent,
                            reason=reason
                        )
                        
                        logger.info(
                            f"Контекст обновлен после переключения: "
                            f"current_agent={context.current_agent.value}, "
                            f"switch_count={context.switch_count}"
                        )
                        
                        # Уведомить о переключении
                        yield StreamChunk(
                            type="agent_switched",
                            content=f"Switched to {target_agent.value} agent",
                            metadata={
                                "from_agent": from_agent.value,
                                "to_agent": target_agent.value,
                                "reason": reason
                            },
                            is_final=False
                        )
                        
                        # Продолжить обработку с новым агентом
                        # Обновить сессию после переключения и добавления tool_result
                        session = await self._session_service.get_session(session_id)
                        new_agent = self._agent_router.get_agent(target_agent)
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
                # Используем event_bus напрямую, так как это техническое событие
                from ...events.agent_events import AgentErrorOccurredEvent
                from ...events.event_bus import event_bus
                await event_bus.publish(
                    AgentErrorOccurredEvent(
                        session_id=session_id,
                        agent_type=current_agent_for_tracking.value,
                        error_message=str(e),
                        error_type=type(e).__name__,
                        correlation_id=correlation_id
                    )
                )
                
                raise
            
            finally:
                # Опубликовать инфраструктурное событие завершения для метрик
                # Используем event_bus напрямую, так как это техническое событие
                duration_ms = (time.time() - start_time) * 1000
                
                from ...events.agent_events import AgentProcessingCompletedEvent
                from ...events.event_bus import event_bus
                await event_bus.publish(
                    AgentProcessingCompletedEvent(
                        session_id=session_id,
                        agent_type=current_agent_for_tracking.value,
                        duration_ms=duration_ms,
                        success=processing_success,
                        correlation_id=correlation_id
                    )
                )
                
                logger.info(
                    f"Обработка сообщения завершена для сессии {session_id} "
                    f"(длительность: {duration_ms:.2f}ms, успех: {processing_success})"
                )
    
    async def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Получить текущего активного агента для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Тип текущего агента или None если сессия не существует
            
        Пример:
            >>> agent = await service.get_current_agent("session-1")
            >>> if agent:
            ...     print(f"Current agent: {agent.value}")
        """
        return await self._agent_service.get_current_agent(session_id)
    
    async def switch_agent(
        self,
        session_id: str,
        agent_type: AgentType,
        reason: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Явное переключение агента для сессии.
        
        Args:
            session_id: ID сессии
            agent_type: Целевой тип агента
            reason: Причина переключения (опционально)
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Пример:
            >>> async for chunk in service.switch_agent(
            ...     session_id="session-1",
            ...     agent_type=AgentType.CODER,
            ...     reason="User switched to coder"
            ... ):
            ...     print(chunk)
        """
        # Установить reason по умолчанию, если не указан
        if reason is None:
            reason = f"User requested switch to {agent_type.value}"
        
        logger.info(
            f"Явное переключение агента для сессии {session_id} "
            f"на {agent_type.value}: {reason}"
        )
        
        async with self._lock_manager.lock(session_id):
            # Получить текущий контекст
            context = await self._agent_service.get_or_create_context(
                session_id=session_id,
                initial_agent=AgentType.ORCHESTRATOR
            )
            
            from_agent = context.current_agent
            
            # Переключить агента
            context = await self._agent_service.switch_agent(
                session_id=session_id,
                target_agent=agent_type,
                reason=reason,
                confidence="high"
            )
            
            # Уведомить о переключении
            yield StreamChunk(
                type="agent_switched",
                content=f"Switched to {agent_type.value} agent",
                metadata={
                    "from_agent": from_agent.value,
                    "to_agent": agent_type.value,
                    "reason": reason,
                    "confidence": "high"
                },
                is_final=True
            )
    
    async def process_tool_result(
        self,
        session_id: str,
        call_id: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать результат выполнения инструмента.
        
        Добавляет результат в сессию и продолжает обработку с текущим агентом.
        
        Args:
            session_id: ID сессии
            call_id: ID вызова инструмента
            result: Результат выполнения (если успешно)
            error: Сообщение об ошибке (если неуспешно)
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Пример:
            >>> async for chunk in service.process_tool_result(
            ...     session_id="session-1",
            ...     call_id="call-123",
            ...     result="File created successfully"
            ... ):
            ...     print(chunk)
        """
        logger.info(
            f"Обработка результата инструмента для сессии {session_id}: "
            f"call_id={call_id}, has_error={error is not None}"
        )
        
        async with self._lock_manager.lock(session_id):
            # NOTE: НЕ удаляем pending approval автоматически при ошибке rejection
            # Pending approval должен быть удален только после явного решения пользователя через HITL dialog
            # Это позволяет IDE восстановить диалог после перезапуска
            
            # Старая логика (закомментирована):
            # if error and ("Операция отклонена" in error or "User rejected" in error):
            #     if self._hitl_service:
            #         pending = await self._hitl_service.get_pending(session_id, call_id)
            #         if pending:
            #             logger.info(f"Removing pending approval due to rejection error: {call_id}")
            #             await self._hitl_service.remove_pending(session_id, call_id)
            
            # Получить сессию
            session = await self._session_service.get_or_create_session(session_id)
            
            # Получить контекст агента
            # ВАЖНО: НЕ указываем initial_agent, чтобы не сбросить существующий контекст
            context = await self._agent_service.get_or_create_context(
                session_id=session_id
            )
            
            logger.info(
                f"Загружен контекст для сессии {session_id}: "
                f"current_agent={context.current_agent.value}, "
                f"switch_count={context.switch_count}"
            )
            
            # Добавить результат инструмента в сессию
            await self._session_service.add_tool_result(
                session_id=session_id,
                call_id=call_id,
                result=result,
                error=error
            )
            
            logger.info(
                f"Результат инструмента добавлен в сессию {session_id}, "
                f"продолжаем обработку с агентом {context.current_agent.value}"
            )
            
            # Получить текущего агента и продолжить обработку
            current_agent = self._agent_router.get_agent(context.current_agent)
            
            logger.debug(f"Вызываем {context.current_agent.value}.process() для продолжения")
            
            # Обновить сессию после добавления tool_result
            session = await self._session_service.get_session(session_id)
            
            # Получить последнее user message для передачи новому агенту при переключении
            user_messages = session.get_messages_by_role("user")
            last_user_message = user_messages[-1].content if user_messages else ""
            
            logger.debug(f"Последнее user message: {last_user_message[:50]}...")
            
            # ВАЖНО: Продолжить обработку с пустым сообщением
            # НЕ добавляем user message, так как tool_result уже в истории
            # Агент получит историю с tool_call и tool_result для продолжения
            chunk_count = 0
            async for chunk in current_agent.process(
                session_id=session_id,
                message=None,  # None означает "не добавлять user message"
                context=self._context_to_dict(context),
                session=session,
                session_service=self._session_service,
                stream_handler=self._stream_handler
            ):
                chunk_count += 1
                logger.debug(f"Получен chunk #{chunk_count}: type={chunk.type}, is_final={chunk.is_final}")
                
                # Если агент запрашивает переключение, продолжить с новым агентом
                if chunk.type == "switch_agent":
                    target_agent_str = chunk.metadata.get("target_agent")
                    target_agent = AgentType(target_agent_str)
                    reason = chunk.metadata.get("reason", "Agent requested switch")
                    from_agent = context.current_agent
                    
                    logger.info(
                        f"Агент запросил переключение при обработке tool_result: "
                        f"{from_agent.value} -> {target_agent.value}"
                    )
                    
                    # ВАЖНО: Добавить tool_result для switch_mode в историю
                    # Это предотвращает ошибку "No tool output found" от LLM провайдера
                    # Получаем обновленную сессию
                    session = await self._session_service.get_session(session_id)
                    history = session.get_history_for_llm()
                    
                    # Найти последний tool_call для switch_mode
                    switch_call_id = None
                    for msg in reversed(history):
                        if msg.get("role") == "assistant" and msg.get("tool_calls"):
                            for tc in msg["tool_calls"]:
                                if tc.get("function", {}).get("name") == "switch_mode":
                                    switch_call_id = tc.get("id")
                                    break
                            if switch_call_id:
                                break
                    
                    if switch_call_id:
                        logger.debug(
                            f"Добавляем tool_result для switch_mode (call_id={switch_call_id})"
                        )
                        await self._session_service.add_tool_result(
                            session_id=session_id,
                            call_id=switch_call_id,
                            result=f"Switched to {target_agent.value} agent",
                            error=None
                        )
                    else:
                        logger.warning(
                            "Не найден call_id для switch_mode tool_call, "
                            "tool_result не добавлен"
                        )
                    
                    # Переключить агента
                    context = await self._agent_service.switch_agent(
                        session_id=session_id,
                        target_agent=target_agent,
                        reason=reason
                    )
                    
                    # Уведомить о переключении
                    yield StreamChunk(
                        type="agent_switched",
                        content=f"Switched to {target_agent.value} agent",
                        metadata={
                            "from_agent": from_agent.value,
                            "to_agent": target_agent.value,
                            "reason": reason
                        },
                        is_final=False
                    )
                    
                    # Продолжить обработку с новым агентом и ОРИГИНАЛЬНЫМ сообщением
                    # Обновить сессию после добавления tool_result
                    session = await self._session_service.get_session(session_id)
                    new_agent = self._agent_router.get_agent(target_agent)
                    async for new_chunk in new_agent.process(
                        session_id=session_id,
                        message=last_user_message,  # Передаем оригинальное сообщение пользователя
                        context=self._context_to_dict(context),
                        session=session,
                        session_service=self._session_service,
                        stream_handler=self._stream_handler
                    ):
                        yield new_chunk
                    
                    return
                
                yield chunk
            
            logger.info(f"Обработка tool_result завершена, отправлено {chunk_count} chunks")
    
    async def process_hitl_decision(
        self,
        session_id: str,
        call_id: str,
        decision: str,
        modified_arguments: Optional[dict] = None,
        feedback: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать HITL (Human-in-the-Loop) решение пользователя.
        
        Обрабатывает решение пользователя по запросу на одобрение инструмента:
        - approve: Выполнить инструмент с оригинальными аргументами
        - edit: Выполнить инструмент с модифицированными аргументами
        - reject: Не выполнять инструмент, отправить feedback LLM
        
        Args:
            session_id: ID сессии
            call_id: ID вызова инструмента
            decision: Решение пользователя (approve/edit/reject)
            modified_arguments: Модифицированные аргументы (для edit)
            feedback: Обратная связь пользователя (для reject)
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            ValueError: Если решение невалидно или pending state не найден
            
        Пример:
            >>> async for chunk in service.process_hitl_decision(
            ...     session_id="session-1",
            ...     call_id="call-123",
            ...     decision="approve"
            ... ):
            ...     print(chunk)
        """
        import json
        from ...models.hitl_models import HITLDecision
        
        logger.info(
            f"Обработка HITL решения для сессии {session_id}: "
            f"call_id={call_id}, decision={decision}"
        )
        
        async with self._lock_manager.lock(session_id):
            # Валидация решения
            try:
                decision_enum = HITLDecision(decision)
            except ValueError:
                error_msg = f"Invalid HITL decision: {decision}"
                logger.error(error_msg)
                yield StreamChunk(
                    type="error",
                    error=error_msg,
                    is_final=True
                )
                return
            
            # Получить pending state
            pending_state = await self._hitl_service.get_pending(session_id, call_id)
            if not pending_state:
                error_msg = f"No pending HITL state found for call_id={call_id}"
                logger.error(error_msg)
                yield StreamChunk(
                    type="error",
                    error=error_msg,
                    is_final=True
                )
                return
            
            # Логировать решение в audit
            await self._hitl_service.log_decision(
                session_id=session_id,
                call_id=call_id,
                tool_name=pending_state.tool_name,
                original_arguments=pending_state.arguments,
                decision=decision_enum,
                modified_arguments=modified_arguments,
                feedback=feedback
            )
            
            # Обработать решение
            if decision_enum == HITLDecision.APPROVE:
                # Выполнить инструмент с оригинальными аргументами
                logger.info(f"HITL APPROVED: executing {pending_state.tool_name}")
                result = {
                    "status": "approved",
                    "tool_name": pending_state.tool_name,
                    "arguments": pending_state.arguments
                }
                
            elif decision_enum == HITLDecision.EDIT:
                # Выполнить инструмент с модифицированными аргументами
                logger.info(f"HITL EDITED: executing {pending_state.tool_name} with modified args")
                result = {
                    "status": "approved_with_edits",
                    "tool_name": pending_state.tool_name,
                    "arguments": modified_arguments or pending_state.arguments
                }
                
            elif decision_enum == HITLDecision.REJECT:
                # Не выполнять, отправить feedback LLM
                logger.info(f"HITL REJECTED: {pending_state.tool_name}, feedback={feedback}")
                result = {
                    "status": "rejected",
                    "tool_name": pending_state.tool_name,
                    "feedback": feedback or "User rejected this operation"
                }
            
            # Удалить pending state
            await self._hitl_service.remove_pending(session_id, call_id)
            
            # Добавить результат в историю сессии
            result_str = json.dumps(result)
            await self._session_service.add_message(
                session_id=session_id,
                role="tool",
                content=result_str,
                name=pending_state.tool_name,
                tool_call_id=call_id
            )
            
            logger.info(
                f"HITL результат добавлен в сессию {session_id}, "
                f"продолжаем обработку с текущим агентом"
            )
            
            # Продолжить обработку с текущим агентом (пустое сообщение)
            # Используем process_message с message="" для продолжения после tool_result
            async for chunk in self.process_message(
                session_id=session_id,
                message=""  # Пустое сообщение = продолжить после tool_result
            ):
                yield chunk
    
    async def reset_session(self, session_id: str) -> None:
        """
        Сбросить сессию в начальное состояние (Orchestrator).
        
        Args:
            session_id: ID сессии
            
        Пример:
            >>> await service.reset_session("session-1")
        """
        logger.info(f"Сброс сессии {session_id} к Orchestrator агенту")
        
        await self._agent_service.switch_agent(
            session_id=session_id,
            target_agent=AgentType.ORCHESTRATOR,
            reason="Session reset"
        )
    
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

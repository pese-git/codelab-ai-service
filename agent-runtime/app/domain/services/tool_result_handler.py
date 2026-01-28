"""
Сервис обработки результатов выполнения инструментов.

Отвечает за добавление результатов инструментов в историю сессии
и продолжение обработки с текущим агентом.
"""

import logging
from typing import AsyncGenerator, Optional, TYPE_CHECKING

from ...models.schemas import StreamChunk

if TYPE_CHECKING:
    from .session_management import SessionManagementService
    from .agent_orchestration import AgentOrchestrationService
    from .helpers.agent_switch_helper import AgentSwitchHelper
    from ..interfaces.stream_handler import IStreamHandler
    from .approval_management import ApprovalManager

logger = logging.getLogger("agent-runtime.domain.tool_result_handler")


class ToolResultHandler:
    """
    Сервис обработки результатов выполнения инструментов.
    
    Ответственности:
    - Добавление tool_result в сессию
    - Продолжение обработки с текущим агентом
    - Обработка переключений агента при tool_result
    - Извлечение последнего user message для нового агента
    
    Атрибуты:
        _session_service: Сервис управления сессиями
        _agent_service: Сервис оркестрации агентов
        _agent_router: Роутер для получения экземпляров агентов
        _stream_handler: Handler для стриминга LLM ответов
        _switch_helper: Helper для переключения агентов
        _approval_manager: Unified approval manager
    """
    
    def __init__(
        self,
        session_service: "SessionManagementService",
        agent_service: "AgentOrchestrationService",
        agent_router,  # AgentRouter
        stream_handler: Optional["IStreamHandler"],
        switch_helper: "AgentSwitchHelper",
        approval_manager: Optional["ApprovalManager"] = None
    ):
        """
        Инициализация handler.
        
        Args:
            session_service: Сервис управления сессиями
            agent_service: Сервис оркестрации агентов
            agent_router: Роутер для получения экземпляров агентов
            stream_handler: Handler для стриминга LLM ответов
            switch_helper: Helper для переключения агентов
            approval_manager: Unified approval manager для удаления pending approvals
        """
        self._session_service = session_service
        self._agent_service = agent_service
        self._agent_router = agent_router
        self._stream_handler = stream_handler
        self._switch_helper = switch_helper
        self._approval_manager = approval_manager
        
        logger.debug(
            f"ToolResultHandler инициализирован с stream_handler={stream_handler is not None}, "
            f"approval_manager={approval_manager is not None}"
        )
    
    async def handle(
        self,
        session_id: str,
        call_id: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать результат выполнения инструмента.
        
        Добавляет результат в историю сессии и продолжает обработку
        с текущим агентом. Если агент запрашивает переключение,
        обрабатывает его и продолжает с новым агентом.
        
        Args:
            session_id: ID сессии
            call_id: ID вызова инструмента
            result: Результат выполнения (если успешно)
            error: Сообщение об ошибке (если неуспешно)
            
        Yields:
            StreamChunk: Чанки для SSE streaming
        """
        logger.info(
            f"Обработка результата инструмента для сессии {session_id}: "
            f"call_id={call_id}, has_error={error is not None}"
        )
        
        # BUGFIX: Обновляем статус pending approval при получении tool_result
        # Если tool_result получен (успех или ошибка), значит решение пользователя
        # уже принято (approve/reject) и нужно обновить статус pending approval.
        # Это предотвращает повторное появление диалога после перезапуска IDE.
        if self._approval_manager:
            try:
                # Проверяем, есть ли pending approval для этого call_id
                pending = await self._approval_manager.get_pending(call_id)
                if pending:
                    # Если есть error, значит пользователь reject'нул
                    # Если нет error, значит пользователь approve'нул
                    if error:
                        await self._approval_manager.reject(call_id, reason=f"Tool execution failed: {error}")
                        logger.info(
                            f"✅ Marked pending approval as rejected for request_id={call_id} "
                            f"after receiving tool_result with error"
                        )
                    else:
                        await self._approval_manager.approve(call_id)
                        logger.info(
                            f"✅ Marked pending approval as approved for request_id={call_id} "
                            f"after receiving successful tool_result"
                        )
                else:
                    logger.debug(
                        f"No pending approval found for request_id={call_id} "
                        f"(tool was executed without approval requirement)"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to update pending approval status for request_id={call_id}: {e}"
                )
                # Не блокируем обработку из-за ошибки обновления статуса
        else:
            logger.debug(
                "ApprovalManager not available, skipping pending approval status update"
            )
        
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
        last_user_message = self._extract_last_user_message(session)
        
        logger.debug(f"Последнее user message: {last_user_message[:50] if last_user_message else 'None'}...")
        
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
                # Обработать переключение через helper
                context, notification_chunk = await self._switch_helper.handle_agent_switch_request(
                    session_id=session_id,
                    chunk=chunk,
                    current_context=context
                )
                
                yield notification_chunk
                
                # Продолжить обработку с новым агентом и ОРИГИНАЛЬНЫМ сообщением
                # Обновить сессию после добавления tool_result
                session = await self._session_service.get_session(session_id)
                new_agent = self._agent_router.get_agent(context.current_agent)
                
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
    
    def _extract_last_user_message(self, session) -> str:
        """
        Извлечь последнее user message из сессии.
        
        Args:
            session: Объект сессии
            
        Returns:
            Содержимое последнего user message или пустая строка
        """
        user_messages = session.get_messages_by_role("user")
        return user_messages[-1].content if user_messages else ""
    
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

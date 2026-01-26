"""
Доменный сервис оркестрации сообщений (Фасад).

Координирует обработку сообщений через специализированные сервисы.
Обеспечивает обратную совместимость с существующим API.
"""

import logging
from typing import AsyncGenerator, Optional

from ..entities.agent_context import AgentType
from ...models.schemas import StreamChunk

logger = logging.getLogger("agent-runtime.domain.message_orchestration")


class MessageOrchestrationService:
    """
    Фасад для координации обработки сообщений.
    
    Делегирует работу специализированным сервисам:
    - MessageProcessor - обработка входящих сообщений
    - AgentSwitcher - переключение агентов
    - ToolResultHandler - обработка результатов инструментов
    - HITLDecisionHandler - обработка HITL решений
    
    Обеспечивает обратную совместимость с существующим API.
    
    Атрибуты:
        _message_processor: Процессор сообщений
        _agent_switcher: Switcher агентов
        _tool_result_handler: Handler результатов инструментов
        _hitl_handler: Handler HITL решений
        _lock_manager: Менеджер блокировок сессий
    
    Пример:
        >>> service = MessageOrchestrationService(
        ...     message_processor=message_processor,
        ...     agent_switcher=agent_switcher,
        ...     tool_result_handler=tool_result_handler,
        ...     hitl_handler=hitl_handler,
        ...     lock_manager=lock_manager
        ... )
        >>> async for chunk in service.process_message(
        ...     session_id="session-1",
        ...     message="Hello"
        ... ):
        ...     print(chunk)
    """
    
    def __init__(
        self,
        message_processor,  # MessageProcessor
        agent_switcher,  # AgentSwitcher
        tool_result_handler,  # ToolResultHandler
        hitl_handler,  # HITLDecisionHandler
        lock_manager  # SessionLockManager
    ):
        """
        Инициализация сервиса-фасада.
        
        Args:
            message_processor: Процессор сообщений
            agent_switcher: Switcher агентов
            tool_result_handler: Handler результатов инструментов
            hitl_handler: Handler HITL решений
            lock_manager: Менеджер блокировок сессий
        """
        self._message_processor = message_processor
        self._agent_switcher = agent_switcher
        self._tool_result_handler = tool_result_handler
        self._hitl_handler = hitl_handler
        self._lock_manager = lock_manager
        
        logger.info("MessageOrchestrationService (фасад) инициализирован")
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать сообщение через систему мульти-агентов.
        
        Делегирует обработку в MessageProcessor.
        
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
        logger.debug(
            f"Делегирование process_message в MessageProcessor "
            f"для сессии {session_id}"
        )
        
        # Делегировать в MessageProcessor с блокировкой сессии
        async with self._lock_manager.lock(session_id):
            async for chunk in self._message_processor.process(
                session_id=session_id,
                message=message,
                agent_type=agent_type
            ):
                yield chunk
    
    async def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Получить текущего активного агента для сессии.
        
        Делегирует в AgentSwitcher.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Тип текущего агента или None если сессия не существует
            
        Пример:
            >>> agent = await service.get_current_agent("session-1")
            >>> if agent:
            ...     print(f"Current agent: {agent.value}")
        """
        logger.debug(
            f"Делегирование get_current_agent в AgentSwitcher "
            f"для сессии {session_id}"
        )
        
        return await self._agent_switcher.get_current_agent(session_id)
    
    async def switch_agent(
        self,
        session_id: str,
        agent_type: AgentType,
        reason: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Явное переключение агента для сессии.
        
        Делегирует в AgentSwitcher.
        
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
        logger.debug(
            f"Делегирование switch_agent в AgentSwitcher "
            f"для сессии {session_id} -> {agent_type.value}"
        )
        
        # Делегировать в AgentSwitcher с блокировкой сессии
        async with self._lock_manager.lock(session_id):
            async for chunk in self._agent_switcher.switch(
                session_id=session_id,
                target_agent=agent_type,
                reason=reason
            ):
                yield chunk
    
    async def process_tool_result(
        self,
        session_id: str,
        call_id: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать результат выполнения инструмента.
        
        Делегирует в ToolResultHandler.
        
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
        logger.debug(
            f"Делегирование process_tool_result в ToolResultHandler "
            f"для сессии {session_id}, call_id={call_id}"
        )
        
        # Делегировать в ToolResultHandler с блокировкой сессии
        async with self._lock_manager.lock(session_id):
            async for chunk in self._tool_result_handler.handle(
                session_id=session_id,
                call_id=call_id,
                result=result,
                error=error
            ):
                yield chunk
    
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
        
        Делегирует в HITLDecisionHandler.
        
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
        logger.debug(
            f"Делегирование process_hitl_decision в HITLDecisionHandler "
            f"для сессии {session_id}, call_id={call_id}, decision={decision}"
        )
        
        # Делегировать в HITLDecisionHandler с блокировкой сессии
        async with self._lock_manager.lock(session_id):
            async for chunk in self._hitl_handler.handle(
                session_id=session_id,
                call_id=call_id,
                decision=decision,
                modified_arguments=modified_arguments,
                feedback=feedback
            ):
                yield chunk
    
    async def reset_session(self, session_id: str) -> None:
        """
        Сбросить сессию в начальное состояние (Orchestrator).
        
        Делегирует в AgentSwitcher.
        
        Args:
            session_id: ID сессии
            
        Пример:
            >>> await service.reset_session("session-1")
        """
        logger.debug(
            f"Делегирование reset_session в AgentSwitcher "
            f"для сессии {session_id}"
        )
        
        await self._agent_switcher.reset_to_orchestrator(session_id)

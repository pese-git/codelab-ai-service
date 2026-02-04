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
    - PlanApprovalHandler - обработка Plan Approval решений
    
    Обеспечивает обратную совместимость с существующим API.
    
    Атрибуты:
        _message_processor: Процессор сообщений
        _agent_switcher: Switcher агентов
        _tool_result_handler: Handler результатов инструментов
        _hitl_handler: Handler HITL решений
        _plan_approval_handler: Handler Plan Approval решений (опционально)
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
        lock_manager,  # SessionLockManager
        plan_approval_handler=None,  # PlanApprovalHandler (optional)
        plan_repository=None,  # PlanRepository (optional)
        execution_coordinator=None,  # ExecutionCoordinator (optional)
        session_service=None,  # SessionManagementService (optional)
        stream_handler=None  # IStreamHandler (optional)
    ):
        """
        Инициализация сервиса-фасада.
        
        Args:
            message_processor: Процессор сообщений
            agent_switcher: Switcher агентов
            tool_result_handler: Handler результатов инструментов
            hitl_handler: Handler HITL решений
            lock_manager: Менеджер блокировок сессий
            plan_approval_handler: Handler Plan Approval решений (опционально)
            plan_repository: Repository для поиска активных планов (опционально)
            execution_coordinator: Coordinator для продолжения execution (опционально)
            session_service: Session service для execution (опционально)
            stream_handler: Stream handler для execution (опционально)
        """
        self._message_processor = message_processor
        self._agent_switcher = agent_switcher
        self._tool_result_handler = tool_result_handler
        self._hitl_handler = hitl_handler
        self._plan_approval_handler = plan_approval_handler
        self._lock_manager = lock_manager
        self._plan_repository = plan_repository
        self._execution_coordinator = execution_coordinator
        self._session_service = session_service
        self._stream_handler = stream_handler
        
        logger.info(
            f"MessageOrchestrationService (фасад) инициализирован "
            f"(plan_approval={'yes' if plan_approval_handler else 'no'}, "
            f"resumable_execution={'yes' if (plan_repository and execution_coordinator) else 'no'})"
        )
    
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
        # ToolResultHandler проверит активный план и пропустит agent.process() если нужно
        async with self._lock_manager.lock(session_id):
            async for chunk in self._tool_result_handler.handle(
                session_id=session_id,
                call_id=call_id,
                result=result,
                error=error
            ):
                yield chunk
            
            # ✅ НОВОЕ: После обработки tool_result проверить активный plan
            # Если есть IN_PROGRESS plan - продолжить execution (следующая subtask)
            if self._plan_repository and self._execution_coordinator and self._session_service and self._stream_handler:
                active_plan = await self._get_active_plan_for_session(session_id)
                
                if active_plan:
                    logger.info(
                        f"Found active plan {active_plan.id} for session {session_id}, "
                        f"resuming execution"
                    )
                    
                    # Продолжить execution (следующая subtask)
                    async for chunk in self._execution_coordinator.execute_plan(
                        plan_id=active_plan.id,
                        session_id=session_id,
                        session_service=self._session_service,
                        stream_handler=self._stream_handler
                    ):
                        yield chunk
                    
                    logger.info(f"Plan execution resumed for plan {active_plan.id}")
                else:
                    logger.debug(f"No active plan found for session {session_id}")
    
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
    
    async def process_plan_decision(
        self,
        session_id: str,
        approval_request_id: str,
        decision: str,
        feedback: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать Plan Approval решение пользователя.
        
        Делегирует в PlanApprovalHandler.
        
        Args:
            session_id: ID сессии
            approval_request_id: ID запроса на одобрение
            decision: Решение пользователя (approve/reject/modify)
            feedback: Обратная связь пользователя (для reject/modify)
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            ValueError: Если PlanApprovalHandler не настроен
            
        Пример:
            >>> async for chunk in service.process_plan_decision(
            ...     session_id="session-1",
            ...     approval_request_id="plan-approval-123",
            ...     decision="approve"
            ... ):
            ...     print(chunk)
        """
        if not self._plan_approval_handler:
            error_msg = "Plan approval not configured"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                is_final=True
            )
            return
        
        logger.debug(
            f"Делегирование process_plan_decision в PlanApprovalHandler "
            f"для сессии {session_id}, approval_request_id={approval_request_id}, "
            f"decision={decision}"
        )
        
        # Делегировать в PlanApprovalHandler с блокировкой сессии
        async with self._lock_manager.lock(session_id):
            async for chunk in self._plan_approval_handler.handle(
                session_id=session_id,
                approval_request_id=approval_request_id,
                decision=decision,
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
    
    async def _get_active_plan_for_session(self, session_id: str):
        """
        Получить активный plan для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Plan со статусом IN_PROGRESS или None
        """
        from ..entities.plan import PlanStatus
        
        try:
            # Использовать существующий метод find_by_session_id
            # Он возвращает последний план в статусе IN_PROGRESS или APPROVED
            plan = await self._plan_repository.find_by_session_id(session_id)
            
            if plan and plan.status == PlanStatus.IN_PROGRESS:
                logger.debug(f"Found active plan {plan.id} for session {session_id}")
                return plan
            else:
                logger.debug(f"No active plan (IN_PROGRESS) found for session {session_id}")
                return None
            
        except Exception as e:
            logger.warning(f"Error finding active plan: {e}")
            return None

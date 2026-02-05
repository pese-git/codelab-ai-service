"""
Use Case для обработки решений пользователя по approval запросам.

Координирует обработку HITL и Plan Approval решений.
"""

import logging
from typing import Optional, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from .base_use_case import StreamingUseCase
from ...models.schemas import StreamChunk

logger = logging.getLogger("agent-runtime.use_cases.handle_approval")


class ApprovalType(str, Enum):
    """Тип approval запроса."""
    HITL = "hitl"  # Human-in-the-Loop для tool calls
    PLAN = "plan"  # Plan Approval для execution plans


@dataclass
class HandleApprovalRequest:
    """
    Запрос на обработку approval решения.
    
    Attributes:
        session_id: ID сессии
        approval_type: Тип approval (HITL или Plan)
        approval_id: ID approval запроса (call_id для HITL, approval_request_id для Plan)
        decision: Решение пользователя (approve/reject/edit/modify)
        modified_arguments: Модифицированные аргументы (для HITL edit)
        feedback: Обратная связь пользователя (для reject)
    
    Пример HITL:
        >>> request = HandleApprovalRequest(
        ...     session_id="session-123",
        ...     approval_type=ApprovalType.HITL,
        ...     approval_id="call-456",
        ...     decision="approve"
        ... )
    
    Пример Plan:
        >>> request = HandleApprovalRequest(
        ...     session_id="session-123",
        ...     approval_type=ApprovalType.PLAN,
        ...     approval_id="plan-approval-789",
        ...     decision="approve"
        ... )
    """
    session_id: str
    approval_type: ApprovalType
    approval_id: str
    decision: str
    modified_arguments: Optional[dict] = None
    feedback: Optional[str] = None


class HandleApprovalUseCase(StreamingUseCase[HandleApprovalRequest, StreamChunk]):
    """
    Use Case для обработки approval решений пользователя.
    
    Поддерживает два типа approval:
    1. HITL (Human-in-the-Loop) - для tool calls
    2. Plan Approval - для execution plans
    
    Координирует:
    1. Валидацию решения
    2. Обработку через соответствующий handler
    3. Продолжение диалога/execution
    4. Streaming ответа клиенту
    
    Зависимости:
        - HITLDecisionHandler: Обработка HITL решений
        - PlanApprovalHandler: Обработка Plan Approval решений
        - SessionLockManager: Управление блокировками
    
    Пример:
        >>> use_case = HandleApprovalUseCase(
        ...     hitl_handler=hitl_handler,
        ...     plan_approval_handler=plan_approval_handler,
        ...     lock_manager=lock_manager
        ... )
        >>> request = HandleApprovalRequest(
        ...     session_id="session-123",
        ...     approval_type=ApprovalType.HITL,
        ...     approval_id="call-456",
        ...     decision="approve"
        ... )
        >>> async for chunk in use_case.execute(request):
        ...     print(chunk)
    """
    
    def __init__(
        self,
        hitl_handler,  # HITLDecisionHandler
        plan_approval_handler,  # PlanApprovalHandler
        lock_manager  # SessionLockManager
    ):
        """
        Инициализация Use Case.
        
        Args:
            hitl_handler: Handler HITL решений из Domain Layer
            plan_approval_handler: Handler Plan Approval решений из Domain Layer
            lock_manager: Менеджер блокировок сессий
        """
        self._hitl_handler = hitl_handler
        self._plan_approval_handler = plan_approval_handler
        self._lock_manager = lock_manager
        
        logger.debug("HandleApprovalUseCase инициализирован")
    
    async def execute(
        self,
        request: HandleApprovalRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить обработку approval решения.
        
        Args:
            request: Запрос с параметрами обработки
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            ValueError: Если approval_type невалиден или handler не настроен
            SessionNotFoundError: Если сессия не найдена
            
        Пример потока для HITL:
            1. tool_result (результат выполнения tool)
            2. assistant_message (продолжение ответа)
            3. done (завершение)
        
        Пример потока для Plan:
            1. plan_execution_started (начало execution)
            2. subtask_started (начало subtask)
            3. tool_call (вызовы инструментов)
            4. done (завершение)
        """
        logger.info(
            f"Обработка {request.approval_type.value} approval для сессии {request.session_id}, "
            f"approval_id={request.approval_id}, decision={request.decision}"
        )
        
        try:
            # Блокировка сессии для предотвращения конкурентных запросов
            async with self._lock_manager.lock(request.session_id):
                if request.approval_type == ApprovalType.HITL:
                    # Обработка HITL решения
                    async for chunk in self._handle_hitl_decision(request):
                        yield chunk
                
                elif request.approval_type == ApprovalType.PLAN:
                    # Обработка Plan Approval решения
                    async for chunk in self._handle_plan_decision(request):
                        yield chunk
                
                else:
                    error_msg = f"Unsupported approval type: {request.approval_type}"
                    logger.error(error_msg)
                    yield StreamChunk(
                        type="error",
                        error=error_msg,
                        is_final=True
                    )
        
        except Exception as e:
            logger.error(
                f"Ошибка обработки approval для сессии {request.session_id}: {e}",
                exc_info=True
            )
            # Отправить error chunk клиенту
            yield StreamChunk(
                type="error",
                error=str(e),
                is_final=True
            )
    
    async def _handle_hitl_decision(
        self,
        request: HandleApprovalRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать HITL решение.
        
        Args:
            request: Запрос с параметрами
            
        Yields:
            StreamChunk: Чанки для SSE streaming
        """
        logger.debug(
            f"Обработка HITL решения: call_id={request.approval_id}, "
            f"decision={request.decision}"
        )
        
        # Делегировать в HITLDecisionHandler (Domain Layer)
        async for chunk in self._hitl_handler.handle(
            session_id=request.session_id,
            call_id=request.approval_id,
            decision=request.decision,
            modified_arguments=request.modified_arguments,
            feedback=request.feedback
        ):
            yield chunk
            
            # Логирование важных событий
            if chunk.type == "tool_result":
                logger.info(
                    f"HITL decision processed: {request.decision} "
                    f"для call_id={request.approval_id}"
                )
    
    async def _handle_plan_decision(
        self,
        request: HandleApprovalRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать Plan Approval решение.
        
        Args:
            request: Запрос с параметрами
            
        Yields:
            StreamChunk: Чанки для SSE streaming
        """
        if not self._plan_approval_handler:
            error_msg = "Plan approval handler not configured"
            logger.error(error_msg)
            yield StreamChunk(
                type="error",
                error=error_msg,
                is_final=True
            )
            return
        
        logger.debug(
            f"Обработка Plan Approval решения: "
            f"approval_request_id={request.approval_id}, decision={request.decision}"
        )
        
        # Делегировать в PlanApprovalHandler (Domain Layer)
        async for chunk in self._plan_approval_handler.handle(
            session_id=request.session_id,
            approval_request_id=request.approval_id,
            decision=request.decision,
            feedback=request.feedback
        ):
            yield chunk
            
            # Логирование важных событий
            if chunk.type == "plan_execution_started":
                logger.info(
                    f"Plan execution started после approval: "
                    f"plan_id={chunk.metadata.get('plan_id')}"
                )
            elif chunk.type == "plan_execution_rejected":
                logger.info(
                    f"Plan execution rejected: "
                    f"plan_id={chunk.metadata.get('plan_id')}"
                )

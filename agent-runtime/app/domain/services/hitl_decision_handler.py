"""
Сервис обработки HITL (Human-in-the-Loop) решений пользователя.

Отвечает за обработку решений пользователя по запросам на одобрение
инструментов и продолжение обработки после принятия решения.
"""

import json
import logging
from typing import AsyncGenerator, Optional, TYPE_CHECKING

from ...models.schemas import StreamChunk

if TYPE_CHECKING:
    from .session_management import SessionManagementService
    from .message_processor import MessageProcessor

logger = logging.getLogger("agent-runtime.domain.hitl_decision_handler")


class HITLDecisionHandler:
    """
    Сервис обработки HITL решений пользователя.
    
    Ответственности:
    - Валидация решения (approve/edit/reject)
    - Получение pending state
    - Логирование решения в audit
    - Обработка решения и добавление в историю
    - Продолжение обработки через MessageProcessor
    
    Атрибуты:
        _hitl_service: Сервис HITL
        _session_service: Сервис управления сессиями
        _message_processor: Процессор сообщений для продолжения
    """
    
    def __init__(
        self,
        hitl_service,  # HITLService
        session_service: "SessionManagementService",
        message_processor: "MessageProcessor"
    ):
        """
        Инициализация handler.
        
        Args:
            hitl_service: Сервис HITL
            session_service: Сервис управления сессиями
            message_processor: Процессор сообщений для продолжения
        """
        self._hitl_service = hitl_service
        self._session_service = session_service
        self._message_processor = message_processor
        
        logger.debug("HITLDecisionHandler инициализирован")
    
    async def handle(
        self,
        session_id: str,
        call_id: str,
        decision: str,
        modified_arguments: Optional[dict] = None,
        feedback: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать HITL решение пользователя.
        
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
        """
        from ...models.hitl_models import HITLDecision
        
        logger.info(
            f"Обработка HITL решения для сессии {session_id}: "
            f"call_id={call_id}, decision={decision}"
        )
        
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
        result = await self._process_decision(
            decision_enum=decision_enum,
            pending_state=pending_state,
            modified_arguments=modified_arguments,
            feedback=feedback
        )
        
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
        # Используем MessageProcessor для продолжения после tool_result
        async for chunk in self._message_processor.process(
            session_id=session_id,
            message=""  # Пустое сообщение = продолжить после tool_result
        ):
            yield chunk
    
    async def _process_decision(
        self,
        decision_enum,  # HITLDecision
        pending_state,
        modified_arguments: Optional[dict],
        feedback: Optional[str]
    ) -> dict:
        """
        Обработать решение и создать результат.
        
        Args:
            decision_enum: Enum решения
            pending_state: Pending state из HITL service
            modified_arguments: Модифицированные аргументы (для edit)
            feedback: Обратная связь (для reject)
            
        Returns:
            Словарь с результатом решения
        """
        from ...models.hitl_models import HITLDecision
        
        if decision_enum == HITLDecision.APPROVE:
            # Выполнить инструмент с оригинальными аргументами
            logger.info(f"HITL APPROVED: executing {pending_state.tool_name}")
            return {
                "status": "approved",
                "tool_name": pending_state.tool_name,
                "arguments": pending_state.arguments
            }
            
        elif decision_enum == HITLDecision.EDIT:
            # Выполнить инструмент с модифицированными аргументами
            logger.info(
                f"HITL EDITED: executing {pending_state.tool_name} with modified args"
            )
            return {
                "status": "approved_with_edits",
                "tool_name": pending_state.tool_name,
                "arguments": modified_arguments or pending_state.arguments
            }
            
        elif decision_enum == HITLDecision.REJECT:
            # Не выполнять, отправить feedback LLM
            logger.info(f"HITL REJECTED: {pending_state.tool_name}, feedback={feedback}")
            return {
                "status": "rejected",
                "tool_name": pending_state.tool_name,
                "feedback": feedback or "User rejected this operation"
            }
        
        # Не должно произойти из-за валидации выше
        raise ValueError(f"Unexpected decision: {decision_enum}")

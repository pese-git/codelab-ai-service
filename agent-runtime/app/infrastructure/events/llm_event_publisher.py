"""
Event Publisher для LLM событий.

Адаптер для публикации событий, связанных с LLM запросами,
через глобальную шину событий.
"""

import logging
from typing import Optional

from ...events.event_bus import event_bus
from ...events.llm_events import (
    LLMRequestStartedEvent,
    LLMRequestCompletedEvent,
    LLMRequestFailedEvent
)
from ...events.tool_events import (
    ToolExecutionRequestedEvent,
    ToolApprovalRequiredEvent
)
from ...domain.entities.llm_response import TokenUsage

logger = logging.getLogger("agent-runtime.infrastructure.llm_event_publisher")


class LLMEventPublisher:
    """
    Адаптер для публикации LLM событий.
    
    Инкапсулирует логику публикации событий через event bus,
    предоставляя удобный интерфейс для Application Layer.
    
    Ответственность:
    - Создание событий с правильными параметрами
    - Публикация через event bus
    - Логирование публикаций
    
    Пример:
        >>> publisher = LLMEventPublisher()
        >>> await publisher.publish_request_started(
        ...     session_id="session-1",
        ...     model="gpt-4",
        ...     messages_count=5,
        ...     tools_count=10
        ... )
    """
    
    def __init__(self):
        """Инициализация publisher"""
        self._event_bus = event_bus
        logger.debug("LLMEventPublisher initialized")
    
    async def publish_request_started(
        self,
        session_id: str,
        model: str,
        messages_count: int,
        tools_count: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Опубликовать событие начала LLM запроса.
        
        Args:
            session_id: ID сессии
            model: Имя модели
            messages_count: Количество сообщений в истории
            tools_count: Количество доступных инструментов
            correlation_id: ID для трассировки (опционально)
        """
        logger.info(
            f"📊 Publishing LLM_REQUEST_STARTED event for session {session_id}"
        )
        
        event = LLMRequestStartedEvent(
            session_id=session_id,
            model=model,
            messages_count=messages_count,
            tools_count=tools_count,
            correlation_id=correlation_id
        )
        
        await self._event_bus.publish(event)
        logger.debug("✓ LLM_REQUEST_STARTED event published")
    
    async def publish_request_completed(
        self,
        session_id: str,
        model: str,
        duration_ms: int,
        usage: TokenUsage,
        has_tool_calls: bool,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Опубликовать событие завершения LLM запроса.
        
        Args:
            session_id: ID сессии
            model: Имя модели
            duration_ms: Длительность запроса в миллисекундах
            usage: Информация об использовании токенов
            has_tool_calls: Содержит ли ответ tool calls
            correlation_id: ID для трассировки (опционально)
        """
        logger.info(
            f"📊 Publishing LLM_REQUEST_COMPLETED event "
            f"({'with tool calls' if has_tool_calls else 'assistant message'}) "
            f"for session {session_id}"
        )
        
        event = LLMRequestCompletedEvent(
            session_id=session_id,
            model=model,
            duration_ms=duration_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            has_tool_calls=has_tool_calls,
            correlation_id=correlation_id
        )
        
        await self._event_bus.publish(event)
        logger.debug("✓ LLM_REQUEST_COMPLETED event published")
    
    async def publish_request_failed(
        self,
        session_id: str,
        model: str,
        error: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Опубликовать событие ошибки LLM запроса.
        
        Args:
            session_id: ID сессии
            model: Имя модели
            error: Сообщение об ошибке
            correlation_id: ID для трассировки (опционально)
        """
        logger.error(
            f"📊 Publishing LLM_REQUEST_FAILED event for session {session_id}: {error}"
        )
        
        event = LLMRequestFailedEvent(
            session_id=session_id,
            model=model,
            error=error,
            correlation_id=correlation_id
        )
        
        await self._event_bus.publish(event)
        logger.debug("✓ LLM_REQUEST_FAILED event published")
    
    async def publish_tool_execution_requested(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict,
        call_id: str,
        agent: str = "unknown",
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Опубликовать событие запроса выполнения инструмента.
        
        Args:
            session_id: ID сессии
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            call_id: ID вызова инструмента
            agent: Имя агента, запросившего инструмент
            correlation_id: ID для трассировки (опционально)
        """
        logger.info(
            f"📊 Publishing TOOL_EXECUTION_REQUESTED event: "
            f"{tool_name} (call_id={call_id})"
        )
        
        event = ToolExecutionRequestedEvent(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            call_id=call_id,
            agent=agent,
            correlation_id=correlation_id
        )
        
        await self._event_bus.publish(event)
        logger.debug("✓ TOOL_EXECUTION_REQUESTED event published")
    
    async def publish_tool_approval_required(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict,
        call_id: str,
        reason: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Опубликовать событие необходимости одобрения инструмента.
        
        Args:
            session_id: ID сессии
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            call_id: ID вызова инструмента
            reason: Причина необходимости одобрения
            correlation_id: ID для трассировки (опционально)
        """
        logger.info(
            f"📊 Publishing TOOL_APPROVAL_REQUIRED event: "
            f"{tool_name} (call_id={call_id}, reason={reason})"
        )
        
        event = ToolApprovalRequiredEvent(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            call_id=call_id,
            reason=reason,
            correlation_id=correlation_id
        )
        
        await self._event_bus.publish(event)
        logger.debug("✓ TOOL_APPROVAL_REQUIRED event published")

"""
Entity для взаимодействия с LLM.

Инкапсулирует полный цикл запрос-ответ с LLM провайдером.
"""

from datetime import datetime
from typing import Optional
from pydantic import Field

from ...shared.base_entity import BaseEntity
from ..value_objects.llm_request_id import LLMRequestId
from .llm_request import LLMRequest
from ...entities.llm_response import LLMResponse


class LLMInteraction(BaseEntity):
    """
    Entity для полного цикла взаимодействия с LLM.
    
    Отслеживает запрос, ответ, время выполнения и возможные ошибки.
    
    Атрибуты:
        id: Уникальный идентификатор взаимодействия
        request: LLM запрос
        response: LLM ответ (опционально, заполняется после получения)
        started_at: Время начала взаимодействия
        completed_at: Время завершения (опционально)
        error: Сообщение об ошибке (опционально)
        duration_ms: Длительность в миллисекундах (вычисляется)
    
    Examples:
        >>> interaction = LLMInteraction.start(request)
        >>> # ... выполнение запроса ...
        >>> interaction.complete(response)
        >>> duration = interaction.get_duration_ms()
        
        >>> # В случае ошибки
        >>> interaction.fail("Connection timeout")
    """
    
    id: LLMRequestId = Field(
        ...,
        description="Уникальный идентификатор взаимодействия"
    )
    
    request: LLMRequest = Field(
        ...,
        description="LLM запрос"
    )
    
    response: Optional[LLMResponse] = Field(
        default=None,
        description="LLM ответ"
    )
    
    started_at: datetime = Field(
        ...,
        description="Время начала взаимодействия"
    )
    
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Время завершения взаимодействия"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Сообщение об ошибке"
    )
    
    @staticmethod
    def start(request: LLMRequest) -> "LLMInteraction":
        """
        Начать новое взаимодействие с LLM.
        
        Args:
            request: LLM запрос для выполнения
            
        Returns:
            Новый LLMInteraction в состоянии "started"
            
        Example:
            >>> request = LLMRequest.create(...)
            >>> interaction = LLMInteraction.start(request)
        """
        now = datetime.utcnow()
        interaction = LLMInteraction(
            id=request.id,
            request=request,
            started_at=now
        )
        
        # Генерация Domain Event
        from ..events.llm_events import LLMInteractionStarted
        interaction.add_domain_event(LLMInteractionStarted(
            interaction_id=interaction.id.value,
            model=interaction.request.model.value,
            message_count=interaction.request.get_message_count(),
            timestamp=now
        ))
        
        return interaction
    
    def complete(self, response: LLMResponse) -> None:
        """
        Завершить взаимодействие с успешным ответом.
        
        Args:
            response: LLM ответ
            
        Raises:
            ValueError: Если взаимодействие уже завершено
            
        Example:
            >>> interaction = LLMInteraction.start(request)
            >>> # ... получение ответа ...
            >>> interaction.complete(response)
        """
        if self.is_completed():
            raise ValueError("Interaction is already completed")
        
        if self.is_failed():
            raise ValueError("Cannot complete a failed interaction")
        
        self.response = response
        self.completed_at = datetime.utcnow()
        
        # Генерация Domain Event
        from ..events.llm_events import LLMInteractionCompleted
        self.add_domain_event(LLMInteractionCompleted(
            interaction_id=self.id.value,
            model=self.request.model.value,
            duration_ms=self.get_duration_ms() or 0,
            tokens_used=response.usage.total_tokens,
            timestamp=self.completed_at
        ))
    
    def fail(self, error: str) -> None:
        """
        Завершить взаимодействие с ошибкой.
        
        Args:
            error: Сообщение об ошибке
            
        Raises:
            ValueError: Если взаимодействие уже завершено
            
        Example:
            >>> interaction = LLMInteraction.start(request)
            >>> try:
            ...     # ... выполнение запроса ...
            ... except Exception as e:
            ...     interaction.fail(str(e))
        """
        if self.is_completed():
            raise ValueError("Interaction is already completed")
        
        if self.is_failed():
            raise ValueError("Interaction is already failed")
        
        self.error = error
        self.completed_at = datetime.utcnow()
        
        # Генерация Domain Event
        from ..events.llm_events import LLMInteractionFailed
        self.add_domain_event(LLMInteractionFailed(
            interaction_id=self.id.value,
            model=self.request.model.value,
            error=error,
            duration_ms=self.get_duration_ms() or 0,
            timestamp=self.completed_at
        ))
    
    def get_duration_ms(self) -> Optional[int]:
        """
        Получить длительность взаимодействия в миллисекундах.
        
        Returns:
            Длительность в мс или None если не завершено
            
        Example:
            >>> interaction = LLMInteraction.start(request)
            >>> interaction.complete(response)
            >>> duration = interaction.get_duration_ms()
            >>> print(f"Request took {duration}ms")
        """
        if self.completed_at is None:
            return None
        
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)
    
    def is_completed(self) -> bool:
        """
        Проверить, завершено ли взаимодействие успешно.
        
        Returns:
            True если есть ответ и нет ошибки
            
        Example:
            >>> if interaction.is_completed():
            ...     print("Success!")
        """
        return self.response is not None and self.error is None
    
    def is_failed(self) -> bool:
        """
        Проверить, завершилось ли взаимодействие с ошибкой.
        
        Returns:
            True если есть ошибка
            
        Example:
            >>> if interaction.is_failed():
            ...     print(f"Error: {interaction.error}")
        """
        return self.error is not None
    
    def is_in_progress(self) -> bool:
        """
        Проверить, выполняется ли взаимодействие.
        
        Returns:
            True если не завершено и нет ошибки
            
        Example:
            >>> if interaction.is_in_progress():
            ...     print("Waiting for response...")
        """
        return not self.is_completed() and not self.is_failed()
    
    def get_tokens_used(self) -> int:
        """
        Получить количество использованных токенов.
        
        Returns:
            Количество токенов или 0 если нет ответа
            
        Example:
            >>> tokens = interaction.get_tokens_used()
            >>> print(f"Used {tokens} tokens")
        """
        if self.response is None:
            return 0
        return self.response.usage.total_tokens
    
    def get_status(self) -> str:
        """
        Получить текстовый статус взаимодействия.
        
        Returns:
            Статус: "in_progress", "completed", "failed"
            
        Example:
            >>> status = interaction.get_status()
            >>> print(f"Status: {status}")
        """
        if self.is_failed():
            return "failed"
        elif self.is_completed():
            return "completed"
        else:
            return "in_progress"
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        status = self.get_status()
        duration = self.get_duration_ms()
        duration_str = f"{duration}ms" if duration else "ongoing"
        
        return (
            f"<LLMInteraction(id='{self.id.value}', "
            f"status='{status}', "
            f"duration={duration_str})>"
        )

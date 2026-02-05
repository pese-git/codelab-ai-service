"""
Domain Events для LLM Context.

События, отслеживающие жизненный цикл LLM запросов и взаимодействий.
"""

from datetime import datetime
from typing import Optional
from pydantic import Field

from ...shared.domain_event import DomainEvent


# ============================================================================
# Request Events
# ============================================================================

class LLMRequestCreated(DomainEvent):
    """
    Событие создания LLM запроса.
    
    Генерируется при создании нового запроса к LLM провайдеру.
    
    Attributes:
        request_id: ID запроса
        model: Имя модели
        message_count: Количество сообщений
        tool_count: Количество инструментов
        timestamp: Время создания
    """
    
    request_id: str = Field(..., description="ID запроса")
    model: str = Field(..., description="Имя модели")
    message_count: int = Field(..., description="Количество сообщений")
    tool_count: int = Field(..., description="Количество инструментов")
    timestamp: datetime = Field(..., description="Время создания")


class LLMRequestValidated(DomainEvent):
    """
    Событие валидации LLM запроса.
    
    Генерируется после успешной валидации запроса.
    
    Attributes:
        request_id: ID запроса
        is_valid: Результат валидации
        timestamp: Время валидации
    """
    
    request_id: str = Field(..., description="ID запроса")
    is_valid: bool = Field(..., description="Результат валидации")
    timestamp: datetime = Field(..., description="Время валидации")


class LLMRequestSent(DomainEvent):
    """
    Событие отправки LLM запроса.
    
    Генерируется при отправке запроса к LLM провайдеру.
    
    Attributes:
        request_id: ID запроса
        model: Имя модели
        provider: Провайдер LLM
        timestamp: Время отправки
    """
    
    request_id: str = Field(..., description="ID запроса")
    model: str = Field(..., description="Имя модели")
    provider: Optional[str] = Field(None, description="Провайдер LLM")
    timestamp: datetime = Field(..., description="Время отправки")


# ============================================================================
# Response Events
# ============================================================================

class LLMResponseReceived(DomainEvent):
    """
    Событие получения LLM ответа.
    
    Генерируется при получении ответа от LLM провайдера.
    
    Attributes:
        request_id: ID запроса
        model: Имя модели
        has_content: Есть ли текстовое содержимое
        has_tool_calls: Есть ли вызовы инструментов
        tokens_used: Использовано токенов
        finish_reason: Причина завершения
        timestamp: Время получения
    """
    
    request_id: str = Field(..., description="ID запроса")
    model: str = Field(..., description="Имя модели")
    has_content: bool = Field(..., description="Есть ли текстовое содержимое")
    has_tool_calls: bool = Field(..., description="Есть ли вызовы инструментов")
    tokens_used: int = Field(..., description="Использовано токенов")
    finish_reason: Optional[str] = Field(None, description="Причина завершения")
    timestamp: datetime = Field(..., description="Время получения")


class LLMResponseProcessed(DomainEvent):
    """
    Событие обработки LLM ответа.
    
    Генерируется после применения бизнес-правил к ответу.
    
    Attributes:
        request_id: ID запроса
        requires_approval: Требуется ли одобрение
        has_warnings: Есть ли предупреждения валидации
        timestamp: Время обработки
    """
    
    request_id: str = Field(..., description="ID запроса")
    requires_approval: bool = Field(..., description="Требуется ли одобрение")
    has_warnings: bool = Field(..., description="Есть ли предупреждения")
    timestamp: datetime = Field(..., description="Время обработки")


# ============================================================================
# Interaction Events
# ============================================================================

class LLMInteractionStarted(DomainEvent):
    """
    Событие начала взаимодействия с LLM.
    
    Генерируется при начале полного цикла запрос-ответ.
    
    Attributes:
        interaction_id: ID взаимодействия
        model: Имя модели
        message_count: Количество сообщений
        timestamp: Время начала
    """
    
    interaction_id: str = Field(..., description="ID взаимодействия")
    model: str = Field(..., description="Имя модели")
    message_count: int = Field(..., description="Количество сообщений")
    timestamp: datetime = Field(..., description="Время начала")


class LLMInteractionCompleted(DomainEvent):
    """
    Событие успешного завершения взаимодействия.
    
    Генерируется при успешном получении ответа от LLM.
    
    Attributes:
        interaction_id: ID взаимодействия
        model: Имя модели
        duration_ms: Длительность в миллисекундах
        tokens_used: Использовано токенов
        timestamp: Время завершения
    """
    
    interaction_id: str = Field(..., description="ID взаимодействия")
    model: str = Field(..., description="Имя модели")
    duration_ms: int = Field(..., description="Длительность в мс")
    tokens_used: int = Field(..., description="Использовано токенов")
    timestamp: datetime = Field(..., description="Время завершения")


class LLMInteractionFailed(DomainEvent):
    """
    Событие неудачного завершения взаимодействия.
    
    Генерируется при ошибке во время взаимодействия с LLM.
    
    Attributes:
        interaction_id: ID взаимодействия
        model: Имя модели
        error: Сообщение об ошибке
        duration_ms: Длительность до ошибки в миллисекундах
        timestamp: Время ошибки
    """
    
    interaction_id: str = Field(..., description="ID взаимодействия")
    model: str = Field(..., description="Имя модели")
    error: str = Field(..., description="Сообщение об ошибке")
    duration_ms: int = Field(..., description="Длительность до ошибки в мс")
    timestamp: datetime = Field(..., description="Время ошибки")

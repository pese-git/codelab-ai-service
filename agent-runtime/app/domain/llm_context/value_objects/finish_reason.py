"""
Value Object для причины завершения генерации LLM.

Инкапсулирует валидацию и работу с причинами завершения.
"""

from enum import Enum
from pydantic import Field, field_validator

from ...shared.value_object import ValueObject


class FinishReasonType(str, Enum):
    """Типы причин завершения генерации."""
    
    STOP = "stop"  # Нормальное завершение
    LENGTH = "length"  # Достигнут лимит токенов
    TOOL_CALLS = "tool_calls"  # Вызов инструментов
    CONTENT_FILTER = "content_filter"  # Фильтр контента
    ERROR = "error"  # Ошибка
    UNKNOWN = "unknown"  # Неизвестная причина


class FinishReason(ValueObject):
    """
    Value Object для причины завершения генерации LLM.
    
    Значения:
    - STOP: Нормальное завершение (модель закончила генерацию)
    - LENGTH: Достигнут лимит токенов
    - TOOL_CALLS: Модель запросила вызов инструментов
    - CONTENT_FILTER: Сработал фильтр контента
    - ERROR: Произошла ошибка
    - UNKNOWN: Неизвестная причина
    
    Examples:
        >>> reason = FinishReason.stop()
        >>> reason.is_normal()
        True
        
        >>> reason = FinishReason.tool_calls()
        >>> reason.requires_action()
        True
        
        >>> reason = FinishReason(value="length")
        >>> reason.is_truncated()
        True
    """
    
    value: str = Field(
        ...,
        description="Причина завершения генерации"
    )
    
    @field_validator("value")
    @classmethod
    def validate_finish_reason(cls, v: str) -> str:
        """Валидация причины завершения."""
        if not v or not v.strip():
            raise ValueError("Finish reason cannot be empty")
        
        # Нормализация значения
        normalized = v.strip().lower()
        
        # Проверка на известные значения
        valid_values = [r.value for r in FinishReasonType]
        if normalized not in valid_values:
            # Если неизвестное значение, используем UNKNOWN
            return FinishReasonType.UNKNOWN.value
        
        return normalized
    
    @staticmethod
    def stop() -> "FinishReason":
        """
        Создать причину нормального завершения.
        
        Returns:
            FinishReason со значением STOP
            
        Example:
            >>> reason = FinishReason.stop()
            >>> reason.value
            'stop'
        """
        return FinishReason(value=FinishReasonType.STOP.value)
    
    @staticmethod
    def length() -> "FinishReason":
        """
        Создать причину завершения по лимиту токенов.
        
        Returns:
            FinishReason со значением LENGTH
            
        Example:
            >>> reason = FinishReason.length()
            >>> reason.is_truncated()
            True
        """
        return FinishReason(value=FinishReasonType.LENGTH.value)
    
    @staticmethod
    def tool_calls() -> "FinishReason":
        """
        Создать причину завершения для вызова инструментов.
        
        Returns:
            FinishReason со значением TOOL_CALLS
            
        Example:
            >>> reason = FinishReason.tool_calls()
            >>> reason.requires_action()
            True
        """
        return FinishReason(value=FinishReasonType.TOOL_CALLS.value)
    
    @staticmethod
    def content_filter() -> "FinishReason":
        """
        Создать причину завершения из-за фильтра контента.
        
        Returns:
            FinishReason со значением CONTENT_FILTER
            
        Example:
            >>> reason = FinishReason.content_filter()
            >>> reason.is_error()
            True
        """
        return FinishReason(value=FinishReasonType.CONTENT_FILTER.value)
    
    @staticmethod
    def error() -> "FinishReason":
        """
        Создать причину завершения из-за ошибки.
        
        Returns:
            FinishReason со значением ERROR
            
        Example:
            >>> reason = FinishReason.error()
            >>> reason.is_error()
            True
        """
        return FinishReason(value=FinishReasonType.ERROR.value)
    
    @staticmethod
    def unknown() -> "FinishReason":
        """
        Создать причину неизвестного завершения.
        
        Returns:
            FinishReason со значением UNKNOWN
        """
        return FinishReason(value=FinishReasonType.UNKNOWN.value)
    
    @staticmethod
    def from_string(value: str) -> "FinishReason":
        """
        Создать FinishReason из строки.
        
        Args:
            value: Строковое значение причины
            
        Returns:
            FinishReason instance
            
        Example:
            >>> reason = FinishReason.from_string("stop")
            >>> reason.is_normal()
            True
        """
        return FinishReason(value=value)
    
    def is_normal(self) -> bool:
        """
        Проверить, является ли завершение нормальным.
        
        Returns:
            True если причина STOP
            
        Example:
            >>> FinishReason.stop().is_normal()
            True
            >>> FinishReason.length().is_normal()
            False
        """
        return self.value == FinishReasonType.STOP.value
    
    def is_truncated(self) -> bool:
        """
        Проверить, было ли завершение из-за лимита токенов.
        
        Returns:
            True если причина LENGTH
            
        Example:
            >>> FinishReason.length().is_truncated()
            True
        """
        return self.value == FinishReasonType.LENGTH.value
    
    def requires_action(self) -> bool:
        """
        Проверить, требуется ли действие (вызов инструментов).
        
        Returns:
            True если причина TOOL_CALLS
            
        Example:
            >>> FinishReason.tool_calls().requires_action()
            True
        """
        return self.value == FinishReasonType.TOOL_CALLS.value
    
    def is_error(self) -> bool:
        """
        Проверить, является ли завершение ошибочным.
        
        Returns:
            True если причина ERROR или CONTENT_FILTER
            
        Example:
            >>> FinishReason.error().is_error()
            True
            >>> FinishReason.content_filter().is_error()
            True
        """
        return self.value in [
            FinishReasonType.ERROR.value,
            FinishReasonType.CONTENT_FILTER.value
        ]
    
    def get_description(self) -> str:
        """
        Получить описание причины завершения.
        
        Returns:
            Текстовое описание
            
        Example:
            >>> FinishReason.stop().get_description()
            'Normal completion'
            >>> FinishReason.length().get_description()
            'Token limit reached'
        """
        descriptions = {
            FinishReasonType.STOP.value: "Normal completion",
            FinishReasonType.LENGTH.value: "Token limit reached",
            FinishReasonType.TOOL_CALLS.value: "Tool calls requested",
            FinishReasonType.CONTENT_FILTER.value: "Content filter triggered",
            FinishReasonType.ERROR.value: "Error occurred",
            FinishReasonType.UNKNOWN.value: "Unknown reason",
        }
        return descriptions.get(self.value, "Unknown reason")
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        return f"<FinishReason(value='{self.value}', {self.get_description()})>"

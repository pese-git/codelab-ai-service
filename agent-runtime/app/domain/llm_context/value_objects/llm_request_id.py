"""
Value Object для ID LLM запроса.

Инкапсулирует валидацию и генерацию уникальных идентификаторов.
"""

import uuid
from pydantic import Field, field_validator

from ...shared.value_object import ValueObject


class LLMRequestId(ValueObject):
    """
    Value Object для ID LLM запроса.
    
    Валидация:
    - UUID формат или строка 1-255 символов
    - Не пустое
    - Уникальность (через генерацию UUID)
    
    Examples:
        >>> request_id = LLMRequestId.generate()
        >>> str(request_id)
        'llm-req-...'
        
        >>> request_id = LLMRequestId(value="custom-id-123")
        >>> request_id.value
        'custom-id-123'
    """
    
    value: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Уникальный идентификатор LLM запроса"
    )
    
    @field_validator("value")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Валидация ID запроса."""
        if not v or not v.strip():
            raise ValueError("LLM request ID cannot be empty")
        
        # Проверка на пробелы
        if v != v.strip():
            raise ValueError("LLM request ID cannot have leading/trailing whitespace")
        
        # Проверка на недопустимые символы
        if any(char in v for char in ["\n", "\r", "\t"]):
            raise ValueError("LLM request ID cannot contain whitespace characters")
        
        return v
    
    @staticmethod
    def generate() -> "LLMRequestId":
        """
        Сгенерировать новый уникальный ID.
        
        Returns:
            LLMRequestId с UUID значением
            
        Example:
            >>> request_id = LLMRequestId.generate()
            >>> request_id.value.startswith('llm-req-')
            True
        """
        unique_id = str(uuid.uuid4())
        return LLMRequestId(value=f"llm-req-{unique_id}")
    
    @staticmethod
    def from_string(value: str) -> "LLMRequestId":
        """
        Создать LLMRequestId из строки.
        
        Args:
            value: Строковое значение ID
            
        Returns:
            LLMRequestId instance
            
        Example:
            >>> request_id = LLMRequestId.from_string("custom-123")
            >>> request_id.value
            'custom-123'
        """
        return LLMRequestId(value=value)
    
    def is_generated(self) -> bool:
        """
        Проверить, был ли ID сгенерирован автоматически.
        
        Returns:
            True если ID имеет префикс 'llm-req-'
            
        Example:
            >>> LLMRequestId.generate().is_generated()
            True
            >>> LLMRequestId(value="custom").is_generated()
            False
        """
        return self.value.startswith("llm-req-")
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        return f"<LLMRequestId(value='{self.value}')>"
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)

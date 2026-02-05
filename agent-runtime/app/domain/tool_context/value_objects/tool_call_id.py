"""
Value Object для ID вызова инструмента.

Инкапсулирует валидацию и генерацию уникальных идентификаторов.
"""

import uuid
import re
from typing import ClassVar, Optional

from ...shared.value_object import ValueObject


class ToolCallId(ValueObject):
    """
    Value Object для ID вызова инструмента.
    
    Валидация:
    - Не пустое
    - Формат: call_xxx или UUID
    - Уникальность гарантируется при генерации
    
    Примеры:
        >>> call_id = ToolCallId.generate()
        >>> str(call_id).startswith('call_')
        True
        >>> call_id2 = ToolCallId.from_string("call_abc123")
        >>> str(call_id2)
        'call_abc123'
    """
    
    value: str
    
    # Паттерны валидации
    CALL_PATTERN: ClassVar[re.Pattern] = re.compile(r'^call_[a-zA-Z0-9_-]+$')
    UUID_PATTERN: ClassVar[re.Pattern] = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    def model_post_init(self, __context) -> None:
        """Валидация после инициализации."""
        super().model_post_init(__context)
        self._validate()
    
    def _validate(self) -> None:
        """
        Валидировать ID вызова инструмента.
        
        Raises:
            ValueError: Если ID невалиден
        """
        if not self.value:
            raise ValueError("Tool call ID cannot be empty")
        
        if len(self.value) > 255:
            raise ValueError(
                f"Tool call ID too long: {len(self.value)} characters (max 255)"
            )
        
        # Проверка формата: call_xxx или UUID
        is_call_format = self.CALL_PATTERN.match(self.value)
        is_uuid_format = self.UUID_PATTERN.match(self.value)
        
        if not (is_call_format or is_uuid_format):
            raise ValueError(
                f"Invalid tool call ID format: '{self.value}'. "
                "Must be 'call_xxx' or UUID format"
            )
    
    @staticmethod
    def generate() -> "ToolCallId":
        """
        Сгенерировать новый уникальный ID.
        
        Returns:
            ToolCallId с уникальным значением
            
        Example:
            >>> call_id = ToolCallId.generate()
            >>> str(call_id).startswith('call_')
            True
        """
        unique_id = str(uuid.uuid4())[:8]
        return ToolCallId(value=f"call_{unique_id}")
    
    @staticmethod
    def from_string(value: str) -> "ToolCallId":
        """
        Создать ToolCallId из строки.
        
        Args:
            value: ID вызова инструмента
            
        Returns:
            ToolCallId instance
            
        Example:
            >>> call_id = ToolCallId.from_string("call_abc123")
            >>> str(call_id)
            'call_abc123'
        """
        return ToolCallId(value=value)
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolCallId('{self.value}')"
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)

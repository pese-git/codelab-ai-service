"""
ApprovalId Value Object.

Типобезопасный идентификатор для запросов на утверждение.
"""

from typing import Any

from pydantic import field_validator
from app.domain.shared.value_object import ValueObject


class ApprovalId(ValueObject):
    """
    Типобезопасный идентификатор для запроса на утверждение.
    
    Обеспечивает:
    - Валидацию непустого значения
    - Валидацию отсутствия пробелов
    - Иммутабельность
    - Сравнение по значению
    
    Примеры:
        >>> approval_id = ApprovalId("req-tool-123")
        >>> str(approval_id)
        'req-tool-123'
        
        >>> ApprovalId("")  # Raises ValueError
        >>> ApprovalId("req 123")  # Raises ValueError (пробелы)
    """
    value: str
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Валидация значения ApprovalId."""
        if not v or not v.strip():
            raise ValueError("ApprovalId value cannot be empty")
        if ' ' in v:
            raise ValueError("ApprovalId value cannot contain spaces")
        return v
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ApprovalId(value='{self.value}')"
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение по значению."""
        if not isinstance(other, ApprovalId):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)

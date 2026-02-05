"""
ApprovalId Value Object.

Типобезопасный идентификатор для запросов на утверждение.
"""

from typing import Any

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
    
    def __init__(self, value: str):
        """
        Создать ApprovalId.
        
        Args:
            value: Строковый идентификатор
            
        Raises:
            ValueError: Если value пустой или содержит пробелы
        """
        if not value or not value.strip():
            raise ValueError("Approval ID cannot be empty or whitespace")
        
        if " " in value:
            raise ValueError("Approval ID cannot contain spaces")
        
        self._value = value
    
    @property
    def value(self) -> str:
        """Получить строковое значение ID."""
        return self._value
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self._value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ApprovalId('{self._value}')"
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение по значению."""
        if not isinstance(other, ApprovalId):
            return False
        return self._value == other._value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self._value)

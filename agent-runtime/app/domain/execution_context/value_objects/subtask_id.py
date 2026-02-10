"""
Value Object для идентификатора подзадачи.

Инкапсулирует валидацию и бизнес-правила для ID подзадачи.
"""

from pydantic import field_validator
from app.domain.shared.value_object import ValueObject


class SubtaskId(ValueObject):
    """
    Идентификатор подзадачи в плане выполнения.
    
    Бизнес-правила:
    - ID не может быть пустым
    - ID не может превышать 255 символов
    - ID должен быть строкой
    
    Attributes:
        value: Строковое значение идентификатора
    
    Example:
        >>> subtask_id = SubtaskId("subtask-1")
        >>> print(subtask_id.value)
        'subtask-1'
        
        >>> invalid_id = SubtaskId("")  # Raises ValueError
    """
    value: str

    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Валидация значения SubtaskId."""
        if not v or not v.strip():
            raise ValueError("SubtaskId value cannot be empty")
        return v

    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"SubtaskId('{self.value}')"
    
    def __eq__(self, other: object) -> bool:
        """Сравнение на равенство."""
        if not isinstance(other, SubtaskId):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)

"""
Value Object для идентификатора подзадачи.

Инкапсулирует валидацию и бизнес-правила для ID подзадачи.
"""

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
    
    def __init__(self, value: str):
        """
        Создать идентификатор подзадачи.
        
        Args:
            value: Строковое значение ID
            
        Raises:
            ValueError: Если ID невалиден
        """
        if not value:
            raise ValueError("Subtask ID cannot be empty")
        
        if not isinstance(value, str):
            raise ValueError(f"Subtask ID must be a string, got {type(value).__name__}")
        
        if len(value) > 255:
            raise ValueError(
                f"Subtask ID too long: {len(value)} characters (max 255)"
            )
        
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
        return f"SubtaskId('{self._value}')"
    
    def __eq__(self, other: object) -> bool:
        """Сравнение на равенство."""
        if not isinstance(other, SubtaskId):
            return False
        return self._value == other._value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self._value)

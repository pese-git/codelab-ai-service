"""
Value Object для идентификатора плана выполнения.

Инкапсулирует валидацию и бизнес-правила для ID плана.
"""

from app.domain.shared.value_object import ValueObject


class PlanId(ValueObject):
    """
    Идентификатор плана выполнения.
    
    Бизнес-правила:
    - ID не может быть пустым
    - ID не может превышать 255 символов
    - ID должен быть строкой
    
    Attributes:
        value: Строковое значение идентификатора
    
    Example:
        >>> plan_id = PlanId("plan-123")
        >>> print(plan_id.value)
        'plan-123'
        
        >>> invalid_id = PlanId("")  # Raises ValueError
    """
    
    def __init__(self, value: str):
        """
        Создать идентификатор плана.
        
        Args:
            value: Строковое значение ID
            
        Raises:
            ValueError: Если ID невалиден
        """
        if not value:
            raise ValueError("Plan ID cannot be empty")
        
        if not isinstance(value, str):
            raise ValueError(f"Plan ID must be a string, got {type(value).__name__}")
        
        if len(value) > 255:
            raise ValueError(
                f"Plan ID too long: {len(value)} characters (max 255)"
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
        return f"PlanId('{self._value}')"
    
    def __eq__(self, other: object) -> bool:
        """Сравнение на равенство."""
        if not isinstance(other, PlanId):
            return False
        return self._value == other._value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self._value)

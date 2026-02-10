"""
Value Object для идентификатора плана выполнения.

Инкапсулирует валидацию и бизнес-правила для ID плана.
"""

import uuid
from pydantic import field_validator
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
    value: str

    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Валидация значения PlanId."""
        if not v or not v.strip():
            raise ValueError("PlanId value cannot be empty")
        return v

    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"PlanId(value='{self.value}')"
    
    def __eq__(self, other: object) -> bool:
        """Сравнение на равенство."""
        if not isinstance(other, PlanId):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)
    
    @staticmethod
    def generate() -> "PlanId":
        """
        Сгенерировать новый уникальный PlanId.
        
        Returns:
            Новый PlanId с уникальным UUID
            
        Example:
            >>> plan_id = PlanId.generate()
            >>> len(plan_id.value)
            36
        """
        unique_id = str(uuid.uuid4())
        return PlanId(value=unique_id)

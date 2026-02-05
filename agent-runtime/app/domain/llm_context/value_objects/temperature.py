"""
Value Object для температуры генерации LLM.

Инкапсулирует валидацию и предустановленные значения температуры.
"""

from typing import ClassVar
from pydantic import Field, field_validator

from ...shared.value_object import ValueObject


class Temperature(ValueObject):
    """
    Value Object для температуры генерации LLM.
    
    Температура контролирует случайность генерации:
    - 0.0: Детерминированный, предсказуемый вывод
    - 0.7: Сбалансированный (рекомендуется по умолчанию)
    - 1.0: Креативный, разнообразный вывод
    - 2.0: Максимальная случайность
    
    Валидация:
    - Диапазон: 0.0 - 2.0
    - Точность: до 2 знаков после запятой
    
    Examples:
        >>> temp = Temperature.conservative()
        >>> temp.value
        0.0
        
        >>> temp = Temperature.balanced()
        >>> temp.value
        0.7
        
        >>> temp = Temperature(value=1.5)
        >>> temp.is_creative()
        True
    """
    
    value: float = Field(
        ...,
        ge=0.0,
        le=2.0,
        description="Температура генерации (0.0-2.0)"
    )
    
    # Предустановленные значения
    CONSERVATIVE: ClassVar[float] = 0.0
    BALANCED: ClassVar[float] = 0.7
    CREATIVE: ClassVar[float] = 1.0
    MAXIMUM: ClassVar[float] = 2.0
    
    @field_validator("value")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Валидация температуры."""
        if not isinstance(v, (int, float)):
            raise ValueError("Temperature must be a number")
        
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        
        # Округление до 2 знаков после запятой
        return round(float(v), 2)
    
    @staticmethod
    def conservative() -> "Temperature":
        """
        Создать консервативную температуру (0.0).
        
        Используется для:
        - Детерминированных задач
        - Генерации кода
        - Точных ответов
        
        Returns:
            Temperature с value=0.0
            
        Example:
            >>> temp = Temperature.conservative()
            >>> temp.value
            0.0
        """
        return Temperature(value=Temperature.CONSERVATIVE)
    
    @staticmethod
    def balanced() -> "Temperature":
        """
        Создать сбалансированную температуру (0.7).
        
        Используется для:
        - Общих задач
        - Диалогов
        - Рекомендуется по умолчанию
        
        Returns:
            Temperature с value=0.7
            
        Example:
            >>> temp = Temperature.balanced()
            >>> temp.value
            0.7
        """
        return Temperature(value=Temperature.BALANCED)
    
    @staticmethod
    def creative() -> "Temperature":
        """
        Создать креативную температуру (1.0).
        
        Используется для:
        - Креативных задач
        - Генерации идей
        - Разнообразных ответов
        
        Returns:
            Temperature с value=1.0
            
        Example:
            >>> temp = Temperature.creative()
            >>> temp.value
            1.0
        """
        return Temperature(value=Temperature.CREATIVE)
    
    @staticmethod
    def maximum() -> "Temperature":
        """
        Создать максимальную температуру (2.0).
        
        Используется для:
        - Экспериментов
        - Максимального разнообразия
        
        Returns:
            Temperature с value=2.0
            
        Example:
            >>> temp = Temperature.maximum()
            >>> temp.value
            2.0
        """
        return Temperature(value=Temperature.MAXIMUM)
    
    def is_conservative(self) -> bool:
        """
        Проверить, является ли температура консервативной (< 0.3).
        
        Returns:
            True если температура консервативная
            
        Example:
            >>> Temperature(value=0.0).is_conservative()
            True
            >>> Temperature(value=0.5).is_conservative()
            False
        """
        return self.value < 0.3
    
    def is_balanced(self) -> bool:
        """
        Проверить, является ли температура сбалансированной (0.3-0.9).
        
        Returns:
            True если температура сбалансированная
            
        Example:
            >>> Temperature(value=0.7).is_balanced()
            True
        """
        return 0.3 <= self.value <= 0.9
    
    def is_creative(self) -> bool:
        """
        Проверить, является ли температура креативной (> 0.9).
        
        Returns:
            True если температура креативная
            
        Example:
            >>> Temperature(value=1.5).is_creative()
            True
        """
        return self.value > 0.9
    
    def get_description(self) -> str:
        """
        Получить описание уровня температуры.
        
        Returns:
            Текстовое описание
            
        Example:
            >>> Temperature(value=0.0).get_description()
            'Conservative (deterministic)'
            >>> Temperature(value=0.7).get_description()
            'Balanced (recommended)'
        """
        if self.is_conservative():
            return "Conservative (deterministic)"
        elif self.is_balanced():
            return "Balanced (recommended)"
        else:
            return "Creative (diverse)"
    
    def __str__(self) -> str:
        """Строковое представление."""
        return f"{self.value}"
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        return f"<Temperature(value={self.value}, {self.get_description()})>"
    
    def __float__(self) -> float:
        """Преобразование в float."""
        return self.value

"""
Доменные сущности для классификации задач.

Представляют результат классификации задачи на атомарную vs сложную.
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class TaskClassification(BaseModel):
    """
    Результат классификации задачи.
    
    Определяет, является ли задача атомарной (выполняется одним агентом)
    или сложной (требует планирования и декомпозиции).
    
    Атрибуты:
        is_atomic: True если задача атомарная, False если требует планирования
        agent: Целевой агент для обработки задачи
        confidence: Уровень уверенности в классификации
        reason: Обоснование классификации
    
    Бизнес-правила:
        - Если is_atomic=False, то agent ОБЯЗАТЕЛЬНО должен быть "plan"
        - Это гарантирует, что сложные задачи не идут напрямую к исполнителям
    """
    
    is_atomic: bool = Field(
        ...,
        description="Является ли задача атомарной (single-step) или сложной (multi-step)"
    )
    
    agent: Literal["code", "plan", "debug", "explain"] = Field(
        ...,
        description="Целевой агент для обработки задачи"
    )
    
    confidence: Literal["high", "medium", "low"] = Field(
        ...,
        description="Уровень уверенности в классификации"
    )
    
    reason: str = Field(
        ...,
        description="Обоснование классификации"
    )
    
    @field_validator("agent")
    @classmethod
    def validate_non_atomic_must_be_plan(cls, v: str, info) -> str:
        """
        Валидация ОБЯЗАТЕЛЬНОГО правила: is_atomic=False → agent="plan"
        
        Это критически важное правило гарантирует, что сложные задачи
        всегда направляются на планирование, а не напрямую к исполнителям.
        
        Args:
            v: Значение поля agent
            info: Контекст валидации с доступом к другим полям
            
        Returns:
            Валидированное значение agent
            
        Raises:
            ValueError: Если правило нарушено
        """
        # Получить значение is_atomic из контекста
        is_atomic = info.data.get("is_atomic")
        
        # ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: non-atomic → plan
        if is_atomic is False and v != "plan":
            raise ValueError(
                f"RULE VIOLATION: Non-atomic tasks MUST be assigned to 'plan' agent. "
                f"Got is_atomic=False but agent='{v}'. "
                f"This ensures complex tasks go through planning phase."
            )
        
        return v
    
    def to_dict(self) -> dict:
        """
        Преобразовать в словарь для логирования и API.
        
        Returns:
            Словарь с данными классификации
        """
        return {
            "is_atomic": self.is_atomic,
            "agent": self.agent,
            "confidence": self.confidence,
            "reason": self.reason
        }
    
    def __repr__(self) -> str:
        """Строковое представление классификации"""
        return (
            f"<TaskClassification("
            f"is_atomic={self.is_atomic}, "
            f"agent='{self.agent}', "
            f"confidence='{self.confidence}')>"
        )

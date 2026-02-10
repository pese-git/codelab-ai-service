"""
PolicyAction Value Object.

Типобезопасное действие политики HITL.
"""

from enum import Enum
from typing import Any, ClassVar

from pydantic import field_validator
from app.domain.shared.value_object import ValueObject


class PolicyActionEnum(str, Enum):
    """
    Действия, которые может предпринять политика HITL.
    
    - APPROVE: Автоматически одобрить запрос
    - REJECT: Автоматически отклонить запрос
    - ASK_USER: Запросить решение у пользователя
    """
    APPROVE: ClassVar = "approve"
    REJECT: ClassVar = "reject"
    ASK_USER: ClassVar = "ask_user"


class PolicyAction(ValueObject):
    """
    
    value: PolicyActionEnum
    Типобезопасное действие политики HITL.
    
    Обеспечивает:
    - Валидацию действия из enum
    - Иммутабельность
    - Сравнение по значению
    
    Примеры:
        >>> action = PolicyAction(PolicyActionEnum.ASK_USER)
        >>> str(action)
        'ask_user'
        
        >>> action.requires_user_decision()
        True
    """
    value: PolicyActionEnum
    
    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v: Any) -> PolicyActionEnum:
        """Валидация что value является PolicyActionEnum."""
        if not isinstance(v, PolicyActionEnum):
            raise ValueError(f"value must be PolicyActionEnum, got {type(v).__name__}")
        return v
    
    def is_approve(self) -> bool:
        """Проверить, является ли действие автоматическим одобрением."""
        return self.value == PolicyActionEnum.APPROVE
    
    def is_reject(self) -> bool:
        """Проверить, является ли действие автоматическим отклонением."""
        return self.value == PolicyActionEnum.REJECT
    
    def is_ask_user(self) -> bool:
        """Проверить, требуется ли запрос решения у пользователя."""
        return self.value == PolicyActionEnum.ASK_USER
    
    def requires_user_decision(self) -> bool:
        """
        Проверить, требуется ли решение пользователя.
        
        Returns:
            True если действие ASK_USER, False для автоматических действий
        """
        return self.value == PolicyActionEnum.ASK_USER
    
    def is_automatic(self) -> bool:
        """
        Проверить, является ли действие автоматическим.
        
        Returns:
            True если действие APPROVE или REJECT
        """
        return self.value in (PolicyActionEnum.APPROVE, PolicyActionEnum.REJECT)
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"PolicyAction({self.value.name})"
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение по значению."""
        if not isinstance(other, PolicyAction):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)

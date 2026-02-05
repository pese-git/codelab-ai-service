"""
PolicyAction Value Object.

Типобезопасное действие политики HITL.
"""

from enum import Enum
from typing import Any

from app.domain.shared.value_object import ValueObject


class PolicyActionEnum(str, Enum):
    """
    Действия, которые может предпринять политика HITL.
    
    - APPROVE: Автоматически одобрить запрос
    - REJECT: Автоматически отклонить запрос
    - ASK_USER: Запросить решение у пользователя
    """
    APPROVE = "approve"
    REJECT = "reject"
    ASK_USER = "ask_user"


class PolicyAction(ValueObject):
    """
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
    
    def __init__(self, value: PolicyActionEnum):
        """
        Создать PolicyAction.
        
        Args:
            value: Значение действия из PolicyActionEnum
            
        Raises:
            ValueError: Если value не является PolicyActionEnum
        """
        if not isinstance(value, PolicyActionEnum):
            raise ValueError(
                f"Action must be PolicyActionEnum, got {type(value).__name__}"
            )
        self._value = value
    
    @property
    def value(self) -> PolicyActionEnum:
        """Получить значение действия."""
        return self._value
    
    def is_approve(self) -> bool:
        """Проверить, является ли действие автоматическим одобрением."""
        return self._value == PolicyActionEnum.APPROVE
    
    def is_reject(self) -> bool:
        """Проверить, является ли действие автоматическим отклонением."""
        return self._value == PolicyActionEnum.REJECT
    
    def is_ask_user(self) -> bool:
        """Проверить, требуется ли запрос решения у пользователя."""
        return self._value == PolicyActionEnum.ASK_USER
    
    def requires_user_decision(self) -> bool:
        """
        Проверить, требуется ли решение пользователя.
        
        Returns:
            True если действие ASK_USER, False для автоматических действий
        """
        return self._value == PolicyActionEnum.ASK_USER
    
    def is_automatic(self) -> bool:
        """
        Проверить, является ли действие автоматическим.
        
        Returns:
            True если действие APPROVE или REJECT
        """
        return self._value in (PolicyActionEnum.APPROVE, PolicyActionEnum.REJECT)
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self._value.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"PolicyAction({self._value.name})"
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение по значению."""
        if not isinstance(other, PolicyAction):
            return False
        return self._value == other._value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self._value)

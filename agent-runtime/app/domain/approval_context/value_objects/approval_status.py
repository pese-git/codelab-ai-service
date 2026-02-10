"""
ApprovalStatus Value Object.

Типобезопасный статус утверждения с валидацией переходов состояний.
"""

from enum import Enum
from typing import Any, Set, ClassVar

from pydantic import field_validator
from app.domain.shared.value_object import ValueObject


class ApprovalStatusEnum(str, Enum):
    """
    Возможные статусы утверждения.
    
    Жизненный цикл:
    - PENDING: Ожидает решения пользователя
    - APPROVED: Одобрено пользователем
    - REJECTED: Отклонено пользователем
    - EXPIRED: Истек таймаут ожидания
    """
    PENDING: ClassVar = "pending"
    APPROVED: ClassVar = "approved"
    REJECTED: ClassVar = "rejected"
    EXPIRED: ClassVar = "expired"


class ApprovalStatus(ValueObject):
    """
    
    value: ApprovalStatusEnum
    Типобезопасный статус утверждения с валидацией переходов.
    
    Обеспечивает:
    - Валидацию допустимых переходов состояний
    - Проверку терминальных состояний
    - Иммутабельность
    - Сравнение по значению
    
    Допустимые переходы:
    - PENDING → APPROVED (пользователь одобрил)
    - PENDING → REJECTED (пользователь отклонил)
    - PENDING → EXPIRED (истек таймаут)
    - APPROVED, REJECTED, EXPIRED → (терминальные состояния)
    
    Примеры:
        >>> status = ApprovalStatus(ApprovalStatusEnum.PENDING)
        >>> status.can_transition_to(ApprovalStatus(ApprovalStatusEnum.APPROVED))
        True
        
        >>> approved = ApprovalStatus(ApprovalStatusEnum.APPROVED)
        >>> approved.is_terminal()
        True
    """
    value: ApprovalStatusEnum
    
    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v: Any) -> ApprovalStatusEnum:
        """Валидация что value является ApprovalStatusEnum."""
        if not isinstance(v, ApprovalStatusEnum):
            raise ValueError(f"value must be ApprovalStatusEnum, got {type(v).__name__}")
        return v
    
    # Допустимые переходы состояний
    _VALID_TRANSITIONS: dict[ApprovalStatusEnum, Set[ApprovalStatusEnum]] = {
        ApprovalStatusEnum.PENDING: {
            ApprovalStatusEnum.APPROVED,
            ApprovalStatusEnum.REJECTED,
            ApprovalStatusEnum.EXPIRED,
        },
        ApprovalStatusEnum.APPROVED: set(),  # Терминальное состояние
        ApprovalStatusEnum.REJECTED: set(),  # Терминальное состояние
        ApprovalStatusEnum.EXPIRED: set(),   # Терминальное состояние
    }
    
    def can_transition_to(self, target: "ApprovalStatus") -> bool:
        """
        Проверить, возможен ли переход в целевой статус.
        
        Args:
            target: Целевой статус
            
        Returns:
            True если переход допустим, False иначе
            
        Примеры:
            >>> pending = ApprovalStatus(ApprovalStatusEnum.PENDING)
            >>> approved = ApprovalStatus(ApprovalStatusEnum.APPROVED)
            >>> pending.can_transition_to(approved)
            True
            
            >>> approved.can_transition_to(pending)
            False
        """
        return target.value in self._VALID_TRANSITIONS[self.value]
    
    def is_terminal(self) -> bool:
        """
        Проверить, является ли статус терминальным.
        
        Терминальные статусы: APPROVED, REJECTED, EXPIRED
        
        Returns:
            True если статус терминальный (нет допустимых переходов)
            
        Примеры:
            >>> ApprovalStatus(ApprovalStatusEnum.PENDING).is_terminal()
            False
            
            >>> ApprovalStatus(ApprovalStatusEnum.APPROVED).is_terminal()
            True
        """
        return len(self._VALID_TRANSITIONS[self.value]) == 0
    
    def is_pending(self) -> bool:
        """
        Проверить, находится ли утверждение в ожидании.
        
        Returns:
            True если статус PENDING
        """
        return self.value == ApprovalStatusEnum.PENDING
    
    def is_approved(self) -> bool:
        """
        Проверить, одобрено ли утверждение.
        
        Returns:
            True если статус APPROVED
        """
        return self.value == ApprovalStatusEnum.APPROVED
    
    def is_rejected(self) -> bool:
        """
        Проверить, отклонено ли утверждение.
        
        Returns:
            True если статус REJECTED
        """
        return self.value == ApprovalStatusEnum.REJECTED
    
    def is_expired(self) -> bool:
        """
        Проверить, истекло ли утверждение.
        
        Returns:
            True если статус EXPIRED
        """
        return self.value == ApprovalStatusEnum.EXPIRED
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ApprovalStatus({self.value.name})"
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение по значению."""
        if not isinstance(other, ApprovalStatus):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)

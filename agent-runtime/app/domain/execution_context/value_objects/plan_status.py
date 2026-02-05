"""
Value Object для статуса плана выполнения.

Инкапсулирует валидацию и бизнес-правила для статусов планов.
"""

from enum import Enum
from typing import Set

from app.domain.shared.value_object import ValueObject


class PlanStatusEnum(str, Enum):
    """
    Возможные статусы плана выполнения.
    """
    DRAFT = "draft"           # Черновик, не утвержден
    APPROVED = "approved"     # Утвержден, готов к выполнению
    IN_PROGRESS = "in_progress"  # В процессе выполнения
    COMPLETED = "completed"   # Успешно завершен
    FAILED = "failed"         # Завершен с ошибкой
    CANCELLED = "cancelled"   # Отменен


class PlanStatus(ValueObject):
    """
    Статус плана выполнения с валидацией переходов.
    
    Бизнес-правила переходов:
    - DRAFT → APPROVED, CANCELLED
    - APPROVED → IN_PROGRESS, CANCELLED, FAILED
    - IN_PROGRESS → COMPLETED, FAILED, CANCELLED
    - COMPLETED → (терминальный статус)
    - FAILED → (терминальный статус)
    - CANCELLED → (терминальный статус)
    
    Attributes:
        value: Значение статуса
    
    Example:
        >>> status = PlanStatus.draft()
        >>> status.can_transition_to(PlanStatus.approved())
        True
        
        >>> completed = PlanStatus.completed()
        >>> completed.is_terminal()
        True
    """
    
    # Допустимые переходы между статусами
    _VALID_TRANSITIONS: dict[PlanStatusEnum, Set[PlanStatusEnum]] = {
        PlanStatusEnum.DRAFT: {PlanStatusEnum.APPROVED, PlanStatusEnum.CANCELLED},
        PlanStatusEnum.APPROVED: {
            PlanStatusEnum.IN_PROGRESS,
            PlanStatusEnum.CANCELLED,
            PlanStatusEnum.FAILED
        },
        PlanStatusEnum.IN_PROGRESS: {
            PlanStatusEnum.COMPLETED,
            PlanStatusEnum.FAILED,
            PlanStatusEnum.CANCELLED
        },
        PlanStatusEnum.COMPLETED: set(),  # Терминальный
        PlanStatusEnum.FAILED: set(),  # Терминальный
        PlanStatusEnum.CANCELLED: set(),  # Терминальный
    }
    
    def __init__(self, value: PlanStatusEnum):
        """
        Создать статус плана.
        
        Args:
            value: Значение статуса
            
        Raises:
            ValueError: Если статус невалиден
        """
        if not isinstance(value, PlanStatusEnum):
            raise ValueError(
                f"Status must be PlanStatusEnum, got {type(value).__name__}"
            )
        
        self._value = value
    
    @property
    def value(self) -> PlanStatusEnum:
        """Получить значение статуса."""
        return self._value
    
    @classmethod
    def draft(cls) -> "PlanStatus":
        """Создать статус DRAFT."""
        return cls(PlanStatusEnum.DRAFT)
    
    @classmethod
    def approved(cls) -> "PlanStatus":
        """Создать статус APPROVED."""
        return cls(PlanStatusEnum.APPROVED)
    
    @classmethod
    def in_progress(cls) -> "PlanStatus":
        """Создать статус IN_PROGRESS."""
        return cls(PlanStatusEnum.IN_PROGRESS)
    
    @classmethod
    def completed(cls) -> "PlanStatus":
        """Создать статус COMPLETED."""
        return cls(PlanStatusEnum.COMPLETED)
    
    @classmethod
    def failed(cls) -> "PlanStatus":
        """Создать статус FAILED."""
        return cls(PlanStatusEnum.FAILED)
    
    @classmethod
    def cancelled(cls) -> "PlanStatus":
        """Создать статус CANCELLED."""
        return cls(PlanStatusEnum.CANCELLED)
    
    @classmethod
    def from_string(cls, value: str) -> "PlanStatus":
        """
        Создать статус из строки.
        
        Args:
            value: Строковое значение статуса
            
        Returns:
            Объект PlanStatus
            
        Raises:
            ValueError: Если статус невалиден
        """
        try:
            enum_value = PlanStatusEnum(value)
            return cls(enum_value)
        except ValueError:
            valid_values = [s.value for s in PlanStatusEnum]
            raise ValueError(
                f"Invalid plan status: '{value}'. "
                f"Valid values: {', '.join(valid_values)}"
            )
    
    def can_transition_to(self, target: "PlanStatus") -> bool:
        """
        Проверить, возможен ли переход в целевой статус.
        
        Args:
            target: Целевой статус
            
        Returns:
            True если переход допустим
        
        Example:
            >>> draft = PlanStatus.draft()
            >>> approved = PlanStatus.approved()
            >>> draft.can_transition_to(approved)
            True
        """
        valid_targets = self._VALID_TRANSITIONS.get(self._value, set())
        return target._value in valid_targets
    
    def is_terminal(self) -> bool:
        """
        Проверить, является ли статус терминальным.
        
        Returns:
            True если статус терминальный (COMPLETED, FAILED, CANCELLED)
        
        Example:
            >>> completed = PlanStatus.completed()
            >>> completed.is_terminal()
            True
        """
        return self._value in {
            PlanStatusEnum.COMPLETED,
            PlanStatusEnum.FAILED,
            PlanStatusEnum.CANCELLED
        }
    
    def is_draft(self) -> bool:
        """Проверить, является ли статус DRAFT."""
        return self._value == PlanStatusEnum.DRAFT
    
    def is_approved(self) -> bool:
        """Проверить, является ли статус APPROVED."""
        return self._value == PlanStatusEnum.APPROVED
    
    def is_in_progress(self) -> bool:
        """Проверить, является ли статус IN_PROGRESS."""
        return self._value == PlanStatusEnum.IN_PROGRESS
    
    def is_completed(self) -> bool:
        """Проверить, является ли статус COMPLETED."""
        return self._value == PlanStatusEnum.COMPLETED
    
    def is_failed(self) -> bool:
        """Проверить, является ли статус FAILED."""
        return self._value == PlanStatusEnum.FAILED
    
    def is_cancelled(self) -> bool:
        """Проверить, является ли статус CANCELLED."""
        return self._value == PlanStatusEnum.CANCELLED
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self._value.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"PlanStatus({self._value.value})"
    
    def __eq__(self, other: object) -> bool:
        """Сравнение на равенство."""
        if not isinstance(other, PlanStatus):
            return False
        return self._value == other._value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self._value)

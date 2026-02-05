"""
Value Object для статуса подзадачи.

Инкапсулирует валидацию и бизнес-правила для статусов подзадач.
"""

from enum import Enum
from typing import Set

from app.domain.shared.value_object import ValueObject


class SubtaskStatusEnum(str, Enum):
    """
    Возможные статусы подзадачи.
    """
    PENDING = "pending"      # Ожидает выполнения
    RUNNING = "running"      # В процессе выполнения
    DONE = "done"           # Успешно завершена
    FAILED = "failed"       # Завершена с ошибкой
    BLOCKED = "blocked"     # Заблокирована зависимостями


class SubtaskStatus(ValueObject):
    """
    Статус подзадачи с валидацией переходов.
    
    Бизнес-правила переходов:
    - PENDING → RUNNING, BLOCKED
    - RUNNING → DONE, FAILED
    - BLOCKED → PENDING
    - DONE → (терминальный статус)
    - FAILED → (терминальный статус)
    
    Attributes:
        value: Значение статуса
    
    Example:
        >>> status = SubtaskStatus.pending()
        >>> status.can_transition_to(SubtaskStatus.running())
        True
        
        >>> done_status = SubtaskStatus.done()
        >>> done_status.is_terminal()
        True
    """
    
    # Допустимые переходы между статусами
    _VALID_TRANSITIONS: dict[SubtaskStatusEnum, Set[SubtaskStatusEnum]] = {
        SubtaskStatusEnum.PENDING: {SubtaskStatusEnum.RUNNING, SubtaskStatusEnum.BLOCKED},
        SubtaskStatusEnum.RUNNING: {SubtaskStatusEnum.DONE, SubtaskStatusEnum.FAILED},
        SubtaskStatusEnum.BLOCKED: {SubtaskStatusEnum.PENDING},
        SubtaskStatusEnum.DONE: set(),  # Терминальный
        SubtaskStatusEnum.FAILED: set(),  # Терминальный
    }
    
    def __init__(self, value: SubtaskStatusEnum):
        """
        Создать статус подзадачи.
        
        Args:
            value: Значение статуса
            
        Raises:
            ValueError: Если статус невалиден
        """
        if not isinstance(value, SubtaskStatusEnum):
            raise ValueError(
                f"Status must be SubtaskStatusEnum, got {type(value).__name__}"
            )
        
        self._value = value
    
    @property
    def value(self) -> SubtaskStatusEnum:
        """Получить значение статуса."""
        return self._value
    
    @classmethod
    def pending(cls) -> "SubtaskStatus":
        """Создать статус PENDING."""
        return cls(SubtaskStatusEnum.PENDING)
    
    @classmethod
    def running(cls) -> "SubtaskStatus":
        """Создать статус RUNNING."""
        return cls(SubtaskStatusEnum.RUNNING)
    
    @classmethod
    def done(cls) -> "SubtaskStatus":
        """Создать статус DONE."""
        return cls(SubtaskStatusEnum.DONE)
    
    @classmethod
    def failed(cls) -> "SubtaskStatus":
        """Создать статус FAILED."""
        return cls(SubtaskStatusEnum.FAILED)
    
    @classmethod
    def blocked(cls) -> "SubtaskStatus":
        """Создать статус BLOCKED."""
        return cls(SubtaskStatusEnum.BLOCKED)
    
    @classmethod
    def from_string(cls, value: str) -> "SubtaskStatus":
        """
        Создать статус из строки.
        
        Args:
            value: Строковое значение статуса
            
        Returns:
            Объект SubtaskStatus
            
        Raises:
            ValueError: Если статус невалиден
        """
        try:
            enum_value = SubtaskStatusEnum(value)
            return cls(enum_value)
        except ValueError:
            valid_values = [s.value for s in SubtaskStatusEnum]
            raise ValueError(
                f"Invalid subtask status: '{value}'. "
                f"Valid values: {', '.join(valid_values)}"
            )
    
    def can_transition_to(self, target: "SubtaskStatus") -> bool:
        """
        Проверить, возможен ли переход в целевой статус.
        
        Args:
            target: Целевой статус
            
        Returns:
            True если переход допустим
        
        Example:
            >>> pending = SubtaskStatus.pending()
            >>> running = SubtaskStatus.running()
            >>> pending.can_transition_to(running)
            True
        """
        valid_targets = self._VALID_TRANSITIONS.get(self._value, set())
        return target._value in valid_targets
    
    def is_terminal(self) -> bool:
        """
        Проверить, является ли статус терминальным.
        
        Returns:
            True если статус терминальный (DONE или FAILED)
        
        Example:
            >>> done = SubtaskStatus.done()
            >>> done.is_terminal()
            True
        """
        return self._value in {SubtaskStatusEnum.DONE, SubtaskStatusEnum.FAILED}
    
    def is_pending(self) -> bool:
        """Проверить, является ли статус PENDING."""
        return self._value == SubtaskStatusEnum.PENDING
    
    def is_running(self) -> bool:
        """Проверить, является ли статус RUNNING."""
        return self._value == SubtaskStatusEnum.RUNNING
    
    def is_done(self) -> bool:
        """Проверить, является ли статус DONE."""
        return self._value == SubtaskStatusEnum.DONE
    
    def is_failed(self) -> bool:
        """Проверить, является ли статус FAILED."""
        return self._value == SubtaskStatusEnum.FAILED
    
    def is_blocked(self) -> bool:
        """Проверить, является ли статус BLOCKED."""
        return self._value == SubtaskStatusEnum.BLOCKED
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self._value.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"SubtaskStatus({self._value.value})"
    
    def __eq__(self, other: object) -> bool:
        """Сравнение на равенство."""
        if not isinstance(other, SubtaskStatus):
            return False
        return self._value == other._value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self._value)

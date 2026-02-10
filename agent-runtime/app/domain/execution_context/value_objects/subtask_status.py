"""
Value Object для статуса подзадачи.

Инкапсулирует валидацию и бизнес-правила для статусов подзадач.
"""

from enum import Enum
from typing import Set, ClassVar, Dict

from app.domain.shared.value_object import ValueObject


class SubtaskStatusEnum(str, Enum):
    """
    Возможные статусы подзадачи.
    """
    PENDING: ClassVar = "pending"          # Ожидает выполнения
    IN_PROGRESS: ClassVar = "in_progress"  # В процессе выполнения
    RUNNING: ClassVar = "running"          # В процессе выполнения (alias)
    DONE: ClassVar = "done"               # Успешно завершена
    FAILED: ClassVar = "failed"           # Завершена с ошибкой
    BLOCKED: ClassVar = "blocked"         # Заблокирована зависимостями


class SubtaskStatus(ValueObject):
    """
    
    value: SubtaskStatusEnum
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
    _VALID_TRANSITIONS: ClassVar[Dict[SubtaskStatusEnum, Set[SubtaskStatusEnum]]] = {
        SubtaskStatusEnum.PENDING: {
            SubtaskStatusEnum.IN_PROGRESS,
            SubtaskStatusEnum.RUNNING,
            SubtaskStatusEnum.BLOCKED
        },
        SubtaskStatusEnum.IN_PROGRESS: {SubtaskStatusEnum.DONE, SubtaskStatusEnum.FAILED},
        SubtaskStatusEnum.RUNNING: {SubtaskStatusEnum.DONE, SubtaskStatusEnum.FAILED},
        SubtaskStatusEnum.BLOCKED: {SubtaskStatusEnum.PENDING},
        SubtaskStatusEnum.DONE: set(),  # Терминальный
        SubtaskStatusEnum.FAILED: {SubtaskStatusEnum.PENDING},  # Можно retry
    }
    
    value: SubtaskStatusEnum
    
    # Константы для удобного использования
    PENDING: 'SubtaskStatus | None' = None  # Будет инициализировано после определения класса
    IN_PROGRESS: 'SubtaskStatus | None' = None
    RUNNING: 'SubtaskStatus | None' = None  # Alias для IN_PROGRESS
    DONE: 'SubtaskStatus | None' = None
    FAILED: 'SubtaskStatus | None' = None
    
    @classmethod
    def pending(cls) -> "SubtaskStatus":
        """Создать статус PENDING."""
        return cls(value=SubtaskStatusEnum.PENDING)
    
    @classmethod
    def in_progress(cls) -> "SubtaskStatus":
        """Создать статус IN_PROGRESS."""
        return cls(value=SubtaskStatusEnum.IN_PROGRESS)
    
    @classmethod
    def running(cls) -> "SubtaskStatus":
        """Создать статус RUNNING."""
        return cls(value=SubtaskStatusEnum.RUNNING)
    
    @classmethod
    def done(cls) -> "SubtaskStatus":
        """Создать статус DONE."""
        return cls(value=SubtaskStatusEnum.DONE)
    
    @classmethod
    def failed(cls) -> "SubtaskStatus":
        """Создать статус FAILED."""
        return cls(value=SubtaskStatusEnum.FAILED)
    
    @classmethod
    def blocked(cls) -> "SubtaskStatus":
        """Создать статус BLOCKED."""
        return cls(value=SubtaskStatusEnum.BLOCKED)
    
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
            return cls(value=enum_value)
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
        valid_targets = self._VALID_TRANSITIONS.get(self.value, set())
        return target.value in valid_targets
    
    def is_terminal(self) -> bool:
        """
        Проверить, является ли статус терминальным.
        
        Returns:
            True если статус терминальный (только DONE, FAILED можно retry)
        
        Example:
            >>> done = SubtaskStatus.done()
            >>> done.is_terminal()
            True
            
            >>> failed = SubtaskStatus.failed()
            >>> failed.is_terminal()
            False  # FAILED можно retry
        """
        return self.value == SubtaskStatusEnum.DONE
    
    def is_pending(self) -> bool:
        """Проверить, является ли статус PENDING."""
        return self.value == SubtaskStatusEnum.PENDING
    
    def is_running(self) -> bool:
        """Проверить, является ли статус RUNNING."""
        return self.value == SubtaskStatusEnum.RUNNING
    
    def is_done(self) -> bool:
        """Проверить, является ли статус DONE."""
        return self.value == SubtaskStatusEnum.DONE
    
    def is_failed(self) -> bool:
        """Проверить, является ли статус FAILED."""
        return self.value == SubtaskStatusEnum.FAILED
    
    def is_blocked(self) -> bool:
        """Проверить, является ли статус BLOCKED."""
        return self.value == SubtaskStatusEnum.BLOCKED
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"SubtaskStatus({self.value.value})"
    
    def __eq__(self, other: object) -> bool:
        """Сравнение на равенство."""
        if not isinstance(other, SubtaskStatus):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)


# Инициализация констант
SubtaskStatus.PENDING = SubtaskStatus.pending()
SubtaskStatus.IN_PROGRESS = SubtaskStatus.in_progress()
SubtaskStatus.RUNNING = SubtaskStatus.running()  # Alias для IN_PROGRESS
SubtaskStatus.DONE = SubtaskStatus.done()
SubtaskStatus.FAILED = SubtaskStatus.failed()

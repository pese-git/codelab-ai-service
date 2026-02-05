"""
Value Object для режима выполнения инструмента.

Инкапсулирует место выполнения инструмента.
"""

from typing import ClassVar, Optional

from ...shared.value_object import ValueObject


class ToolExecutionMode(ValueObject):
    """
    Value Object для режима выполнения инструмента.
    
    Режимы:
    - LOCAL: Выполняется в agent-runtime (echo, calculator, switch_mode)
    - IDE: Выполняется на стороне IDE через WebSocket (read_file, write_file, etc.)
    - REMOTE: Выполняется на удаленном сервере (зарезервировано)
    
    Примеры:
        >>> mode = ToolExecutionMode.local()
        >>> mode.is_local()
        True
        >>> mode.is_ide()
        False
    """
    
    value: str
    
    # Допустимые режимы
    LOCAL: ClassVar[str] = "LOCAL"
    IDE: ClassVar[str] = "IDE"
    REMOTE: ClassVar[str] = "REMOTE"
    
    VALID_MODES: ClassVar[frozenset] = frozenset(["LOCAL", "IDE", "REMOTE"])
    
    def model_post_init(self, __context) -> None:
        """Валидация после инициализации."""
        super().model_post_init(__context)
        self._validate()
    
    def _validate(self) -> None:
        """
        Валидировать режим выполнения.
        
        Raises:
            ValueError: Если режим невалиден
        """
        if self.value not in self.VALID_MODES:
            raise ValueError(
                f"Invalid execution mode: '{self.value}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_MODES))}"
            )
    
    @staticmethod
    def local() -> "ToolExecutionMode":
        """
        Создать режим LOCAL.
        
        Локальные инструменты выполняются в agent-runtime:
        - echo
        - calculator
        - switch_mode
        
        Returns:
            ToolExecutionMode для локального выполнения
            
        Example:
            >>> mode = ToolExecutionMode.local()
            >>> mode.is_local()
            True
        """
        return ToolExecutionMode(value=ToolExecutionMode.LOCAL)
    
    @staticmethod
    def ide() -> "ToolExecutionMode":
        """
        Создать режим IDE.
        
        IDE инструменты выполняются на стороне IDE через WebSocket:
        - read_file
        - write_file
        - execute_command
        - search_in_code
        - list_files
        - create_directory
        
        Returns:
            ToolExecutionMode для выполнения в IDE
            
        Example:
            >>> mode = ToolExecutionMode.ide()
            >>> mode.is_ide()
            True
        """
        return ToolExecutionMode(value=ToolExecutionMode.IDE)
    
    @staticmethod
    def remote() -> "ToolExecutionMode":
        """
        Создать режим REMOTE.
        
        Удаленные инструменты выполняются на удаленном сервере.
        (Зарезервировано для будущего использования)
        
        Returns:
            ToolExecutionMode для удаленного выполнения
            
        Example:
            >>> mode = ToolExecutionMode.remote()
            >>> mode.is_local()
            False
        """
        return ToolExecutionMode(value=ToolExecutionMode.REMOTE)
    
    @staticmethod
    def from_string(value: str) -> "ToolExecutionMode":
        """
        Создать ToolExecutionMode из строки.
        
        Args:
            value: Название режима
            
        Returns:
            ToolExecutionMode instance
            
        Example:
            >>> mode = ToolExecutionMode.from_string("LOCAL")
            >>> mode.is_local()
            True
        """
        return ToolExecutionMode(value=value.upper())
    
    def is_local(self) -> bool:
        """
        Проверить, является ли режим локальным.
        
        Returns:
            True если инструмент выполняется локально
            
        Example:
            >>> ToolExecutionMode.local().is_local()
            True
            >>> ToolExecutionMode.ide().is_local()
            False
        """
        return self.value == self.LOCAL
    
    def is_ide(self) -> bool:
        """
        Проверить, является ли режим IDE.
        
        Returns:
            True если инструмент выполняется в IDE
            
        Example:
            >>> ToolExecutionMode.ide().is_ide()
            True
            >>> ToolExecutionMode.local().is_ide()
            False
        """
        return self.value == self.IDE
    
    def is_remote(self) -> bool:
        """
        Проверить, является ли режим удаленным.
        
        Returns:
            True если инструмент выполняется удаленно
            
        Example:
            >>> ToolExecutionMode.remote().is_remote()
            True
            >>> ToolExecutionMode.local().is_remote()
            False
        """
        return self.value == self.REMOTE
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolExecutionMode.{self.value}"

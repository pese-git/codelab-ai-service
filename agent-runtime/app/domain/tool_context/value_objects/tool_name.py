"""
Value Object для имени инструмента.

Инкапсулирует валидацию и бизнес-правила для имен инструментов.
"""

import re
from typing import ClassVar, Optional

from ...shared.value_object import ValueObject


class ToolName(ValueObject):
    """
    Value Object для имени инструмента.
    
    Валидация:
    - Не пустое
    - Формат: snake_case
    - Длина: 1-100 символов
    - Только буквы, цифры, подчеркивания
    
    Примеры:
        >>> tool_name = ToolName(value="read_file")
        >>> tool_name.is_local_tool()
        False
        >>> tool_name.is_ide_tool()
        True
    """
    
    value: str
    
    # Локальные инструменты (выполняются в agent-runtime)
    LOCAL_TOOLS: ClassVar[frozenset] = frozenset(["echo", "calculator", "switch_mode"])
    
    # Паттерн валидации: snake_case
    PATTERN: ClassVar[re.Pattern] = re.compile(r'^[a-z][a-z0-9_]*$')
    
    def model_post_init(self, __context) -> None:
        """Валидация после инициализации."""
        super().model_post_init(__context)
        self._validate()
    
    def _validate(self) -> None:
        """
        Валидировать имя инструмента.
        
        Raises:
            ValueError: Если имя невалидно
        """
        if not self.value:
            raise ValueError("Tool name cannot be empty")
        
        if len(self.value) > 100:
            raise ValueError(
                f"Tool name too long: {len(self.value)} characters (max 100)"
            )
        
        if not self.PATTERN.match(self.value):
            raise ValueError(
                f"Invalid tool name format: '{self.value}'. "
                "Must be snake_case (lowercase letters, numbers, underscores)"
            )
    
    @staticmethod
    def from_string(value: str) -> "ToolName":
        """
        Создать ToolName из строки.
        
        Args:
            value: Имя инструмента
            
        Returns:
            ToolName instance
            
        Example:
            >>> tool_name = ToolName.from_string("read_file")
            >>> str(tool_name)
            'read_file'
        """
        return ToolName(value=value)
    
    def is_local_tool(self) -> bool:
        """
        Проверить, является ли инструмент локальным.
        
        Локальные инструменты выполняются в agent-runtime:
        - echo
        - calculator
        - switch_mode
        
        Returns:
            True если инструмент локальный
            
        Example:
            >>> ToolName.from_string("echo").is_local_tool()
            True
            >>> ToolName.from_string("read_file").is_local_tool()
            False
        """
        return self.value in self.LOCAL_TOOLS
    
    def is_ide_tool(self) -> bool:
        """
        Проверить, является ли инструмент IDE-инструментом.
        
        IDE инструменты выполняются на стороне IDE через WebSocket:
        - read_file
        - write_file
        - execute_command
        - search_in_code
        - list_files
        - create_directory
        
        Returns:
            True если инструмент IDE-инструмент
            
        Example:
            >>> ToolName.from_string("read_file").is_ide_tool()
            True
            >>> ToolName.from_string("echo").is_ide_tool()
            False
        """
        return not self.is_local_tool()
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolName('{self.value}')"

"""
Value Object для категории инструмента.

Инкапсулирует классификацию инструментов по функциональности.
"""

from typing import ClassVar, Optional

from ...shared.value_object import ValueObject


class ToolCategory(ValueObject):
    """
    Value Object для категории инструмента.
    
    Категории:
    - FILE_SYSTEM: read_file, write_file, list_files, create_directory
    - COMMAND: execute_command
    - SEARCH: search_in_code
    - AGENT: switch_mode
    - UTILITY: echo, calculator
    
    Примеры:
        >>> category = ToolCategory.file_system()
        >>> category.is_dangerous()
        True
        >>> category.requires_approval()
        True
    """
    
    value: str
    
    # Допустимые категории
    FILE_SYSTEM: ClassVar[str] = "FILE_SYSTEM"
    COMMAND: ClassVar[str] = "COMMAND"
    SEARCH: ClassVar[str] = "SEARCH"
    AGENT: ClassVar[str] = "AGENT"
    UTILITY: ClassVar[str] = "UTILITY"
    
    VALID_CATEGORIES: ClassVar[frozenset] = frozenset([
        "FILE_SYSTEM",
        "COMMAND",
        "SEARCH",
        "AGENT",
        "UTILITY"
    ])
    
    # Опасные категории (требуют особого внимания)
    DANGEROUS_CATEGORIES: ClassVar[frozenset] = frozenset([
        "FILE_SYSTEM",
        "COMMAND"
    ])
    
    # Категории, требующие одобрения
    APPROVAL_REQUIRED_CATEGORIES: ClassVar[frozenset] = frozenset([
        "FILE_SYSTEM",
        "COMMAND"
    ])
    
    def model_post_init(self, __context) -> None:
        """Валидация после инициализации."""
        super().model_post_init(__context)
        self._validate()
    
    def _validate(self) -> None:
        """
        Валидировать категорию.
        
        Raises:
            ValueError: Если категория невалидна
        """
        if self.value not in self.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid tool category: '{self.value}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_CATEGORIES))}"
            )
    
    @staticmethod
    def file_system() -> "ToolCategory":
        """
        Создать категорию FILE_SYSTEM.
        
        Returns:
            ToolCategory для файловых операций
            
        Example:
            >>> category = ToolCategory.file_system()
            >>> category.is_dangerous()
            True
        """
        return ToolCategory(value=ToolCategory.FILE_SYSTEM)
    
    @staticmethod
    def command() -> "ToolCategory":
        """
        Создать категорию COMMAND.
        
        Returns:
            ToolCategory для выполнения команд
            
        Example:
            >>> category = ToolCategory.command()
            >>> category.requires_approval()
            True
        """
        return ToolCategory(value=ToolCategory.COMMAND)
    
    @staticmethod
    def search() -> "ToolCategory":
        """
        Создать категорию SEARCH.
        
        Returns:
            ToolCategory для поиска
            
        Example:
            >>> category = ToolCategory.search()
            >>> category.is_dangerous()
            False
        """
        return ToolCategory(value=ToolCategory.SEARCH)
    
    @staticmethod
    def agent() -> "ToolCategory":
        """
        Создать категорию AGENT.
        
        Returns:
            ToolCategory для агентских операций
            
        Example:
            >>> category = ToolCategory.agent()
            >>> category.is_dangerous()
            False
        """
        return ToolCategory(value=ToolCategory.AGENT)
    
    @staticmethod
    def utility() -> "ToolCategory":
        """
        Создать категорию UTILITY.
        
        Returns:
            ToolCategory для утилит
            
        Example:
            >>> category = ToolCategory.utility()
            >>> category.requires_approval()
            False
        """
        return ToolCategory(value=ToolCategory.UTILITY)
    
    @staticmethod
    def from_string(value: str) -> "ToolCategory":
        """
        Создать ToolCategory из строки.
        
        Args:
            value: Название категории
            
        Returns:
            ToolCategory instance
            
        Example:
            >>> category = ToolCategory.from_string("FILE_SYSTEM")
            >>> category.is_dangerous()
            True
        """
        return ToolCategory(value=value.upper())
    
    def is_dangerous(self) -> bool:
        """
        Проверить, является ли категория опасной.
        
        Опасные категории:
        - FILE_SYSTEM: Может изменять файлы
        - COMMAND: Может выполнять произвольные команды
        
        Returns:
            True если категория опасная
            
        Example:
            >>> ToolCategory.file_system().is_dangerous()
            True
            >>> ToolCategory.utility().is_dangerous()
            False
        """
        return self.value in self.DANGEROUS_CATEGORIES
    
    def requires_approval(self) -> bool:
        """
        Проверить, требует ли категория одобрения.
        
        Returns:
            True если требуется одобрение пользователя
            
        Example:
            >>> ToolCategory.command().requires_approval()
            True
            >>> ToolCategory.search().requires_approval()
            False
        """
        return self.value in self.APPROVAL_REQUIRED_CATEGORIES
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolCategory.{self.value}"

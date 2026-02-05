"""
Value Object для прав доступа к инструменту.

Инкапсулирует уровни доступа и проверку разрешений.
"""

from typing import ClassVar, Optional

from ...shared.value_object import ValueObject


class ToolPermission(ValueObject):
    """
    Value Object для прав доступа к инструменту.
    
    Уровни (от меньшего к большему):
    - READ_ONLY: Только чтение (read_file, list_files, search_in_code)
    - READ_WRITE: Чтение и запись (write_file, create_directory)
    - EXECUTE: Выполнение команд (execute_command)
    - ADMIN: Административные операции (зарезервировано)
    
    Примеры:
        >>> perm = ToolPermission.read_write()
        >>> perm.allows(ToolPermission.read_only())
        True
        >>> perm.allows(ToolPermission.execute())
        False
    """
    
    level: str
    
    # Уровни доступа (в порядке возрастания)
    READ_ONLY: ClassVar[str] = "READ_ONLY"
    READ_WRITE: ClassVar[str] = "READ_WRITE"
    EXECUTE: ClassVar[str] = "EXECUTE"
    ADMIN: ClassVar[str] = "ADMIN"
    
    VALID_LEVELS: ClassVar[frozenset] = frozenset(["READ_ONLY", "READ_WRITE", "EXECUTE", "ADMIN"])
    
    # Иерархия уровней (больший уровень включает меньшие)
    LEVEL_HIERARCHY: ClassVar[dict] = {
        "READ_ONLY": 1,
        "READ_WRITE": 2,
        "EXECUTE": 3,
        "ADMIN": 4
    }
    
    def model_post_init(self, __context) -> None:
        """Валидация после инициализации."""
        super().model_post_init(__context)
        self._validate()
    
    def _validate(self) -> None:
        """
        Валидировать уровень доступа.
        
        Raises:
            ValueError: Если уровень невалиден
        """
        if self.level not in self.VALID_LEVELS:
            raise ValueError(
                f"Invalid permission level: '{self.level}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_LEVELS))}"
            )
    
    @staticmethod
    def read_only() -> "ToolPermission":
        """
        Создать уровень READ_ONLY.
        
        Разрешает только операции чтения:
        - read_file
        - list_files
        - search_in_code
        
        Returns:
            ToolPermission для чтения
            
        Example:
            >>> perm = ToolPermission.read_only()
            >>> perm.allows(ToolPermission.read_only())
            True
        """
        return ToolPermission(level=ToolPermission.READ_ONLY)
    
    @staticmethod
    def read_write() -> "ToolPermission":
        """
        Создать уровень READ_WRITE.
        
        Разрешает чтение и запись:
        - read_file, list_files, search_in_code (READ_ONLY)
        - write_file
        - create_directory
        
        Returns:
            ToolPermission для чтения и записи
            
        Example:
            >>> perm = ToolPermission.read_write()
            >>> perm.allows(ToolPermission.read_only())
            True
        """
        return ToolPermission(level=ToolPermission.READ_WRITE)
    
    @staticmethod
    def execute() -> "ToolPermission":
        """
        Создать уровень EXECUTE.
        
        Разрешает выполнение команд:
        - Все из READ_WRITE
        - execute_command
        
        Returns:
            ToolPermission для выполнения команд
            
        Example:
            >>> perm = ToolPermission.execute()
            >>> perm.allows(ToolPermission.read_write())
            True
        """
        return ToolPermission(level=ToolPermission.EXECUTE)
    
    @staticmethod
    def admin() -> "ToolPermission":
        """
        Создать уровень ADMIN.
        
        Разрешает все операции (зарезервировано).
        
        Returns:
            ToolPermission для административных операций
            
        Example:
            >>> perm = ToolPermission.admin()
            >>> perm.allows(ToolPermission.execute())
            True
        """
        return ToolPermission(level=ToolPermission.ADMIN)
    
    @staticmethod
    def from_string(value: str) -> "ToolPermission":
        """
        Создать ToolPermission из строки.
        
        Args:
            value: Название уровня
            
        Returns:
            ToolPermission instance
            
        Example:
            >>> perm = ToolPermission.from_string("READ_WRITE")
            >>> perm.allows(ToolPermission.read_only())
            True
        """
        return ToolPermission(level=value.upper())
    
    def allows(self, required: "ToolPermission") -> bool:
        """
        Проверить, разрешает ли текущий уровень требуемый.
        
        Иерархия: READ_ONLY < READ_WRITE < EXECUTE < ADMIN
        Больший уровень включает все меньшие.
        
        Args:
            required: Требуемый уровень доступа
            
        Returns:
            True если текущий уровень >= требуемого
            
        Example:
            >>> read_write = ToolPermission.read_write()
            >>> read_write.allows(ToolPermission.read_only())
            True
            >>> read_write.allows(ToolPermission.execute())
            False
        """
        current_level = self.LEVEL_HIERARCHY[self.level]
        required_level = self.LEVEL_HIERARCHY[required.level]
        return current_level >= required_level
    
    def get_level_number(self) -> int:
        """
        Получить числовой уровень доступа.
        
        Returns:
            Числовой уровень (1-4)
            
        Example:
            >>> ToolPermission.read_only().get_level_number()
            1
            >>> ToolPermission.execute().get_level_number()
            3
        """
        return self.LEVEL_HIERARCHY[self.level]
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.level
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolPermission.{self.level}"
    
    def __lt__(self, other: "ToolPermission") -> bool:
        """Сравнение меньше."""
        return self.get_level_number() < other.get_level_number()
    
    def __le__(self, other: "ToolPermission") -> bool:
        """Сравнение меньше или равно."""
        return self.get_level_number() <= other.get_level_number()
    
    def __gt__(self, other: "ToolPermission") -> bool:
        """Сравнение больше."""
        return self.get_level_number() > other.get_level_number()
    
    def __ge__(self, other: "ToolPermission") -> bool:
        """Сравнение больше или равно."""
        return self.get_level_number() >= other.get_level_number()

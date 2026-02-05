"""
Value Object для результата выполнения инструмента.

Инкапсулирует результат выполнения с метаданными.
"""

from typing import Any, ClassVar, Dict, Optional

from ...shared.value_object import ValueObject


class ToolResult(ValueObject):
    """
    Value Object для результата выполнения инструмента.
    
    Атрибуты:
    - content: str — Результат выполнения
    - is_error: bool — Флаг ошибки
    - metadata: Dict — Дополнительные данные
    
    Примеры:
        >>> result = ToolResult.success("File read successfully")
        >>> result.is_success()
        True
        >>> error = ToolResult.error("File not found")
        >>> error.is_success()
        False
    """
    
    content: str
    is_error: bool = False
    metadata: Dict[str, Any] = {}
    
    # Максимальный размер контента (1MB)
    MAX_CONTENT_SIZE: ClassVar[int] = 1024 * 1024
    
    def model_post_init(self, __context) -> None:
        """Валидация после инициализации."""
        super().model_post_init(__context)
        self._validate()
    
    def _validate(self) -> None:
        """
        Валидировать результат.
        
        Raises:
            ValueError: Если результат невалиден
        """
        if len(self.content) > self.MAX_CONTENT_SIZE:
            raise ValueError(
                f"Result content too large: {len(self.content)} bytes "
                f"(max {self.MAX_CONTENT_SIZE} bytes)"
            )
    
    @staticmethod
    def success(
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "ToolResult":
        """
        Создать успешный результат.
        
        Args:
            content: Содержимое результата
            metadata: Дополнительные метаданные
            
        Returns:
            ToolResult с is_error=False
            
        Example:
            >>> result = ToolResult.success("Operation completed")
            >>> result.is_success()
            True
            >>> result.get_content()
            'Operation completed'
        """
        return ToolResult(
            content=content,
            is_error=False,
            metadata=metadata or {}
        )
    
    @staticmethod
    def error(
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "ToolResult":
        """
        Создать результат с ошибкой.
        
        Args:
            message: Сообщение об ошибке
            metadata: Дополнительные метаданные
            
        Returns:
            ToolResult с is_error=True
            
        Example:
            >>> error = ToolResult.error("File not found")
            >>> error.is_success()
            False
            >>> error.get_content()
            'File not found'
        """
        return ToolResult(
            content=message,
            is_error=True,
            metadata=metadata or {}
        )
    
    def is_success(self) -> bool:
        """
        Проверить, успешен ли результат.
        
        Returns:
            True если результат успешен (не ошибка)
            
        Example:
            >>> ToolResult.success("OK").is_success()
            True
            >>> ToolResult.error("Failed").is_success()
            False
        """
        return not self.is_error
    
    def get_content(self) -> str:
        """
        Получить содержимое результата.
        
        Returns:
            Содержимое результата
            
        Example:
            >>> result = ToolResult.success("Hello, world!")
            >>> result.get_content()
            'Hello, world!'
        """
        return self.content
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Получить значение из метаданных.
        
        Args:
            key: Ключ метаданных
            default: Значение по умолчанию
            
        Returns:
            Значение из метаданных или default
            
        Example:
            >>> result = ToolResult.success("OK", metadata={"duration_ms": 150})
            >>> result.get_metadata("duration_ms")
            150
            >>> result.get_metadata("missing", "default")
            'default'
        """
        return self.metadata.get(key, default)
    
    def has_metadata(self, key: str) -> bool:
        """
        Проверить наличие метаданных.
        
        Args:
            key: Ключ метаданных
            
        Returns:
            True если метаданные присутствуют
            
        Example:
            >>> result = ToolResult.success("OK", metadata={"duration_ms": 150})
            >>> result.has_metadata("duration_ms")
            True
            >>> result.has_metadata("missing")
            False
        """
        return key in self.metadata
    
    def truncate(self, max_length: int = 1000) -> str:
        """
        Получить усеченное содержимое.
        
        Args:
            max_length: Максимальная длина
            
        Returns:
            Усеченное содержимое с "..." если необходимо
            
        Example:
            >>> result = ToolResult.success("A" * 2000)
            >>> len(result.truncate(100))
            103
        """
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        status = "success" if self.is_success() else "error"
        preview = self.truncate(50)
        return f"ToolResult({status}, '{preview}')"

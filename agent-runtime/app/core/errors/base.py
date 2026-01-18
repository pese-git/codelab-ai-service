"""
Базовые исключения для Agent Runtime.

Определяет иерархию исключений для различных слоев приложения.
"""

from typing import Optional, Dict, Any


class AgentRuntimeError(Exception):
    """
    Базовое исключение для всех ошибок Agent Runtime.
    
    Все кастомные исключения должны наследоваться от этого класса.
    Позволяет легко отлавливать все ошибки приложения.
    
    Атрибуты:
        message: Сообщение об ошибке
        details: Дополнительные детали ошибки
        error_code: Код ошибки для идентификации
    
    Пример:
        >>> try:
        ...     raise AgentRuntimeError("Something went wrong")
        ... except AgentRuntimeError as e:
        ...     print(f"Error: {e}")
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        """
        Инициализация исключения.
        
        Args:
            message: Сообщение об ошибке
            details: Дополнительные детали (опционально)
            error_code: Код ошибки (опционально)
        """
        self.message = message
        self.details = details or {}
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать исключение в словарь.
        
        Полезно для логирования и API ответов.
        
        Returns:
            Словарь с информацией об ошибке
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }
    
    def __str__(self) -> str:
        """Строковое представление ошибки"""
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class DomainError(AgentRuntimeError):
    """
    Базовое исключение для ошибок доменного слоя.
    
    Используется для ошибок бизнес-логики, нарушения
    бизнес-правил и инвариантов.
    
    Пример:
        >>> raise DomainError("Invalid business rule")
    """
    pass


class InfrastructureError(AgentRuntimeError):
    """
    Базовое исключение для ошибок инфраструктурного слоя.
    
    Используется для ошибок работы с внешними системами:
    база данных, файловая система, сеть и т.д.
    
    Пример:
        >>> raise InfrastructureError("Database connection failed")
    """
    pass


class ApplicationError(AgentRuntimeError):
    """
    Базовое исключение для ошибок прикладного слоя.
    
    Используется для ошибок в use cases, командах и запросах.
    
    Пример:
        >>> raise ApplicationError("Command validation failed")
    """
    pass

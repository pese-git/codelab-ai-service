"""
Инфраструктурные исключения.

Исключения для ошибок работы с внешними системами и инфраструктурой.
"""

from typing import Optional, Dict, Any
from .base import InfrastructureError


class RepositoryError(InfrastructureError):
    """
    Исключение: ошибка работы с репозиторием.
    
    Выбрасывается при ошибках доступа к данным через репозиторий.
    
    Пример:
        >>> raise RepositoryError(
        ...     operation="save",
        ...     entity_type="Session",
        ...     reason="Database connection failed"
        ... )
    """
    
    def __init__(
        self,
        operation: str,
        entity_type: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            operation: Операция (get, save, delete и т.д.)
            entity_type: Тип сущности
            reason: Причина ошибки
            details: Дополнительные детали
        """
        message = (
            f"Ошибка репозитория при операции '{operation}' "
            f"с {entity_type}: {reason}"
        )
        super().__init__(
            message=message,
            details={
                "operation": operation,
                "entity_type": entity_type,
                "reason": reason,
                **(details or {})
            },
            error_code="REPOSITORY_ERROR"
        )


class DatabaseError(InfrastructureError):
    """
    Исключение: ошибка работы с базой данных.
    
    Выбрасывается при ошибках подключения или выполнения
    запросов к базе данных.
    
    Пример:
        >>> raise DatabaseError(
        ...     operation="query",
        ...     reason="Connection timeout"
        ... )
    """
    
    def __init__(
        self,
        operation: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            operation: Операция БД
            reason: Причина ошибки
            details: Дополнительные детали
        """
        message = f"Ошибка базы данных при операции '{operation}': {reason}"
        super().__init__(
            message=message,
            details={
                "operation": operation,
                "reason": reason,
                **(details or {})
            },
            error_code="DATABASE_ERROR"
        )


class EventBusError(InfrastructureError):
    """
    Исключение: ошибка работы с шиной событий.
    
    Выбрасывается при ошибках публикации или обработки событий.
    
    Пример:
        >>> raise EventBusError(
        ...     event_type="SessionCreated",
        ...     reason="No subscribers found"
        ... )
    """
    
    def __init__(
        self,
        event_type: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            event_type: Тип события
            reason: Причина ошибки
            details: Дополнительные детали
        """
        message = f"Ошибка шины событий для '{event_type}': {reason}"
        super().__init__(
            message=message,
            details={
                "event_type": event_type,
                "reason": reason,
                **(details or {})
            },
            error_code="EVENT_BUS_ERROR"
        )


class LLMProxyError(InfrastructureError):
    """
    Исключение: ошибка работы с LLM Proxy.
    
    Выбрасывается при ошибках взаимодействия с LLM Proxy сервисом.
    
    Пример:
        >>> raise LLMProxyError(
        ...     operation="chat_completion",
        ...     reason="Service unavailable",
        ...     status_code=503
        ... )
    """
    
    def __init__(
        self,
        operation: str,
        reason: str,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            operation: Операция (chat_completion, stream и т.д.)
            reason: Причина ошибки
            status_code: HTTP статус код (если применимо)
            details: Дополнительные детали
        """
        message = f"Ошибка LLM Proxy при операции '{operation}': {reason}"
        if status_code:
            message += f" (HTTP {status_code})"
        
        super().__init__(
            message=message,
            details={
                "operation": operation,
                "reason": reason,
                "status_code": status_code,
                **(details or {})
            },
            error_code="LLM_PROXY_ERROR"
        )

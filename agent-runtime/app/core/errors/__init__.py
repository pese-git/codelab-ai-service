"""
Кастомные исключения для Agent Runtime.

Этот модуль содержит иерархию исключений для различных
ошибочных ситуаций в системе.
"""

from .base import (
    AgentRuntimeError,
    DomainError,
    InfrastructureError,
    ApplicationError
)

from .domain_errors import (
    SessionNotFoundError,
    SessionAlreadyExistsError,
    AgentSwitchError,
    MessageValidationError,
    ConcurrencyError
)

from .infrastructure_errors import (
    RepositoryError,
    DatabaseError,
    EventBusError,
    LLMProxyError
)

__all__ = [
    # Базовые исключения
    "AgentRuntimeError",
    "DomainError",
    "InfrastructureError",
    "ApplicationError",
    
    # Доменные исключения
    "SessionNotFoundError",
    "SessionAlreadyExistsError",
    "AgentSwitchError",
    "MessageValidationError",
    "ConcurrencyError",
    
    # Инфраструктурные исключения
    "RepositoryError",
    "DatabaseError",
    "EventBusError",
    "LLMProxyError",
]

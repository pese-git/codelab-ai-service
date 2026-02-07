"""
Dependency Injection модули для Agent Runtime.

Модульная организация DI согласно Clean Architecture:
- SessionModule - зависимости для Session Context
- AgentModule - зависимости для Agent Context
- ExecutionModule - зависимости для Execution Context
- InfrastructureModule - зависимости для Infrastructure Layer
- DIContainer - центральный контейнер

Пример использования:
    >>> from app.core.di import get_container
    >>> container = get_container()
    >>> use_case = container.get_process_message_use_case(db)
"""

from .container import DIContainer, get_container
from .session_module import SessionModule
from .agent_module import AgentModule
from .execution_module import ExecutionModule
from .infrastructure_module import InfrastructureModule

__all__ = [
    "DIContainer",
    "get_container",
    "SessionModule",
    "AgentModule",
    "ExecutionModule",
    "InfrastructureModule",
]

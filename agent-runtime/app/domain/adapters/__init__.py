"""
Адаптеры для обратной совместимости между старыми и новыми entities.

Эти адаптеры обеспечивают плавную миграцию от старой архитектуры к новой,
позволяя существующему коду продолжать работать без изменений.
"""

from .session_adapter import SessionAdapter
from .agent_context_adapter import AgentContextAdapter
from .execution_engine_adapter import (
    ExecutionEngineAdapter,
    ExecutionEngineError,
    ExecutionResult
)

__all__ = [
    "SessionAdapter",
    "AgentContextAdapter",
    "ExecutionEngineAdapter",
    "ExecutionEngineError",
    "ExecutionResult",
]

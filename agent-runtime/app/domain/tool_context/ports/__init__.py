"""
Ports для Tool Context.

Интерфейсы для абстракции инфраструктуры.
"""

from .local_tool_executor import ILocalToolExecutor
from .ide_tool_executor import IIDEToolExecutor

__all__ = [
    "ILocalToolExecutor",
    "IIDEToolExecutor",
]

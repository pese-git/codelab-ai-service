"""
Entities для Execution Context.

Представляют основные доменные объекты для управления выполнением планов.
"""

from .subtask import Subtask
from .execution_plan import ExecutionPlan

__all__ = [
    "Subtask",
    "ExecutionPlan",
]

"""
Repositories для Execution Context.

Определяют интерфейсы для работы с хранилищем планов выполнения.
"""

from .execution_plan_repository import ExecutionPlanRepository

__all__ = [
    "ExecutionPlanRepository",
]

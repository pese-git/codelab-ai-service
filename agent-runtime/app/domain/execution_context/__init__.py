"""
Execution Context - Bounded Context для управления выполнением планов.

Этот контекст отвечает за:
- Управление планами выполнения (ExecutionPlan)
- Управление подзадачами (Subtask)
- Разрешение зависимостей между подзадачами
- Отслеживание прогресса выполнения

Архитектура:
- entities/ - Доменные сущности (ExecutionPlan, Subtask)
- value_objects/ - Value Objects (PlanId, SubtaskId, PlanStatus, SubtaskStatus)
- services/ - Доменные сервисы (DependencyResolver)
- repositories/ - Интерфейсы репозиториев
- events/ - Доменные события
"""

from .entities import ExecutionPlan, Subtask
from .value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    PlanStatusEnum,
    SubtaskStatus,
    SubtaskStatusEnum,
)
from .services import DependencyResolver
from .repositories import ExecutionPlanRepository
from .events import (
    PlanCreated,
    PlanApproved,
    PlanExecutionStarted,
    PlanCompleted,
    PlanFailed,
    PlanCancelled,
    SubtaskStarted,
    SubtaskCompleted,
    SubtaskFailed,
    SubtaskBlocked,
    SubtaskUnblocked,
)

__all__ = [
    # Entities
    "ExecutionPlan",
    "Subtask",
    # Value Objects
    "PlanId",
    "SubtaskId",
    "PlanStatus",
    "PlanStatusEnum",
    "SubtaskStatus",
    "SubtaskStatusEnum",
    # Services
    "DependencyResolver",
    # Repositories
    "ExecutionPlanRepository",
    # Events
    "PlanCreated",
    "PlanApproved",
    "PlanExecutionStarted",
    "PlanCompleted",
    "PlanFailed",
    "PlanCancelled",
    "SubtaskStarted",
    "SubtaskCompleted",
    "SubtaskFailed",
    "SubtaskBlocked",
    "SubtaskUnblocked",
]

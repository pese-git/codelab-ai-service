"""
Адаптеры для обратной совместимости между старыми и новыми entities.

Эти адаптеры обеспечивают плавную миграцию от старой архитектуры к новой,
позволяя существующему коду продолжать работать без изменений.
"""

from .session_adapter import SessionAdapter
from .agent_context_adapter import AgentContextAdapter
from .plan_adapter import PlanAdapter
from .approval_adapter import ApprovalAdapter

__all__ = [
    "SessionAdapter",
    "AgentContextAdapter",
    "PlanAdapter",
    "ApprovalAdapter",
]

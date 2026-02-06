"""
Интерфейсы репозиториев (Repository Interfaces).

Этот модуль содержит абстрактные интерфейсы для репозиториев.
Репозитории инкапсулируют логику доступа к данным и предоставляют
коллекционно-подобный интерфейс для работы с сущностями.

MIGRATION NOTE (Phase 10):
- SessionRepository, AgentContextRepository, PlanRepository are now aliases to new DDD repositories
- Legacy repository interfaces moved to *_legacy.py files
- Use new imports from domain.session_context, domain.agent_context, domain.execution_context
"""

from .base import Repository
from .approval_repository import ApprovalRepository

# Алиасы для обратной совместимости (deprecated - use new DDD repositories)
from ..session_context.repositories.conversation_repository import ConversationRepository as SessionRepository
from ..agent_context.repositories.agent_repository import AgentRepository as AgentContextRepository
from ..execution_context.repositories.execution_plan_repository import ExecutionPlanRepository as PlanRepository

__all__ = [
    "Repository",
    "ApprovalRepository",
    # Deprecated aliases (use new DDD repositories instead)
    "SessionRepository",  # Use ConversationRepository from domain.session_context
    "AgentContextRepository",  # Use AgentRepository from domain.agent_context
    "PlanRepository",  # Use ExecutionPlanRepository from domain.execution_context
]

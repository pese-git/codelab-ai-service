"""
Интерфейсы репозиториев (Repository Interfaces).

Этот модуль содержит абстрактные интерфейсы для репозиториев.
Репозитории инкапсулируют логику доступа к данным и предоставляют
коллекционно-подобный интерфейс для работы с сущностями.

Clean Architecture (DDD):
- Use ConversationRepository from domain.session_context
- Use AgentRepository from domain.agent_context
- Use ExecutionPlanRepository from domain.execution_context
"""

from .base import Repository
from .approval_repository import ApprovalRepository

__all__ = [
    "Repository",
    "ApprovalRepository",
]

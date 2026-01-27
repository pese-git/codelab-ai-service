"""
Интерфейсы репозиториев (Repository Interfaces).

Этот модуль содержит абстрактные интерфейсы для репозиториев.
Репозитории инкапсулируют логику доступа к данным и предоставляют
коллекционно-подобный интерфейс для работы с сущностями.
"""

from .base import Repository
from .session_repository import SessionRepository
from .agent_context_repository import AgentContextRepository
from .hitl_repository import HITLRepository
from .approval_repository import ApprovalRepository

__all__ = [
    "Repository",
    "SessionRepository",
    "AgentContextRepository",
    "HITLRepository",
    "ApprovalRepository",
]

"""
Мапперы для преобразования между доменными сущностями и моделями БД.

Мапперы изолируют доменный слой от деталей персистентности.
"""

from .session_mapper import SessionMapper
from .agent_context_mapper import AgentContextMapper

__all__ = [
    "SessionMapper",
    "AgentContextMapper",
]

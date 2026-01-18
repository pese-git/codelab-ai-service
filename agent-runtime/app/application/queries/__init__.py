"""
Queries (Запросы).

Запросы представляют намерение получить данные без изменения состояния.
Следуют паттерну CQRS (Command Query Responsibility Segregation).
"""

from .base import Query, QueryHandler
from .get_session import GetSessionQuery, GetSessionHandler
from .list_sessions import ListSessionsQuery, ListSessionsHandler
from .get_agent_context import GetAgentContextQuery, GetAgentContextHandler

__all__ = [
    "Query",
    "QueryHandler",
    "GetSessionQuery",
    "GetSessionHandler",
    "ListSessionsQuery",
    "ListSessionsHandler",
    "GetAgentContextQuery",
    "GetAgentContextHandler",
]

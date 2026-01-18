"""
API схемы для запросов и ответов.

Этот модуль содержит Pydantic схемы для валидации
входящих запросов и форматирования ответов API.
"""

from .session_schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    GetSessionResponse,
    ListSessionsResponse
)
from .message_schemas import (
    AddMessageRequest,
    MessageStreamRequest
)
from .agent_schemas import (
    SwitchAgentRequest,
    GetAgentContextResponse,
    ListAgentsResponse
)
from .health_schemas import HealthResponse

__all__ = [
    # Session schemas
    "CreateSessionRequest",
    "CreateSessionResponse",
    "GetSessionResponse",
    "ListSessionsResponse",
    # Message schemas
    "AddMessageRequest",
    "MessageStreamRequest",
    # Agent schemas
    "SwitchAgentRequest",
    "GetAgentContextResponse",
    "ListAgentsResponse",
    # Health
    "HealthResponse",
]

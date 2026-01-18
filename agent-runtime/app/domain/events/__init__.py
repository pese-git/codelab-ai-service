"""
Доменные события (Domain Events).

Этот модуль содержит базовые классы для доменных событий.
Доменные события описывают важные бизнес-события, которые произошли в системе.
"""

from .base import DomainEvent
from .session_events import (
    SessionCreated,
    MessageReceived,
    ConversationCompleted,
    SessionDeactivated,
    SessionExpired
)
from .agent_events import (
    AgentAssigned,
    AgentSwitchRequested,
    AgentSwitched,
    TaskStarted,
    TaskCompleted,
    TaskFailed
)

__all__ = [
    "DomainEvent",
    # Session events
    "SessionCreated",
    "MessageReceived",
    "ConversationCompleted",
    "SessionDeactivated",
    "SessionExpired",
    # Agent events
    "AgentAssigned",
    "AgentSwitchRequested",
    "AgentSwitched",
    "TaskStarted",
    "TaskCompleted",
    "TaskFailed",
]

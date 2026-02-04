"""
Domain Events для Agent Context.

Этот модуль содержит события, которые происходят в жизненном цикле агента.
"""

from .agent_events import (
    AgentCreated,
    AgentSwitched,
    AgentResetToOrchestrator,
    AgentMetadataUpdated,
    AgentSwitchLimitReached,
)

__all__ = [
    "AgentCreated",
    "AgentSwitched",
    "AgentResetToOrchestrator",
    "AgentMetadataUpdated",
    "AgentSwitchLimitReached",
]

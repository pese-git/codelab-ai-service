"""
Agent Context Bounded Context.

Этот модуль содержит все компоненты для управления агентами:
- Value Objects: AgentId, AgentCapabilities, AgentType
- Entities: Agent, AgentSwitchRecord
- Services: AgentRouterService
- Repositories: AgentRepository
- Events: AgentCreated, AgentSwitched, etc.
"""

from .value_objects import AgentId, AgentCapabilities, AgentType
from .entities import Agent, AgentSwitchRecord
from .services import AgentRouterService
from .repositories import AgentRepository
from .events import (
    AgentCreated,
    AgentSwitched,
    AgentResetToOrchestrator,
    AgentMetadataUpdated,
    AgentSwitchLimitReached,
)

__all__ = [
    # Value Objects
    "AgentId",
    "AgentCapabilities",
    "AgentType",
    
    # Entities
    "Agent",
    "AgentSwitchRecord",
    
    # Services
    "AgentRouterService",
    
    # Repositories
    "AgentRepository",
    
    # Events
    "AgentCreated",
    "AgentSwitched",
    "AgentResetToOrchestrator",
    "AgentMetadataUpdated",
    "AgentSwitchLimitReached",
]

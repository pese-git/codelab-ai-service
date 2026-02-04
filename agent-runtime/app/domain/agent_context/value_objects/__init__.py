"""
Value Objects для Agent Context.

Этот модуль содержит value objects, которые инкапсулируют
примитивные типы и бизнес-логику валидации для Agent Context.
"""

from .agent_id import AgentId
from .agent_capabilities import AgentCapabilities, AgentType

__all__ = [
    "AgentId",
    "AgentCapabilities",
    "AgentType",
]

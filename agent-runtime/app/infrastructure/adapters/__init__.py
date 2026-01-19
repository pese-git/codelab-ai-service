"""
Адаптеры для интеграции между слоями.

Адаптеры связывают новую архитектуру с существующей инфраструктурой.
"""

from .event_publisher_adapter import EventPublisherAdapter
from .session_manager_adapter import SessionManagerAdapter
from .agent_context_manager_adapter import AgentContextManagerAdapter

__all__ = [
    "EventPublisherAdapter",
    "SessionManagerAdapter",
    "AgentContextManagerAdapter",
]

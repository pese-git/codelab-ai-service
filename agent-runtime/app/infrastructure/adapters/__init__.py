"""
Адаптеры для интеграции между слоями.

Адаптеры связывают новую архитектуру с существующей инфраструктурой.
"""

from .event_publisher_adapter import EventPublisherAdapter

__all__ = [
    "EventPublisherAdapter",
]

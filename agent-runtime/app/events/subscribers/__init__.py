"""
Event subscribers for the Event-Driven Architecture.

Subscribers react to published events and perform various actions:
- Collect metrics
- Log events
- Send notifications
- Update caches
- etc.
"""

from .metrics_collector import MetricsCollector, metrics_collector
from .audit_logger import AuditLogger, audit_logger

__all__ = [
    "MetricsCollector",
    "metrics_collector",
    "AuditLogger",
    "audit_logger",
]

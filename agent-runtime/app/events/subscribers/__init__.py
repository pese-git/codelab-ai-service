"""
Event subscribers for the Event-Driven Architecture.

Subscribers react to published events and perform various actions:
- Collect metrics
- Log events
- Update agent context
- Send notifications
- Update caches
- etc.

Note: Persistence is handled by domain services (SessionManagementService, AgentOrchestrationService)
      directly, not through event subscribers. This ensures immediate persistence and ACID guarantees.
"""

from .metrics_collector import MetricsCollector, metrics_collector
from .audit_logger import AuditLogger, audit_logger
from .agent_context_subscriber import AgentContextSubscriber, agent_context_subscriber
from .session_metrics_collector import SessionMetricsCollector, session_metrics_collector

__all__ = [
    "MetricsCollector",
    "metrics_collector",
    "AuditLogger",
    "audit_logger",
    "AgentContextSubscriber",
    "agent_context_subscriber",
    "SessionMetricsCollector",
    "session_metrics_collector",
]

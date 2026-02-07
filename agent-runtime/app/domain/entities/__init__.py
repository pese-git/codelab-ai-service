"""
Доменные сущности (Domain Entities).

Этот модуль содержит базовые классы для доменных сущностей.
Сущности представляют бизнес-объекты с уникальной идентичностью.

MIGRATION NOTE (Phase 10):
- Session, AgentContext, AgentType, AgentSwitch are now aliases to new DDD entities
- Legacy entities moved to *_legacy.py files
- Use new imports from domain.session_context and domain.agent_context for new code
- Lazy imports used to avoid circular dependencies
"""

from .base import Entity
from .message import Message

from .hitl import (
    HITLDecision,
    HITLPolicyRule,
    HITLPolicy,
    HITLUserDecision,
    HITLAuditLog,
    HITLPendingState
)
from .approval import (
    ApprovalRequestType,
    ApprovalPolicyRule,
    ApprovalPolicy,
    PendingApprovalState
)

# Lazy imports для алиасов (избегаем circular imports)
def __getattr__(name):
    """Lazy loading для deprecated aliases."""
    if name == "Session":
        from ..session_context.entities.conversation import Conversation
        return Conversation
    elif name == "AgentContext":
        from ..agent_context.entities.agent import Agent
        return Agent
    elif name == "AgentSwitch":
        from ..agent_context.entities.agent import AgentSwitchRecord
        return AgentSwitchRecord
    elif name == "AgentType":
        from ..agent_context.value_objects.agent_capabilities import AgentType as AT
        return AT
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "Entity",
    "Message",
    # Deprecated aliases (use new DDD entities instead)
    "Session",  # Use Conversation from domain.session_context
    "AgentContext",  # Use Agent from domain.agent_context
    "AgentType",  # Use from domain.agent_context.value_objects
    "AgentSwitch",  # Use AgentSwitchRecord from domain.agent_context.entities
    # HITL entities
    "HITLDecision",
    "HITLPolicyRule",
    "HITLPolicy",
    "HITLUserDecision",
    "HITLAuditLog",
    "HITLPendingState",
    # Approval entities
    "ApprovalRequestType",
    "ApprovalPolicyRule",
    "ApprovalPolicy",
    "PendingApprovalState",
]

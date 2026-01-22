"""
Доменные сущности (Domain Entities).

Этот модуль содержит базовые классы для доменных сущностей.
Сущности представляют бизнес-объекты с уникальной идентичностью.
"""

from .base import Entity
from .message import Message
from .session import Session
from .agent_context import AgentContext, AgentType, AgentSwitch
from .hitl import (
    HITLDecision,
    HITLPolicyRule,
    HITLPolicy,
    HITLUserDecision,
    HITLAuditLog,
    HITLPendingState
)

__all__ = [
    "Entity",
    "Message",
    "Session",
    "AgentContext",
    "AgentType",
    "AgentSwitch",
    "HITLDecision",
    "HITLPolicyRule",
    "HITLPolicy",
    "HITLUserDecision",
    "HITLAuditLog",
    "HITLPendingState",
]

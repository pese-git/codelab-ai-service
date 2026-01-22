"""
Доменные сервисы (Domain Services).

Этот модуль содержит доменные сервисы - объекты, которые инкапсулируют
бизнес-логику, не принадлежащую конкретной сущности.
"""

from .session_management import SessionManagementService
from .agent_orchestration import AgentOrchestrationService
from .message_orchestration import MessageOrchestrationService
from .hitl_management import HITLManager, hitl_manager
from .hitl_policy import HITLPolicyService, hitl_policy_service
from .agent_registry import AgentRegistry, agent_registry, agent_router
from .tool_registry import TOOLS_SPEC, LOCAL_TOOLS, execute_local_tool

__all__ = [
    "SessionManagementService",
    "AgentOrchestrationService",
    "MessageOrchestrationService",
    "HITLManager",
    "hitl_manager",
    "HITLPolicyService",
    "hitl_policy_service",
    "AgentRegistry",
    "agent_registry",
    "agent_router",  # Backward compatibility
    "TOOLS_SPEC",
    "LOCAL_TOOLS",
    "execute_local_tool",
]

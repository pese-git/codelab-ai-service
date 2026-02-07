"""
Доменные сервисы (Domain Services).

Этот модуль содержит доменные сервисы - объекты, которые инкапсулируют
бизнес-логику, не принадлежащую конкретной сущности.
"""

# Новая архитектура - ConversationManagementService
from app.domain.session_context.services import ConversationManagementService

# Обратная совместимость - SessionManagementService (deprecated)
from .session_management import SessionManagementService

from .agent_orchestration import AgentOrchestrationService
from .hitl_policy import HITLPolicyService, hitl_policy_service
from .approval_management import ApprovalManager, get_approval_manager_with_db, approval_manager
from .agent_registry import AgentRegistry, agent_registry, agent_router
from .tool_registry import TOOLS_SPEC, LOCAL_TOOLS, execute_local_tool

# Execution Engine
from .execution_engine import ExecutionEngine

# Новые специализированные сервисы (рефакторинг MessageOrchestrationService)
from .helpers.agent_switch_helper import AgentSwitchHelper
from .message_processor import MessageProcessor
from .agent_switcher import AgentSwitcher
from .tool_result_handler import ToolResultHandler
from .hitl_decision_handler import HITLDecisionHandler
from .plan_approval_handler import PlanApprovalHandler

__all__ = [
    # Новая архитектура
    "ConversationManagementService",
    # Существующие сервисы (SessionManagementService deprecated)
    "SessionManagementService",
    "AgentOrchestrationService",
    "HITLPolicyService",
    "hitl_policy_service",
    "ApprovalManager",
    "get_approval_manager_with_db",
    "approval_manager",
    "AgentRegistry",
    "agent_registry",
    "agent_router",
    "TOOLS_SPEC",
    "LOCAL_TOOLS",
    "execute_local_tool",
    "ExecutionEngine",
    # Новые специализированные сервисы
    "AgentSwitchHelper",
    "MessageProcessor",
    "AgentSwitcher",
    "ToolResultHandler",
    "HITLDecisionHandler",
    "PlanApprovalHandler",
]

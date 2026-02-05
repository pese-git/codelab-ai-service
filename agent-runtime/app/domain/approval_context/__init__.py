"""
Approval Context — Bounded Context для управления утверждениями и HITL политиками.

Этот контекст отвечает за:
- Управление запросами на утверждение (tool calls, plans, etc.)
- HITL (Human-in-the-Loop) политики и правила
- Автоматическое принятие решений на основе политик
- Жизненный цикл утверждений (pending → approved/rejected/expired)

Архитектура:
- Value Objects: ApprovalId, ApprovalStatus, ApprovalType, PolicyAction
- Entities: ApprovalRequest, HITLPolicy, PolicyRule
- Domain Events: 8 событий жизненного цикла
- Repository: ApprovalRepository interface
- Services: ApprovalService, HITLPolicyService
"""

from .value_objects import (
    ApprovalId,
    ApprovalStatus,
    ApprovalStatusEnum,
    ApprovalType,
    ApprovalTypeEnum,
    PolicyAction,
    PolicyActionEnum,
)
from .entities import (
    ApprovalRequest,
    HITLPolicy,
    PolicyRule,
)
from .events import (
    ApprovalRequested,
    ApprovalGranted,
    ApprovalRejected,
    ApprovalExpired,
    PolicyEvaluated,
    PolicyRuleMatched,
    AutoApprovalGranted,
    UserDecisionRequired,
)
from .repositories import ApprovalRepository
from .services import ApprovalService, HITLPolicyService

__all__ = [
    # Value Objects
    "ApprovalId",
    "ApprovalStatus",
    "ApprovalStatusEnum",
    "ApprovalType",
    "ApprovalTypeEnum",
    "PolicyAction",
    "PolicyActionEnum",
    # Entities
    "ApprovalRequest",
    "HITLPolicy",
    "PolicyRule",
    # Events
    "ApprovalRequested",
    "ApprovalGranted",
    "ApprovalRejected",
    "ApprovalExpired",
    "PolicyEvaluated",
    "PolicyRuleMatched",
    "AutoApprovalGranted",
    "UserDecisionRequired",
    # Repository
    "ApprovalRepository",
    # Services
    "ApprovalService",
    "HITLPolicyService",
]

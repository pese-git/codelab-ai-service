"""
Реализации репозиториев.

Этот модуль содержит конкретные реализации интерфейсов репозиториев
для работы с базой данных через SQLAlchemy.

Новая Clean Architecture (DDD):
- ConversationRepositoryImpl - управление разговорами (замена SessionRepositoryImpl)
- AgentRepositoryImpl - управление агентами (замена AgentContextRepositoryImpl)
- ExecutionPlanRepositoryImpl - управление планами (замена PlanRepositoryImpl)
"""

# Новые DDD repositories
from .conversation_repository_impl import ConversationRepositoryImpl
from .agent_repository_impl import AgentRepositoryImpl
from .execution_plan_repository_impl import ExecutionPlanRepositoryImpl
from .fsm_state_repository_impl import FSMStateRepositoryImpl

# Алиасы для обратной совместимости (deprecated)
# TODO: Удалить после полной миграции всех зависимостей
SessionRepositoryImpl = ConversationRepositoryImpl
AgentContextRepositoryImpl = AgentRepositoryImpl

__all__ = [
    # Новые DDD repositories
    "ConversationRepositoryImpl",
    "AgentRepositoryImpl",
    "ExecutionPlanRepositoryImpl",
    "FSMStateRepositoryImpl",
    # Deprecated aliases (для обратной совместимости)
    "SessionRepositoryImpl",
    "AgentContextRepositoryImpl",
]

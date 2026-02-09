"""
Реализации репозиториев.

Этот модуль содержит конкретные реализации интерфейсов репозиториев
для работы с базой данных через SQLAlchemy.

Новая Clean Architecture (DDD):
- ConversationRepositoryImpl - управление разговорами
- AgentRepositoryImpl - управление агентами
- ExecutionPlanRepositoryImpl - управление планами
"""

# Новые DDD repositories
from .conversation_repository_impl import ConversationRepositoryImpl
from .agent_repository_impl import AgentRepositoryImpl
from .execution_plan_repository_impl import ExecutionPlanRepositoryImpl
from .fsm_state_repository_impl import FSMStateRepositoryImpl

__all__ = [
    "ConversationRepositoryImpl",
    "AgentRepositoryImpl",
    "ExecutionPlanRepositoryImpl",
    "FSMStateRepositoryImpl",
]

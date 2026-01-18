"""
SQLAlchemy модели для персистентности.

Этот модуль содержит модели базы данных.
Модели используются только в Infrastructure Layer.
"""

# Импортируем существующие модели из старого модуля для обратной совместимости
from ....services.database import (
    SessionModel,
    MessageModel,
    AgentContextModel,
    AgentSwitchModel,
    PendingApproval,
    Base
)

__all__ = [
    "SessionModel",
    "MessageModel",
    "AgentContextModel",
    "AgentSwitchModel",
    "PendingApproval",
    "Base",
]

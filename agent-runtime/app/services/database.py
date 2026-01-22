"""
SQLAlchemy database module for persistent session and agent context storage.

DEPRECATED: This module is kept for backward compatibility.
New code should use:
- Models: app.infrastructure.persistence.models
- Database functions: app.infrastructure.persistence.database
- DatabaseService: app.infrastructure.persistence.database

This file re-exports everything from the new location.
"""
import logging

logger = logging.getLogger("agent-runtime.services.database")

# Re-export models from new location
from ..infrastructure.persistence.models import (
    Base,
    SessionModel,
    MessageModel,
    AgentContextModel,
    AgentSwitchModel,
    PendingApproval
)

# Re-export database functions and service from new location
from ..infrastructure.persistence.database import (
    init_database,
    get_db,
    init_db,
    close_db,
    DatabaseService,
    get_database_service
)

__all__ = [
    # Models
    "Base",
    "SessionModel",
    "MessageModel",
    "AgentContextModel",
    "AgentSwitchModel",
    "PendingApproval",
    # Functions
    "init_database",
    "get_db",
    "init_db",
    "close_db",
    # Service
    "DatabaseService",
    "get_database_service",
]

logger.warning(
    "app.services.database is deprecated. "
    "Use app.infrastructure.persistence.database and app.infrastructure.persistence.models instead."
)

"""
FastAPI dependencies for agent runtime service.

UPDATED: Removed deprecated AsyncSessionManager and AsyncAgentContextManager dependencies.
         Use adapters from main.py or new architecture services instead.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db, get_database_service, DatabaseService

# Database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Database service dependency
DBService = Annotated[DatabaseService, Depends(get_database_service)]


# Note: Old AsyncSessionManager and AsyncAgentContextManager dependencies removed.
#
# For session/context management, use:
# - SessionManagerAdapter from app.main (global instance)
# - AgentContextManagerAdapter from app.main (global instance)
# - Or inject domain services directly via dependencies_new.py
#
# Migration completed: 20 January 2026

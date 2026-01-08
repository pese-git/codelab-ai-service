"""FastAPI dependencies for agent runtime service"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db, get_database_service, DatabaseService

# Database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Database service dependency
DBService = Annotated[DatabaseService, Depends(get_database_service)]


# Async manager dependencies
async def get_session_manager_dep():
    """Get async session manager dependency"""
    from app.services.session_manager_async import session_manager
    if session_manager is None:
        raise RuntimeError("SessionManager not initialized")
    return session_manager


async def get_agent_context_manager_dep():
    """Get async agent context manager dependency"""
    from app.services.agent_context_async import agent_context_manager
    if agent_context_manager is None:
        raise RuntimeError("AgentContextManager not initialized")
    return agent_context_manager


# Type annotations for async managers
from app.services.session_manager_async import AsyncSessionManager
from app.services.agent_context_async import AsyncAgentContextManager

SessionManagerDep = Annotated[AsyncSessionManager, Depends(get_session_manager_dep)]
AgentContextManagerDep = Annotated[AsyncAgentContextManager, Depends(get_agent_context_manager_dep)]

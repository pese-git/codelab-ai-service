"""FastAPI dependencies for agent runtime service"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db, get_database_service, DatabaseService

# Database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Database service dependency
DBService = Annotated[DatabaseService, Depends(get_database_service)]

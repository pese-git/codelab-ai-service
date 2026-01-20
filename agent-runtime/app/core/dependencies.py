"""
FastAPI dependencies для agent runtime service.

Для управления сессиями и контекстом используйте:
- Адаптеры из main.py (глобальные экземпляры)
- Или доменные сервисы напрямую через dependencies_new.py
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db, get_database_service, DatabaseService

# Database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Database service dependency
DBService = Annotated[DatabaseService, Depends(get_database_service)]


# Для управления сессиями и контекстом используйте:
# - SessionManagerAdapter из app.main (глобальный экземпляр)
# - AgentContextManagerAdapter из app.main (глобальный экземпляр)
# - Или доменные сервисы напрямую через dependencies_new.py

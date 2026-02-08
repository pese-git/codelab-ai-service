"""
Database service - алиас для обратной совместимости.

Этот модуль предоставляет алиасы для функций из app.infrastructure.persistence.database
для обратной совместимости с существующим кодом.
"""

from app.infrastructure.persistence.database import (
    get_db,
    init_db,
    close_db,
    get_database_service,
    DatabaseService,
    init_database
)

__all__ = [
    "get_db",
    "init_db",
    "close_db",
    "get_database_service",
    "DatabaseService",
    "init_database"
]

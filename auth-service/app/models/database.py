"""Database configuration and base models"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all database models"""

    pass


# Create async engine for SQLite
# Note: SQLite URL needs to be converted for async support
db_url = settings.db_url
if db_url.startswith("sqlite:///"):
    # Convert sqlite:/// to sqlite+aiosqlite:///
    async_db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    async_db_url = db_url

engine = create_async_engine(
    async_db_url,
    echo=settings.is_development,
    future=True,
)

# Create async session factory
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Enable WAL mode for SQLite (for better concurrency)
if "sqlite" in db_url:
    sync_engine = create_engine(
        db_url,
        echo=settings.is_development,
    )

    @event.listens_for(sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Set SQLite pragmas for better performance"""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
        cursor.close()


async def get_db() -> AsyncSession:
    """Dependency for getting async database session"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database (create tables)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()

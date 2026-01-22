"""
Integration тесты для репозиториев.

Проверяет работу репозиториев с реальной БД (SQLite in-memory).
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.repositories import (
    SessionRepositoryImpl,
    AgentContextRepositoryImpl
)
from app.domain.entities import Session, Message, AgentContext, AgentType


@pytest_asyncio.fixture
async def db_session():
    """
    Фикстура для создания in-memory БД для тестов.
    
    Создает временную БД SQLite в памяти для каждого теста.
    """
    # Создать in-memory БД
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Создать таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создать session maker
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Создать сессию для теста
    async with async_session_maker() as session:
        yield session
        await session.rollback()
    
    # Очистить
    await engine.dispose()


# ==================== Тесты SessionRepository ====================

class TestSessionRepositoryImpl:
    """Integration тесты для SessionRepositoryImpl"""
    
    @pytest.mark.asyncio
    async def test_save_and_find_session(self, db_session):
        """Тест сохранения и поиска сессии"""
        repository = SessionRepositoryImpl(db_session)
        
        # Создать сессию
        session = Session(id="session-1", title="Test Session")
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="Привет!"
        ))
        
        # Сохранить
        await repository.save(session)
        
        # Найти
        found = await repository.find_by_id("session-1")
        
        assert found is not None
        assert found.id == "session-1"
        assert found.title == "Test Session"
        assert found.get_message_count() == 1
        assert found.messages[0].content == "Привет!"
    
    @pytest.mark.asyncio
    async def test_find_nonexistent_session(self, db_session):
        """Тест поиска несуществующей сессии"""
        repository = SessionRepositoryImpl(db_session)
        
        found = await repository.find_by_id("nonexistent")
        
        assert found is None
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, db_session):
        """Тест получения списка сессий"""
        repository = SessionRepositoryImpl(db_session)
        
        # Создать несколько сессий
        for i in range(3):
            session = Session(id=f"session-{i}", title=f"Session {i}")
            await repository.save(session)
        
        # Получить список
        sessions = await repository.list(limit=10, offset=0)
        
        assert len(sessions) == 3
    
    @pytest.mark.asyncio
    async def test_find_active_sessions(self, db_session):
        """Тест поиска активных сессий"""
        repository = SessionRepositoryImpl(db_session)
        
        # Создать активную и неактивную сессии
        active_session = Session(id="session-active", is_active=True)
        inactive_session = Session(id="session-inactive", is_active=False)
        
        await repository.save(active_session)
        await repository.save(inactive_session)
        
        # Найти только активные
        active = await repository.find_active(limit=10)
        
        assert len(active) == 1
        assert active[0].id == "session-active"
    
    @pytest.mark.asyncio
    async def test_count_active_sessions(self, db_session):
        """Тест подсчета активных сессий"""
        repository = SessionRepositoryImpl(db_session)
        
        # Создать сессии
        for i in range(5):
            session = Session(id=f"session-{i}", is_active=(i < 3))
            await repository.save(session)
        
        # Подсчитать активные
        count = await repository.count_active()
        
        assert count == 3


# ==================== Тесты AgentContextRepository ====================

class TestAgentContextRepositoryImpl:
    """Integration тесты для AgentContextRepositoryImpl"""
    
    @pytest.mark.asyncio
    async def test_save_and_find_context(self, db_session):
        """Тест сохранения и поиска контекста"""
        # Сначала создать сессию (требуется для FK)
        session_repo = SessionRepositoryImpl(db_session)
        session = Session(id="session-1")
        await session_repo.save(session)
        
        # Создать контекст
        context_repo = AgentContextRepositoryImpl(db_session)
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            current_agent=AgentType.CODER
        )
        
        # Сохранить
        await context_repo.save(context)
        
        # Найти
        found = await context_repo.find_by_session_id("session-1")
        
        assert found is not None
        assert found.id == "ctx-1"
        assert found.session_id == "session-1"
        assert found.current_agent == AgentType.CODER
    
    @pytest.mark.asyncio
    async def test_save_context_with_switches(self, db_session):
        """Тест сохранения контекста с историей переключений"""
        # Создать сессию
        session_repo = SessionRepositoryImpl(db_session)
        session = Session(id="session-1")
        await session_repo.save(session)
        
        # Создать контекст с переключениями
        context_repo = AgentContextRepositoryImpl(db_session)
        context = AgentContext(
            id="ctx-1",
            session_id="session-1"
        )
        context.switch_to(AgentType.CODER, "Coding task")
        context.switch_to(AgentType.DEBUG, "Debug issue")
        
        # Сохранить
        await context_repo.save(context)
        
        # Найти и проверить историю
        found = await context_repo.find_by_session_id("session-1")
        
        assert found is not None
        assert found.switch_count == 2
        assert len(found.switch_history) == 2
        assert found.switch_history[0].to_agent == AgentType.CODER
        assert found.switch_history[1].to_agent == AgentType.DEBUG
    
    @pytest.mark.asyncio
    async def test_find_by_agent_type(self, db_session):
        """Тест поиска контекстов по типу агента"""
        # Создать сессии и контексты
        session_repo = SessionRepositoryImpl(db_session)
        context_repo = AgentContextRepositoryImpl(db_session)
        
        for i in range(3):
            session = Session(id=f"session-{i}")
            await session_repo.save(session)
            
            agent_type = AgentType.CODER if i < 2 else AgentType.ARCHITECT
            context = AgentContext(
                id=f"ctx-{i}",
                session_id=f"session-{i}",
                current_agent=agent_type
            )
            await context_repo.save(context)
        
        # Найти контексты с Coder
        coder_contexts = await context_repo.find_by_agent_type(AgentType.CODER)
        
        assert len(coder_contexts) == 2
    
    @pytest.mark.asyncio
    async def test_get_agent_usage_stats(self, db_session):
        """Тест получения статистики использования агентов"""
        # Создать сессии и контексты
        session_repo = SessionRepositoryImpl(db_session)
        context_repo = AgentContextRepositoryImpl(db_session)
        
        agents = [AgentType.CODER, AgentType.CODER, AgentType.ARCHITECT]
        for i, agent_type in enumerate(agents):
            session = Session(id=f"session-{i}")
            await session_repo.save(session)
            
            context = AgentContext(
                id=f"ctx-{i}",
                session_id=f"session-{i}",
                current_agent=agent_type
            )
            await context_repo.save(context)
        
        # Получить статистику
        stats = await context_repo.get_agent_usage_stats()
        
        assert stats["coder"] == 2
        assert stats["architect"] == 1
        assert stats["orchestrator"] == 0  # Нет сессий с orchestrator

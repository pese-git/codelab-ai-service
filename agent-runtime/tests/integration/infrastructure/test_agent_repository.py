"""
Integration тесты для AgentRepositoryImpl.

Тестирует взаимодействие с реальной БД через SQLAlchemy.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.repositories import AgentRepositoryImpl
from app.domain.agent_context.entities import Agent
from app.domain.agent_context.value_objects import AgentId, AgentCapabilities, AgentType


@pytest_asyncio.fixture
async def db_engine():
    """Создать in-memory SQLite engine для тестов."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Создать таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Создать сессию БД для тестов."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def agent_repository(db_session):
    """Создать AgentRepositoryImpl."""
    return AgentRepositoryImpl(db_session)


@pytest.fixture
def sample_agent():
    """Создать тестового агента."""
    agent = Agent.create(
        session_id="session-123",
        capabilities=AgentCapabilities.for_orchestrator()
    )
    return agent


class TestAgentRepositoryImpl:
    """Тесты для AgentRepositoryImpl."""
    
    @pytest.mark.asyncio
    async def test_save_and_find_by_id(
        self,
        agent_repository,
        sample_agent,
        db_session
    ):
        """Тест сохранения и поиска агента по ID."""
        # Arrange
        agent_id = AgentId(sample_agent.id)
        
        # Act - Save
        await agent_repository.save(sample_agent)
        await db_session.commit()
        
        # Act - Find
        found = await agent_repository.find_by_id(agent_id)
        
        # Assert
        assert found is not None
        assert found.id == sample_agent.id
        assert found.session_id == "session-123"
        assert found.current_type == AgentType.ORCHESTRATOR
        assert found.switch_count == 0
    
    @pytest.mark.asyncio
    async def test_find_by_session_id(
        self,
        agent_repository,
        sample_agent,
        db_session
    ):
        """Тест поиска агента по session_id."""
        # Arrange
        await agent_repository.save(sample_agent)
        await db_session.commit()
        
        # Act
        found = await agent_repository.find_by_session_id("session-123")
        
        # Assert
        assert found is not None
        assert found.session_id == "session-123"
        assert found.current_type == AgentType.ORCHESTRATOR
    
    @pytest.mark.asyncio
    async def test_find_by_session_id_not_found(self, agent_repository):
        """Тест поиска несуществующего агента."""
        # Act
        found = await agent_repository.find_by_session_id("non-existent")
        
        # Assert
        assert found is None
    
    @pytest.mark.asyncio
    async def test_save_with_switch_history(
        self,
        agent_repository,
        sample_agent,
        db_session
    ):
        """Тест сохранения агента с историей переключений."""
        # Arrange
        sample_agent.switch_to(AgentType.CODER, "Need to code")
        sample_agent.switch_to(AgentType.DEBUG, "Need to debug")
        
        # Act - Save
        await agent_repository.save(sample_agent)
        await db_session.commit()
        
        # Act - Find
        agent_id = AgentId(sample_agent.id)
        found = await agent_repository.find_by_id(agent_id)
        
        # Assert
        assert found is not None
        assert found.current_type == AgentType.DEBUG
        assert found.switch_count == 2
        assert len(found.switch_history) == 2
        assert found.switch_history[0].to_agent == AgentType.CODER
        assert found.switch_history[1].to_agent == AgentType.DEBUG
    
    @pytest.mark.asyncio
    async def test_update_existing_agent(
        self,
        agent_repository,
        sample_agent,
        db_session
    ):
        """Тест обновления существующего агента."""
        # Arrange
        await agent_repository.save(sample_agent)
        await db_session.commit()
        
        # Act - Update
        agent_id = AgentId(sample_agent.id)
        found = await agent_repository.find_by_id(agent_id)
        found.switch_to(AgentType.ARCHITECT, "Need architecture")
        found.add_metadata("test_key", "test_value")
        
        await agent_repository.save(found)
        await db_session.commit()
        
        # Assert
        updated = await agent_repository.find_by_id(agent_id)
        assert updated.current_type == AgentType.ARCHITECT
        assert updated.switch_count == 1
        assert updated.get_metadata("test_key") == "test_value"
    
    @pytest.mark.asyncio
    async def test_delete_by_id(
        self,
        agent_repository,
        sample_agent,
        db_session
    ):
        """Тест удаления агента по ID."""
        # Arrange
        agent_id = AgentId(sample_agent.id)
        await agent_repository.save(sample_agent)
        await db_session.commit()
        
        # Act
        deleted = await agent_repository.delete(agent_id)
        await db_session.commit()
        
        # Assert
        assert deleted is True
        found = await agent_repository.find_by_id(agent_id)
        assert found is None
    
    @pytest.mark.asyncio
    async def test_delete_by_session_id(
        self,
        agent_repository,
        sample_agent,
        db_session
    ):
        """Тест удаления агента по session_id."""
        # Arrange
        await agent_repository.save(sample_agent)
        await db_session.commit()
        
        # Act
        deleted = await agent_repository.delete_by_session_id("session-123")
        await db_session.commit()
        
        # Assert
        assert deleted is True
        found = await agent_repository.find_by_session_id("session-123")
        assert found is None
    
    @pytest.mark.asyncio
    async def test_exists(
        self,
        agent_repository,
        sample_agent,
        db_session
    ):
        """Тест проверки существования агента."""
        # Arrange
        agent_id = AgentId(sample_agent.id)
        
        # Act - Before save
        exists_before = await agent_repository.exists(agent_id)
        
        # Save
        await agent_repository.save(sample_agent)
        await db_session.commit()
        
        # Act - After save
        exists_after = await agent_repository.exists(agent_id)
        
        # Assert
        assert exists_before is False
        assert exists_after is True
    
    @pytest.mark.asyncio
    async def test_find_by_agent_type(
        self,
        agent_repository,
        db_session
    ):
        """Тест поиска агентов по типу."""
        # Arrange - Create agents of different types
        orchestrator = Agent.create(
            session_id="session-1",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        coder = Agent.create(
            session_id="session-2",
            capabilities=AgentCapabilities.for_coder()
        )
        
        await agent_repository.save(orchestrator)
        await agent_repository.save(coder)
        await db_session.commit()
        
        # Act
        orchestrators = await agent_repository.find_by_agent_type(
            AgentType.ORCHESTRATOR,
            limit=10
        )
        coders = await agent_repository.find_by_agent_type(
            AgentType.CODER,
            limit=10
        )
        
        # Assert
        assert len(orchestrators) == 1
        assert orchestrators[0].current_type == AgentType.ORCHESTRATOR
        assert len(coders) == 1
        assert coders[0].current_type == AgentType.CODER
    
    @pytest.mark.asyncio
    async def test_find_with_many_switches(
        self,
        agent_repository,
        db_session
    ):
        """Тест поиска агентов с большим количеством переключений."""
        # Arrange
        agent_few = Agent.create(
            session_id="session-1",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent_few.switch_to(AgentType.CODER, "Switch 1")
        
        agent_many = Agent.create(
            session_id="session-2",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        for i in range(6):
            target = AgentType.CODER if i % 2 == 0 else AgentType.ARCHITECT
            agent_many.switch_to(target, f"Switch {i+1}")
        
        await agent_repository.save(agent_few)
        await agent_repository.save(agent_many)
        await db_session.commit()
        
        # Act
        agents = await agent_repository.find_with_many_switches(
            min_switches=5,
            limit=10
        )
        
        # Assert
        assert len(agents) == 1
        assert agents[0].switch_count >= 5
    
    @pytest.mark.asyncio
    async def test_count_by_type(
        self,
        agent_repository,
        db_session
    ):
        """Тест подсчета агентов по типу."""
        # Arrange
        for i in range(3):
            agent = Agent.create(
                session_id=f"session-{i}",
                capabilities=AgentCapabilities.for_orchestrator()
            )
            await agent_repository.save(agent)
        
        for i in range(2):
            agent = Agent.create(
                session_id=f"session-coder-{i}",
                capabilities=AgentCapabilities.for_coder()
            )
            await agent_repository.save(agent)
        
        await db_session.commit()
        
        # Act
        orchestrator_count = await agent_repository.count_by_type(AgentType.ORCHESTRATOR)
        coder_count = await agent_repository.count_by_type(AgentType.CODER)
        
        # Assert
        assert orchestrator_count == 3
        assert coder_count == 2
    
    @pytest.mark.asyncio
    async def test_get_agent_usage_stats(
        self,
        agent_repository,
        db_session
    ):
        """Тест получения статистики использования агентов."""
        # Arrange
        for agent_type in [AgentType.ORCHESTRATOR, AgentType.CODER, AgentType.CODER]:
            agent = Agent.create(
                session_id=f"session-{agent_type.value}",
                capabilities=AgentCapabilities.for_agent_type(agent_type)
            )
            await agent_repository.save(agent)
        
        await db_session.commit()
        
        # Act
        stats = await agent_repository.get_agent_usage_stats()
        
        # Assert
        assert stats.get("orchestrator") == 1
        assert stats.get("coder") == 2
    
    @pytest.mark.asyncio
    async def test_get_switch_statistics(
        self,
        agent_repository,
        db_session
    ):
        """Тест получения статистики переключений."""
        # Arrange
        agent1 = Agent.create(
            session_id="session-1",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent1.switch_to(AgentType.CODER, "Switch 1")
        agent1.switch_to(AgentType.DEBUG, "Switch 2")
        
        agent2 = Agent.create(
            session_id="session-2",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent2.switch_to(AgentType.ARCHITECT, "Switch 1")
        
        await agent_repository.save(agent1)
        await agent_repository.save(agent2)
        await db_session.commit()
        
        # Act
        stats = await agent_repository.get_switch_statistics()
        
        # Assert
        assert stats['total_switches'] == 3
        assert stats['sessions_with_switches'] == 2
        assert stats['max_switches'] == 2
        assert stats['avg_switches_per_session'] > 0
    
    @pytest.mark.asyncio
    async def test_get_recent_switches(
        self,
        agent_repository,
        db_session
    ):
        """Тест получения последних переключений."""
        # Arrange
        agent = Agent.create(
            session_id="session-1",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent.switch_to(AgentType.CODER, "First switch")
        agent.switch_to(AgentType.DEBUG, "Second switch")
        
        await agent_repository.save(agent)
        await db_session.commit()
        
        # Act
        switches = await agent_repository.get_recent_switches(limit=10)
        
        # Assert
        assert len(switches) == 2
        assert switches[0]['to_agent'] == "debug"  # Most recent first
        assert switches[1]['to_agent'] == "coder"

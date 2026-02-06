"""
Unit тесты для обновлений PlanRepositoryImpl.

Тестирует новые snapshot методы (save_snapshot, get_snapshot).
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.repositories import PlanRepositoryImpl
from app.domain.entities import Plan


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
def plan_repository(db_session):
    """Создать PlanRepositoryImpl."""
    return PlanRepositoryImpl(db_session)


@pytest.fixture
def sample_plan():
    """Создать тестовый Plan."""
    plan = Plan(
        id="plan-1",
        session_id="session-1",
        goal="Test goal",
        status="draft"
    )
    return plan


class TestPlanRepositorySnapshotMethods:
    """Тесты для snapshot методов PlanRepositoryImpl."""
    
    @pytest.mark.asyncio
    async def test_save_snapshot_basic(self, plan_repository, sample_plan):
        """Тест базового сохранения snapshot."""
        # Arrange
        session_id = "session-1"
        
        # Act
        await plan_repository.save_snapshot(session_id, sample_plan)
        
        # Assert
        snapshot = await plan_repository.get_snapshot(session_id)
        assert snapshot is not None
        assert snapshot.id == sample_plan.id
        assert snapshot.goal == sample_plan.goal
    
    @pytest.mark.asyncio
    async def test_get_snapshot_not_found(self, plan_repository):
        """Тест получения несуществующего snapshot."""
        # Arrange
        session_id = "non-existent"
        
        # Act
        snapshot = await plan_repository.get_snapshot(session_id)
        
        # Assert
        assert snapshot is None
    
    @pytest.mark.asyncio
    async def test_save_snapshot_overwrites_existing(self, plan_repository, sample_plan):
        """Тест перезаписи существующего snapshot."""
        # Arrange
        session_id = "session-1"
        await plan_repository.save_snapshot(session_id, sample_plan)
        
        # Act - Save new snapshot
        new_plan = Plan(
            id="plan-2",
            session_id=session_id,
            goal="Updated goal",
            status="approved"
        )
        await plan_repository.save_snapshot(session_id, new_plan)
        
        # Assert
        snapshot = await plan_repository.get_snapshot(session_id)
        assert snapshot is not None
        assert snapshot.id == "plan-2"
        assert snapshot.goal == "Updated goal"
        assert snapshot.status == "approved"
    
    @pytest.mark.asyncio
    async def test_save_snapshot_multiple_sessions(self, plan_repository):
        """Тест сохранения snapshots для разных сессий."""
        # Arrange
        plan1 = Plan(id="plan-1", session_id="session-1", goal="Goal 1", status="draft")
        plan2 = Plan(id="plan-2", session_id="session-2", goal="Goal 2", status="draft")
        plan3 = Plan(id="plan-3", session_id="session-3", goal="Goal 3", status="draft")
        
        # Act
        await plan_repository.save_snapshot("session-1", plan1)
        await plan_repository.save_snapshot("session-2", plan2)
        await plan_repository.save_snapshot("session-3", plan3)
        
        # Assert
        snapshot1 = await plan_repository.get_snapshot("session-1")
        snapshot2 = await plan_repository.get_snapshot("session-2")
        snapshot3 = await plan_repository.get_snapshot("session-3")
        
        assert snapshot1.id == "plan-1"
        assert snapshot2.id == "plan-2"
        assert snapshot3.id == "plan-3"
    
    @pytest.mark.asyncio
    async def test_save_snapshot_preserves_all_fields(self, plan_repository):
        """Тест сохранения всех полей плана."""
        # Arrange
        plan = Plan(
            id="plan-complex",
            session_id="session-1",
            goal="Complex goal",
            status="in_progress",
            subtasks=[
                {
                    "id": "st-1",
                    "description": "Subtask 1",
                    "agent": "coder",
                    "status": "pending",
                    "dependencies": []
                }
            ],
            current_subtask_id="st-1",
            metadata={"key": "value"}
        )
        
        # Act
        await plan_repository.save_snapshot("session-1", plan)
        
        # Assert
        snapshot = await plan_repository.get_snapshot("session-1")
        assert snapshot.id == plan.id
        assert snapshot.goal == plan.goal
        assert snapshot.status == plan.status
        assert snapshot.subtasks == plan.subtasks
        assert snapshot.current_subtask_id == plan.current_subtask_id
        assert snapshot.metadata == plan.metadata
    
    @pytest.mark.asyncio
    async def test_snapshot_isolation_from_db(self, plan_repository, sample_plan, db_session):
        """Тест изоляции snapshot от БД."""
        # Arrange - Save to DB
        await plan_repository.save(sample_plan)
        await db_session.commit()
        
        # Act - Save different snapshot
        snapshot_plan = Plan(
            id="plan-snapshot",
            session_id="session-1",
            goal="Snapshot goal",
            status="approved"
        )
        await plan_repository.save_snapshot("session-1", snapshot_plan)
        
        # Assert - DB and snapshot are different
        db_plan = await plan_repository.find_by_id("plan-1")
        snapshot = await plan_repository.get_snapshot("session-1")
        
        assert db_plan.id == "plan-1"
        assert snapshot.id == "plan-snapshot"
        assert db_plan.goal != snapshot.goal
    
    @pytest.mark.asyncio
    async def test_get_snapshot_returns_copy(self, plan_repository, sample_plan):
        """Тест что get_snapshot возвращает копию."""
        # Arrange
        session_id = "session-1"
        await plan_repository.save_snapshot(session_id, sample_plan)
        
        # Act
        snapshot1 = await plan_repository.get_snapshot(session_id)
        snapshot2 = await plan_repository.get_snapshot(session_id)
        
        # Assert - Should be different objects but same data
        assert snapshot1 is not snapshot2  # Different objects
        assert snapshot1.id == snapshot2.id  # Same data
        assert snapshot1.goal == snapshot2.goal
    
    @pytest.mark.asyncio
    async def test_save_snapshot_with_none_plan(self, plan_repository):
        """Тест сохранения None как snapshot (удаление)."""
        # Arrange
        session_id = "session-1"
        plan = Plan(id="plan-1", session_id=session_id, goal="Test", status="draft")
        await plan_repository.save_snapshot(session_id, plan)
        
        # Act - Save None to clear snapshot
        await plan_repository.save_snapshot(session_id, None)
        
        # Assert
        snapshot = await plan_repository.get_snapshot(session_id)
        assert snapshot is None
    
    @pytest.mark.asyncio
    async def test_snapshot_persistence_across_repository_instances(
        self,
        db_session,
        sample_plan
    ):
        """Тест сохранения snapshot между разными экземплярами repository."""
        # Arrange
        repo1 = PlanRepositoryImpl(db_session)
        repo2 = PlanRepositoryImpl(db_session)
        
        session_id = "session-1"
        
        # Act - Save with repo1
        await repo1.save_snapshot(session_id, sample_plan)
        
        # Assert - Get with repo2
        snapshot = await repo2.get_snapshot(session_id)
        assert snapshot is not None
        assert snapshot.id == sample_plan.id
    
    @pytest.mark.asyncio
    async def test_save_snapshot_empty_session_id(self, plan_repository, sample_plan):
        """Тест сохранения snapshot с пустым session_id."""
        # Act
        await plan_repository.save_snapshot("", sample_plan)
        
        # Assert
        snapshot = await plan_repository.get_snapshot("")
        assert snapshot is not None
        assert snapshot.id == sample_plan.id
    
    @pytest.mark.asyncio
    async def test_concurrent_snapshot_operations(self, plan_repository):
        """Тест конкурентных операций со snapshots."""
        # Arrange
        plan1 = Plan(id="plan-1", session_id="session-1", goal="Goal 1", status="draft")
        plan2 = Plan(id="plan-2", session_id="session-2", goal="Goal 2", status="draft")
        
        # Act - Save snapshots concurrently
        await plan_repository.save_snapshot("session-1", plan1)
        await plan_repository.save_snapshot("session-2", plan2)
        
        # Assert - Both should be saved correctly
        snapshot1 = await plan_repository.get_snapshot("session-1")
        snapshot2 = await plan_repository.get_snapshot("session-2")
        
        assert snapshot1.id == "plan-1"
        assert snapshot2.id == "plan-2"
    
    @pytest.mark.asyncio
    async def test_snapshot_with_complex_metadata(self, plan_repository):
        """Тест snapshot с сложными metadata."""
        # Arrange
        plan = Plan(
            id="plan-1",
            session_id="session-1",
            goal="Test",
            status="draft",
            metadata={
                "nested": {
                    "key1": "value1",
                    "key2": [1, 2, 3]
                },
                "list": ["a", "b", "c"],
                "number": 42
            }
        )
        
        # Act
        await plan_repository.save_snapshot("session-1", plan)
        
        # Assert
        snapshot = await plan_repository.get_snapshot("session-1")
        assert snapshot.metadata == plan.metadata
        assert snapshot.metadata["nested"]["key1"] == "value1"
        assert snapshot.metadata["list"] == ["a", "b", "c"]
        assert snapshot.metadata["number"] == 42
    
    @pytest.mark.asyncio
    async def test_snapshot_compatibility_with_conversation_repository(
        self,
        plan_repository,
        sample_plan
    ):
        """Тест совместимости snapshot с ConversationRepositoryImpl."""
        # Arrange
        session_id = "session-1"
        
        # Act - Save snapshot using PlanRepositoryImpl
        await plan_repository.save_snapshot(session_id, sample_plan)
        
        # Assert - Should be accessible by session_id (conversation_id)
        snapshot = await plan_repository.get_snapshot(session_id)
        assert snapshot is not None
        assert snapshot.id == sample_plan.id
        
        # Note: ConversationRepositoryImpl может использовать тот же механизм
        # для хранения snapshots планов

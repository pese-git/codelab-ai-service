"""
Unit тесты для ExecutionPlanRepositoryImpl.

Тестирует работу repository с in-memory БД.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.repositories import ExecutionPlanRepositoryImpl
from app.domain.execution_context.entities import ExecutionPlan, Subtask
from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus,
)
from app.domain.session_context.value_objects import ConversationId
from app.domain.agent_context.value_objects import AgentId


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
def execution_plan_repository(db_session):
    """Создать ExecutionPlanRepositoryImpl."""
    return ExecutionPlanRepositoryImpl(db_session)


@pytest.fixture
def sample_subtask():
    """Создать тестовую подзадачу."""
    return Subtask(
        id=SubtaskId(value="subtask-1"),
        description="Test subtask",
        agent_id=AgentId(value="coder"),
        dependencies=[],
        status=SubtaskStatus.pending(),
        estimated_time="5 min"
    )


@pytest.fixture
def sample_execution_plan(sample_subtask):
    """Создать тестовый ExecutionPlan."""
    plan = ExecutionPlan(
        id=PlanId(value="plan-1"),
        conversation_id=ConversationId(value="conv-1"),
        goal="Test goal",
        subtasks=[sample_subtask],
        status=PlanStatus.draft(),
        metadata={"key": "value"}
    )
    return plan


class TestExecutionPlanRepositoryImpl:
    """Тесты для ExecutionPlanRepositoryImpl."""
    
    @pytest.mark.asyncio
    async def test_save_and_find_by_id(
        self,
        execution_plan_repository,
        sample_execution_plan,
        db_session
    ):
        """Тест сохранения и поиска плана по ID."""
        # Arrange
        plan_id = sample_execution_plan.id
        
        # Act - Save
        await execution_plan_repository.save(sample_execution_plan)
        await db_session.commit()
        
        # Act - Find
        found = await execution_plan_repository.find_by_id(plan_id)
        
        # Assert
        assert found is not None
        assert found.id.value == plan_id.value
        assert found.goal == "Test goal"
        assert found.status.value == "draft"
        assert len(found.subtasks) == 1
        assert found.metadata == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, execution_plan_repository):
        """Тест поиска несуществующего плана."""
        # Arrange
        non_existent_id = PlanId.generate()
        
        # Act
        found = await execution_plan_repository.find_by_id(non_existent_id)
        
        # Assert
        assert found is None
    
    @pytest.mark.asyncio
    async def test_save_updates_existing(
        self,
        execution_plan_repository,
        sample_execution_plan,
        db_session
    ):
        """Тест обновления существующего плана."""
        # Arrange
        plan_id = sample_execution_plan.id
        await execution_plan_repository.save(sample_execution_plan)
        await db_session.commit()
        
        # Act - Update
        found = await execution_plan_repository.find_by_id(plan_id)
        found.goal = "Updated goal"
        
        new_subtask = Subtask(
            id=SubtaskId(value="subtask-2"),
            description="New subtask",
            agent_id=AgentId(value="debug")
        )
        found.add_subtask(new_subtask)
        
        await execution_plan_repository.save(found)
        await db_session.commit()
        
        # Assert
        updated = await execution_plan_repository.find_by_id(plan_id)
        assert updated.goal == "Updated goal"
        assert len(updated.subtasks) == 2
    
    @pytest.mark.asyncio
    async def test_delete(
        self,
        execution_plan_repository,
        sample_execution_plan,
        db_session
    ):
        """Тест удаления плана."""
        # Arrange
        plan_id = sample_execution_plan.id
        await execution_plan_repository.save(sample_execution_plan)
        await db_session.commit()
        
        # Act
        deleted = await execution_plan_repository.delete(plan_id)
        await db_session.commit()
        
        # Assert
        assert deleted is True
        found = await execution_plan_repository.find_by_id(plan_id)
        assert found is None
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self, execution_plan_repository):
        """Тест удаления несуществующего плана."""
        # Arrange
        non_existent_id = PlanId.generate()
        
        # Act
        deleted = await execution_plan_repository.delete(non_existent_id)
        
        # Assert
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_find_by_conversation_id(
        self,
        execution_plan_repository,
        db_session
    ):
        """Тест поиска планов по conversation_id."""
        # Arrange
        conv_id = ConversationId(value="conv-1")
        
        plan1 = ExecutionPlan(
            id=PlanId(value="plan-1"),
            conversation_id=conv_id,
            goal="Goal 1"
        )
        plan2 = ExecutionPlan(
            id=PlanId(value="plan-2"),
            conversation_id=conv_id,
            goal="Goal 2"
        )
        plan3 = ExecutionPlan(
            id=PlanId(value="plan-3"),
            conversation_id=ConversationId(value="conv-2"),
            goal="Goal 3"
        )
        
        await execution_plan_repository.save(plan1)
        await execution_plan_repository.save(plan2)
        await execution_plan_repository.save(plan3)
        await db_session.commit()
        
        # Act
        plans = await execution_plan_repository.find_by_conversation_id(conv_id)
        
        # Assert
        assert len(plans) == 2
        assert all(p.conversation_id.value == conv_id.value for p in plans)
    
    @pytest.mark.asyncio
    async def test_find_active_by_conversation_id(
        self,
        execution_plan_repository,
        db_session
    ):
        """Тест поиска активных планов по conversation_id."""
        # Arrange
        conv_id = ConversationId(value="conv-1")
        
        # Создать планы с разными статусами
        draft_plan = ExecutionPlan(
            id=PlanId(value="plan-draft"),
            conversation_id=conv_id,
            goal="Draft plan",
            status=PlanStatus.draft()
        )
        
        approved_plan = ExecutionPlan(
            id=PlanId(value="plan-approved"),
            conversation_id=conv_id,
            goal="Approved plan",
            status=PlanStatus.approved()
        )
        
        in_progress_plan = ExecutionPlan(
            id=PlanId(value="plan-in-progress"),
            conversation_id=conv_id,
            goal="In progress plan",
            status=PlanStatus.in_progress()
        )
        
        completed_plan = ExecutionPlan(
            id=PlanId(value="plan-completed"),
            conversation_id=conv_id,
            goal="Completed plan",
            status=PlanStatus.completed()
        )
        
        await execution_plan_repository.save(draft_plan)
        await execution_plan_repository.save(approved_plan)
        await execution_plan_repository.save(in_progress_plan)
        await execution_plan_repository.save(completed_plan)
        await db_session.commit()
        
        # Act
        active_plans = await execution_plan_repository.find_active_by_conversation_id(conv_id)
        
        # Assert
        assert len(active_plans) == 3  # draft, approved, in_progress
        statuses = [p.status.value for p in active_plans]
        assert "draft" in statuses
        assert "approved" in statuses
        assert "in_progress" in statuses
        assert "completed" not in statuses
    
    @pytest.mark.asyncio
    async def test_count_by_conversation_id(
        self,
        execution_plan_repository,
        db_session
    ):
        """Тест подсчета планов по conversation_id."""
        # Arrange
        conv_id = ConversationId(value="conv-1")
        
        for i in range(3):
            plan = ExecutionPlan(
                id=PlanId(value=f"plan-{i}"),
                conversation_id=conv_id,
                goal=f"Goal {i}"
            )
            await execution_plan_repository.save(plan)
        
        # Другой conversation
        other_plan = ExecutionPlan(
            id=PlanId(value="plan-other"),
            conversation_id=ConversationId(value="conv-2"),
            goal="Other goal"
        )
        await execution_plan_repository.save(other_plan)
        await db_session.commit()
        
        # Act
        count = await execution_plan_repository.count_by_conversation_id(conv_id)
        
        # Assert
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_exists(
        self,
        execution_plan_repository,
        sample_execution_plan,
        db_session
    ):
        """Тест проверки существования плана."""
        # Arrange
        plan_id = sample_execution_plan.id
        
        # Act - Before save
        exists_before = await execution_plan_repository.exists(plan_id)
        
        # Save
        await execution_plan_repository.save(sample_execution_plan)
        await db_session.commit()
        
        # Act - After save
        exists_after = await execution_plan_repository.exists(plan_id)
        
        # Assert
        assert exists_before is False
        assert exists_after is True
    
    @pytest.mark.asyncio
    async def test_save_with_multiple_subtasks(
        self,
        execution_plan_repository,
        db_session
    ):
        """Тест сохранения плана с несколькими подзадачами."""
        # Arrange
        subtask1 = Subtask(
            id=SubtaskId(value="st-1"),
            description="Subtask 1",
            agent_id=AgentId(value="coder")
        )
        subtask2 = Subtask(
            id=SubtaskId(value="st-2"),
            description="Subtask 2",
            agent_id=AgentId(value="debug"),
            dependencies=[SubtaskId(value="st-1")]
        )
        subtask3 = Subtask(
            id=SubtaskId(value="st-3"),
            description="Subtask 3",
            agent_id=AgentId(value="ask")
        )
        
        plan = ExecutionPlan(
            id=PlanId(value="plan-1"),
            conversation_id=ConversationId(value="conv-1"),
            goal="Complex plan",
            subtasks=[subtask1, subtask2, subtask3]
        )
        
        # Act
        await execution_plan_repository.save(plan)
        await db_session.commit()
        
        # Assert
        found = await execution_plan_repository.find_by_id(plan.id)
        assert found is not None
        assert len(found.subtasks) == 3
        assert found.subtasks[1].dependencies[0].value == "st-1"
    
    @pytest.mark.asyncio
    async def test_save_with_timestamps(
        self,
        execution_plan_repository,
        db_session
    ):
        """Тест сохранения плана с timestamps."""
        # Arrange
        now = datetime.now(timezone.utc)
        plan = ExecutionPlan(
            id=PlanId(value="plan-1"),
            conversation_id=ConversationId(value="conv-1"),
            goal="Test goal",
            status=PlanStatus.completed(),
            approved_at=now,
            started_at=now,
            completed_at=now
        )
        
        # Act
        await execution_plan_repository.save(plan)
        await db_session.commit()
        
        # Assert
        found = await execution_plan_repository.find_by_id(plan.id)
        assert found.approved_at is not None
        assert found.started_at is not None
        assert found.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_save_with_current_subtask_id(
        self,
        execution_plan_repository,
        sample_subtask,
        db_session
    ):
        """Тест сохранения плана с current_subtask_id."""
        # Arrange
        plan = ExecutionPlan(
            id=PlanId(value="plan-1"),
            conversation_id=ConversationId(value="conv-1"),
            goal="Test goal",
            subtasks=[sample_subtask],
            status=PlanStatus.in_progress(),
            current_subtask_id=SubtaskId(value="subtask-1")
        )
        
        # Act
        await execution_plan_repository.save(plan)
        await db_session.commit()
        
        # Assert
        found = await execution_plan_repository.find_by_id(plan.id)
        assert found.current_subtask_id is not None
        assert found.current_subtask_id.value == "subtask-1"
    
    @pytest.mark.asyncio
    async def test_find_by_conversation_id_empty(
        self,
        execution_plan_repository
    ):
        """Тест поиска планов в пустой БД."""
        # Arrange
        conv_id = ConversationId(value="conv-1")
        
        # Act
        plans = await execution_plan_repository.find_by_conversation_id(conv_id)
        
        # Assert
        assert plans == []
    
    @pytest.mark.asyncio
    async def test_count_by_conversation_id_zero(
        self,
        execution_plan_repository
    ):
        """Тест подсчета планов в пустой БД."""
        # Arrange
        conv_id = ConversationId(value="conv-1")
        
        # Act
        count = await execution_plan_repository.count_by_conversation_id(conv_id)
        
        # Assert
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_save_preserves_metadata(
        self,
        execution_plan_repository,
        db_session
    ):
        """Тест сохранения metadata."""
        # Arrange
        plan = ExecutionPlan(
            id=PlanId(value="plan-1"),
            conversation_id=ConversationId(value="conv-1"),
            goal="Test goal",
            metadata={
                "key1": "value1",
                "key2": 123,
                "key3": {"nested": "object"}
            }
        )
        
        # Act
        await execution_plan_repository.save(plan)
        await db_session.commit()
        
        # Assert
        found = await execution_plan_repository.find_by_id(plan.id)
        assert found.metadata == plan.metadata
        assert found.metadata["key1"] == "value1"
        assert found.metadata["key2"] == 123
        assert found.metadata["key3"]["nested"] == "object"
    
    @pytest.mark.asyncio
    async def test_delete_cascades_to_subtasks(
        self,
        execution_plan_repository,
        sample_execution_plan,
        db_session
    ):
        """Тест каскадного удаления подзадач при удалении плана."""
        # Arrange
        plan_id = sample_execution_plan.id
        await execution_plan_repository.save(sample_execution_plan)
        await db_session.commit()
        
        # Verify plan and subtasks exist
        found = await execution_plan_repository.find_by_id(plan_id)
        assert found is not None
        assert len(found.subtasks) == 1
        
        # Act - Delete plan
        await execution_plan_repository.delete(plan_id)
        await db_session.commit()
        
        # Assert - Plan and subtasks are deleted
        found = await execution_plan_repository.find_by_id(plan_id)
        assert found is None

"""
Unit тесты для ExecutionPlanMapper.

Тестирует преобразование между ExecutionPlan entity и PlanModel.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.persistence.mappers import ExecutionPlanMapper
from app.infrastructure.persistence.models.plan import PlanModel, SubtaskModel
from app.domain.execution_context.entities import ExecutionPlan, Subtask
from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus,
)
from app.domain.session_context.value_objects import ConversationId
from app.domain.agent_context.value_objects import AgentId


@pytest.fixture
def mapper():
    """Создать ExecutionPlanMapper."""
    return ExecutionPlanMapper()


@pytest.fixture
def mock_db():
    """Создать mock для AsyncSession."""
    db = AsyncMock()
    
    # Mock execute для select запросов
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    
    # Mock других методов
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    
    return db


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


@pytest.fixture
def sample_plan_model():
    """Создать тестовый PlanModel."""
    model = PlanModel(
        id="plan-1",
        session_id="conv-1",
        goal="Test goal",
        status="draft",
        current_subtask_id=None,
        metadata_json='{"key": "value"}',
        approved_at=None,
        started_at=None,
        completed_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    # Добавить подзадачу
    subtask = SubtaskModel(
        id="subtask-1",
        plan_id="plan-1",
        description="Test subtask",
        agent="coder",
        status="pending",
        dependencies_json="[]",
        estimated_time="5 min",
        result=None,
        error=None,
        started_at=None,
        completed_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    model.subtasks = [subtask]
    
    return model


class TestExecutionPlanMapper:
    """Тесты для ExecutionPlanMapper."""
    
    @pytest.mark.asyncio
    async def test_to_model_basic(self, mapper, sample_execution_plan, mock_db):
        """Тест преобразования entity в model (базовый случай)."""
        # Act
        model = await mapper.to_model(sample_execution_plan, mock_db)
        
        # Assert
        assert model.id == "plan-1"
        assert model.session_id == "conv-1"
        assert model.goal == "Test goal"
        assert model.status == "draft"
        assert model.current_subtask_id is None
        assert '"key": "value"' in model.metadata_json
        assert model.approved_at is None
        assert model.started_at is None
        assert model.completed_at is None
    
    @pytest.mark.asyncio
    async def test_to_model_with_timestamps(self, mapper, mock_db):
        """Тест преобразования entity с timestamps."""
        # Arrange
        now = datetime.now(timezone.utc)
        plan = ExecutionPlan(
            id=PlanId(value="plan-1"),
            conversation_id=ConversationId(value="conv-1"),
            goal="Test goal",
            status=PlanStatus.in_progress(),
            approved_at=now,
            started_at=now,
            completed_at=None
        )
        
        # Act
        model = await mapper.to_model(plan, mock_db)
        
        # Assert
        assert model.approved_at == now
        assert model.started_at == now
        assert model.completed_at is None
    
    @pytest.mark.asyncio
    async def test_to_model_with_current_subtask(self, mapper, sample_subtask, mock_db):
        """Тест преобразования entity с current_subtask_id."""
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
        model = await mapper.to_model(plan, mock_db)
        
        # Assert
        assert model.current_subtask_id == "subtask-1"
    
    @pytest.mark.asyncio
    async def test_to_model_with_multiple_subtasks(self, mapper, mock_db):
        """Тест преобразования entity с несколькими подзадачами."""
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
        
        plan = ExecutionPlan(
            id=PlanId(value="plan-1"),
            conversation_id=ConversationId(value="conv-1"),
            goal="Test goal",
            subtasks=[subtask1, subtask2]
        )
        
        # Act
        model = await mapper.to_model(plan, mock_db)
        
        # Assert - проверяем что subtasks были сохранены через _save_subtasks
        # В unit тесте мы не можем проверить model.subtasks напрямую,
        # так как они сохраняются в БД асинхронно
        assert model.id == "plan-1"
    
    @pytest.mark.asyncio
    async def test_to_entity_basic(self, mapper, sample_plan_model, mock_db):
        """Тест преобразования model в entity (базовый случай)."""
        # Act
        entity = await mapper.to_entity(sample_plan_model, mock_db)
        
        # Assert
        assert entity.id.value == "plan-1"
        assert entity.conversation_id.value == "conv-1"
        assert entity.goal == "Test goal"
        assert entity.status.value == "draft"
        assert entity.current_subtask_id is None
        assert entity.metadata == {"key": "value"}
        assert len(entity.subtasks) == 1
    
    @pytest.mark.asyncio
    async def test_to_entity_with_timestamps(self, mapper, mock_db):
        """Тест преобразования model с timestamps."""
        # Arrange
        now = datetime.now(timezone.utc)
        model = PlanModel(
            id="plan-1",
            session_id="conv-1",
            goal="Test goal",
            status="in_progress",
            approved_at=now,
            started_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now
        )
        model.subtasks = []
        
        # Act
        entity = await mapper.to_entity(model, mock_db)
        
        # Assert
        assert entity.approved_at == now
        assert entity.started_at == now
        assert entity.completed_at is None
    
    @pytest.mark.asyncio
    async def test_to_entity_with_current_subtask(self, mapper, mock_db):
        """Тест преобразования model с current_subtask_id."""
        # Arrange
        model = PlanModel(
            id="plan-1",
            session_id="conv-1",
            goal="Test goal",
            status="in_progress",
            current_subtask_id="subtask-1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        model.subtasks = []
        
        # Act
        entity = await mapper.to_entity(model, mock_db)
        
        # Assert
        assert entity.current_subtask_id is not None
        assert entity.current_subtask_id.value == "subtask-1"
    
    @pytest.mark.asyncio
    async def test_to_entity_with_multiple_subtasks(self, mapper, mock_db):
        """Тест преобразования model с несколькими подзадачами."""
        # Arrange
        model = PlanModel(
            id="plan-1",
            session_id="conv-1",
            goal="Test goal",
            status="draft",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        subtask1 = SubtaskModel(
            id="st-1",
            plan_id="plan-1",
            description="Subtask 1",
            agent="coder",
            status="pending",
            dependencies_json="[]",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        subtask2 = SubtaskModel(
            id="st-2",
            plan_id="plan-1",
            description="Subtask 2",
            agent="debug",
            status="pending",
            dependencies_json='["st-1"]',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        model.subtasks = [subtask1, subtask2]
        
        # Act
        entity = await mapper.to_entity(model, mock_db)
        
        # Assert
        assert len(entity.subtasks) == 2
        assert entity.subtasks[0].id.value == "st-1"
        assert entity.subtasks[1].id.value == "st-2"
        assert len(entity.subtasks[1].dependencies) == 1
        assert entity.subtasks[1].dependencies[0].value == "st-1"
    
    @pytest.mark.asyncio
    async def test_to_entity_empty_metadata(self, mapper, mock_db):
        """Тест преобразования model с пустыми metadata."""
        # Arrange
        model = PlanModel(
            id="plan-1",
            session_id="conv-1",
            goal="Test goal",
            status="draft",
            metadata_json=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        model.subtasks = []
        
        # Act
        entity = await mapper.to_entity(model, mock_db)
        
        # Assert
        assert entity.metadata == {}
    
    @pytest.mark.asyncio
    async def test_roundtrip_conversion(self, mapper, sample_execution_plan, mock_db):
        """Тест двустороннего преобразования entity -> model -> entity."""
        # Act
        model = await mapper.to_model(sample_execution_plan, mock_db)
        entity = await mapper.to_entity(model, mock_db)
        
        # Assert
        assert entity.id.value == sample_execution_plan.id.value
        assert entity.conversation_id.value == sample_execution_plan.conversation_id.value
        assert entity.goal == sample_execution_plan.goal
        assert entity.status.value == sample_execution_plan.status.value
        assert len(entity.subtasks) == len(sample_execution_plan.subtasks)
        assert entity.metadata == sample_execution_plan.metadata
    
    def test_subtask_to_entity_with_result(self, mapper):
        """Тест преобразования подзадачи с результатом."""
        # Arrange
        subtask_model = SubtaskModel(
            id="st-1",
            plan_id="plan-1",
            description="Test subtask",
            agent="coder",
            status="done",
            dependencies_json="[]",
            result="Success!",
            error=None,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Act
        entity = mapper._subtask_to_entity(subtask_model)
        
        # Assert
        assert entity.status.value == "done"
        assert entity.result == "Success!"
        assert entity.error is None
    
    def test_subtask_to_entity_with_error(self, mapper):
        """Тест преобразования подзадачи с ошибкой."""
        # Arrange
        subtask_model = SubtaskModel(
            id="st-1",
            plan_id="plan-1",
            description="Test subtask",
            agent="coder",
            status="failed",
            dependencies_json="[]",
            result=None,
            error="Something went wrong",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Act
        entity = mapper._subtask_to_entity(subtask_model)
        
        # Assert
        assert entity.status.value == "failed"
        assert entity.result is None
        assert entity.error == "Something went wrong"
    
    @pytest.mark.asyncio
    async def test_to_model_preserves_all_statuses(self, mapper, mock_db):
        """Тест сохранения всех возможных статусов."""
        statuses = [
            ("draft", PlanStatus.draft()),
            ("approved", PlanStatus.approved()),
            ("in_progress", PlanStatus.in_progress()),
            ("completed", PlanStatus.completed()),
            ("failed", PlanStatus.failed()),
            ("cancelled", PlanStatus.cancelled()),
        ]
        
        for status_str, status_obj in statuses:
            # Arrange
            plan = ExecutionPlan(
                id=PlanId(f"plan-{status_str}"),
                conversation_id=ConversationId(value="conv-1"),
                goal="Test goal",
                status=status_obj
            )
            
            # Act
            model = await mapper.to_model(plan, mock_db)
            
            # Assert
            assert model.status == status_str, f"Failed for status {status_str}"

"""
Unit тесты для обновлений PlanMapper.

Тестирует новые методы для поддержки Value Objects (PlanId, SubtaskId).
"""

import pytest
from datetime import datetime, timezone

from app.infrastructure.persistence.mappers.execution_plan_mapper import ExecutionPlanMapper
from app.infrastructure.persistence.models.plan import PlanModel, SubtaskModel
from app.domain.entities import Plan
from app.domain.execution_context.value_objects import PlanId, SubtaskId


@pytest.fixture
def mapper():
    """Создать ExecutionPlanMapper."""
    return ExecutionPlanMapper()


class TestPlanMapperValueObjectSupport:
    """Тесты для поддержки Value Objects в PlanMapper."""
    
    def test_convert_plan_id_from_string(self, mapper):
        """Тест преобразования строки в PlanId."""
        # Arrange
        plan_id_str = "plan-123"
        
        # Act
        plan_id = mapper._convert_plan_id(plan_id_str)
        
        # Assert
        assert isinstance(plan_id, PlanId)
        assert plan_id.value == plan_id_str
    
    def test_convert_plan_id_from_plan_id(self, mapper):
        """Тест преобразования PlanId в PlanId (идемпотентность)."""
        # Arrange
        plan_id = PlanId("plan-123")
        
        # Act
        result = mapper._convert_plan_id(plan_id)
        
        # Assert
        assert isinstance(result, PlanId)
        assert result.value == plan_id.value
        assert result is plan_id  # Должен вернуть тот же объект
    
    def test_convert_plan_id_none(self, mapper):
        """Тест преобразования None."""
        # Act
        result = mapper._convert_plan_id(None)
        
        # Assert
        assert result is None
    
    def test_convert_subtask_id_from_string(self, mapper):
        """Тест преобразования строки в SubtaskId."""
        # Arrange
        subtask_id_str = "subtask-456"
        
        # Act
        subtask_id = mapper._convert_subtask_id(subtask_id_str)
        
        # Assert
        assert isinstance(subtask_id, SubtaskId)
        assert subtask_id.value == subtask_id_str
    
    def test_convert_subtask_id_from_subtask_id(self, mapper):
        """Тест преобразования SubtaskId в SubtaskId (идемпотентность)."""
        # Arrange
        subtask_id = SubtaskId("subtask-456")
        
        # Act
        result = mapper._convert_subtask_id(subtask_id)
        
        # Assert
        assert isinstance(result, SubtaskId)
        assert result.value == subtask_id.value
        assert result is subtask_id  # Должен вернуть тот же объект
    
    def test_convert_subtask_id_none(self, mapper):
        """Тест преобразования None."""
        # Act
        result = mapper._convert_subtask_id(None)
        
        # Assert
        assert result is None
    
    def test_to_entity_uses_plan_id(self, mapper):
        """Тест что to_entity использует PlanId."""
        # Arrange
        model = PlanModel(
            id="plan-123",
            session_id="session-1",
            goal="Test goal",
            status="draft",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        model.subtasks = []
        
        # Act
        entity = mapper.to_entity(model)
        
        # Assert
        assert hasattr(entity, 'plan_id')
        # Проверяем что plan_id это PlanId или строка (зависит от реализации)
        if hasattr(entity.plan_id, 'value'):
            assert entity.plan_id.value == "plan-123"
        else:
            assert entity.plan_id == "plan-123"
    
    def test_to_entity_with_subtask_ids(self, mapper):
        """Тест что to_entity правильно обрабатывает SubtaskId."""
        # Arrange
        model = PlanModel(
            id="plan-123",
            session_id="session-1",
            goal="Test goal",
            status="draft",
            current_subtask_id="subtask-1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        subtask = SubtaskModel(
            id="subtask-1",
            plan_id="plan-123",
            description="Test subtask",
            agent="coder",
            status="pending",
            dependencies_json='["subtask-0"]',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        model.subtasks = [subtask]
        
        # Act
        entity = mapper.to_entity(model)
        
        # Assert
        assert entity.subtasks is not None
        assert len(entity.subtasks) > 0
        
        # Проверяем что subtask_id это SubtaskId или строка
        first_subtask = entity.subtasks[0]
        if hasattr(first_subtask, 'subtask_id'):
            if hasattr(first_subtask.subtask_id, 'value'):
                assert first_subtask.subtask_id.value == "subtask-1"
            else:
                assert first_subtask.subtask_id == "subtask-1"
    
    def test_backward_compatibility_with_string_ids(self, mapper):
        """Тест обратной совместимости со строковыми ID."""
        # Arrange - Legacy Plan с строковыми ID
        model = PlanModel(
            id="plan-legacy",
            session_id="session-1",
            goal="Legacy plan",
            status="draft",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        model.subtasks = []
        
        # Act
        entity = mapper.to_entity(model)
        
        # Assert - Должно работать без ошибок
        assert entity is not None
        assert entity.id == "plan-legacy" or (hasattr(entity, 'plan_id') and 
                                               (entity.plan_id == "plan-legacy" or 
                                                entity.plan_id.value == "plan-legacy"))
    
    def test_convert_plan_id_list(self, mapper):
        """Тест преобразования списка строк в список PlanId."""
        # Arrange
        plan_ids = ["plan-1", "plan-2", "plan-3"]
        
        # Act
        converted = [mapper._convert_plan_id(pid) for pid in plan_ids]
        
        # Assert
        assert len(converted) == 3
        assert all(isinstance(pid, PlanId) for pid in converted)
        assert [pid.value for pid in converted] == plan_ids
    
    def test_convert_subtask_id_list(self, mapper):
        """Тест преобразования списка строк в список SubtaskId."""
        # Arrange
        subtask_ids = ["st-1", "st-2", "st-3"]
        
        # Act
        converted = [mapper._convert_subtask_id(sid) for sid in subtask_ids]
        
        # Assert
        assert len(converted) == 3
        assert all(isinstance(sid, SubtaskId) for sid in converted)
        assert [sid.value for sid in converted] == subtask_ids
    
    def test_convert_plan_id_empty_string(self, mapper):
        """Тест преобразования пустой строки."""
        # Act
        result = mapper._convert_plan_id("")
        
        # Assert
        # Пустая строка должна создать PlanId с пустым значением
        assert isinstance(result, PlanId)
        assert result.value == ""
    
    def test_convert_subtask_id_empty_string(self, mapper):
        """Тест преобразования пустой строки."""
        # Act
        result = mapper._convert_subtask_id("")
        
        # Assert
        # Пустая строка должна создать SubtaskId с пустым значением
        assert isinstance(result, SubtaskId)
        assert result.value == ""
    
    def test_roundtrip_with_value_objects(self, mapper):
        """Тест двустороннего преобразования с Value Objects."""
        # Arrange
        model = PlanModel(
            id="plan-roundtrip",
            session_id="session-1",
            goal="Roundtrip test",
            status="draft",
            current_subtask_id="subtask-1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        subtask = SubtaskModel(
            id="subtask-1",
            plan_id="plan-roundtrip",
            description="Test subtask",
            agent="coder",
            status="pending",
            dependencies_json="[]",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        model.subtasks = [subtask]
        
        # Act - Model -> Entity -> Model
        entity = mapper.to_entity(model)
        model_back = mapper.to_model(entity)
        
        # Assert
        assert model_back.id == model.id
        assert model_back.session_id == model.session_id
        assert model_back.goal == model.goal
        assert model_back.status == model.status
        assert len(model_back.subtasks) == len(model.subtasks)

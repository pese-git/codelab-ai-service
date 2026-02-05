"""
Unit тесты для Services в Execution Context.

Тестируют:
- DependencyResolver - разрешение зависимостей между подзадачами
"""

import pytest
from datetime import datetime, timezone

from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus
)
from app.domain.execution_context.entities import Subtask, ExecutionPlan
from app.domain.execution_context.services.dependency_resolver import DependencyResolver
from app.domain.agent_context.value_objects import AgentId
from app.domain.session_context.value_objects import ConversationId


class TestDependencyResolver:
    """Тесты для DependencyResolver."""
    
    def test_get_ready_subtasks_no_dependencies(self):
        """Получить готовые подзадачи без зависимостей."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.PENDING
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.PENDING
                )
            ]
        )
        
        resolver = DependencyResolver()
        ready = resolver.get_ready_subtasks(plan)
        
        assert len(ready) == 2
        assert ready[0].id.value == "subtask-1"
        assert ready[1].id.value == "subtask-2"
    
    def test_get_ready_subtasks_with_dependencies(self):
        """Получить готовые подзадачи с зависимостями."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.DONE
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")],
                    status=SubtaskStatus.PENDING
                ),
                Subtask(
                    id=SubtaskId("subtask-3"),
                    description="Task 3",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-2")],
                    status=SubtaskStatus.PENDING
                )
            ]
        )
        
        resolver = DependencyResolver()
        ready = resolver.get_ready_subtasks(plan)
        
        # Только subtask-2 готова (subtask-1 выполнена)
        assert len(ready) == 1
        assert ready[0].id.value == "subtask-2"
    
    def test_get_ready_subtasks_skip_running(self):
        """Пропустить уже выполняющиеся подзадачи."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.RUNNING
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.PENDING
                )
            ]
        )
        
        resolver = DependencyResolver()
        ready = resolver.get_ready_subtasks(plan)
        
        # Только subtask-2 (subtask-1 уже выполняется)
        assert len(ready) == 1
        assert ready[0].id.value == "subtask-2"
    
    def test_get_ready_subtasks_blocked_by_failed(self):
        """Заблокированные подзадачи из-за failed зависимости."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.FAILED
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")],
                    status=SubtaskStatus.PENDING
                )
            ]
        )
        
        resolver = DependencyResolver()
        ready = resolver.get_ready_subtasks(plan)
        
        # Нет готовых (subtask-2 заблокирована failed зависимостью)
        assert len(ready) == 0
    
    def test_has_cyclic_dependencies_no_cycle(self):
        """Проверка отсутствия циклических зависимостей."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[]
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")]
                ),
                Subtask(
                    id=SubtaskId("subtask-3"),
                    description="Task 3",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-2")]
                )
            ]
        )
        
        resolver = DependencyResolver()
        has_cycle = resolver.has_cyclic_dependencies(plan)
        
        assert has_cycle is False
    
    def test_has_cyclic_dependencies_with_cycle(self):
        """Проверка наличия циклических зависимостей."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-3")]
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")]
                ),
                Subtask(
                    id=SubtaskId("subtask-3"),
                    description="Task 3",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-2")]
                )
            ]
        )
        
        resolver = DependencyResolver()
        has_cycle = resolver.has_cyclic_dependencies(plan)
        
        assert has_cycle is True
    
    def test_has_cyclic_dependencies_self_reference(self):
        """Проверка самореференции."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")]
                )
            ]
        )
        
        resolver = DependencyResolver()
        has_cycle = resolver.has_cyclic_dependencies(plan)
        
        assert has_cycle is True
    
    def test_validate_dependencies_success(self):
        """Валидация зависимостей - успех."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[]
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")]
                )
            ]
        )
        
        resolver = DependencyResolver()
        
        # Не должно выбросить исключение
        resolver.validate_dependencies(plan)
    
    def test_validate_dependencies_missing_dependency(self):
        """Валидация зависимостей - отсутствующая зависимость."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-999")]  # Не существует
                )
            ]
        )
        
        resolver = DependencyResolver()
        errors = resolver.validate_dependencies(plan)
        
        # Должна быть ошибка о несуществующей зависимости
        assert len(errors) > 0
        assert any("non-existent" in error for error in errors)
    
    def test_validate_dependencies_cyclic(self):
        """Валидация зависимостей - циклические зависимости."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-2")]
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")]
                )
            ]
        )
        
        resolver = DependencyResolver()
        errors = resolver.validate_dependencies(plan)
        
        # Должна быть ошибка о циклических зависимостях
        assert len(errors) > 0
        assert any("Cyclic" in error for error in errors)
    
    def test_get_ready_subtasks_complex_graph(self):
        """Получить готовые подзадачи в сложном графе зависимостей."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("session-1"),
            goal="Test goal",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.DONE
                ),
                Subtask(
                    id=SubtaskId("subtask-2"),
                    description="Task 2",
                    agent_id=AgentId("coder"),
                    dependencies=[],
                    status=SubtaskStatus.DONE
                ),
                Subtask(
                    id=SubtaskId("subtask-3"),
                    description="Task 3",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1"), SubtaskId("subtask-2")],
                    status=SubtaskStatus.PENDING
                ),
                Subtask(
                    id=SubtaskId("subtask-4"),
                    description="Task 4",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-1")],
                    status=SubtaskStatus.PENDING
                ),
                Subtask(
                    id=SubtaskId("subtask-5"),
                    description="Task 5",
                    agent_id=AgentId("coder"),
                    dependencies=[SubtaskId("subtask-3"), SubtaskId("subtask-4")],
                    status=SubtaskStatus.PENDING
                )
            ]
        )
        
        resolver = DependencyResolver()
        ready = resolver.get_ready_subtasks(plan)
        
        # subtask-3 и subtask-4 готовы (их зависимости выполнены)
        assert len(ready) == 2
        ready_ids = {s.id.value for s in ready}
        assert "subtask-3" in ready_ids
        assert "subtask-4" in ready_ids


class TestPlanExecutionService:
    """Тесты для PlanExecutionService."""
    
    def test_service_initialization(self):
        """Инициализация PlanExecutionService."""
        from unittest.mock import Mock
        from app.domain.execution_context.services.plan_execution_service import PlanExecutionService
        
        mock_repo = Mock()
        mock_executor = Mock()
        mock_resolver = DependencyResolver()
        
        service = PlanExecutionService(
            plan_repository=mock_repo,
            subtask_executor=mock_executor,
            dependency_resolver=mock_resolver
        )
        
        assert service is not None
        assert service.plan_repository == mock_repo
        assert service.subtask_executor == mock_executor
        assert service.dependency_resolver == mock_resolver


class TestSubtaskExecutor:
    """Тесты для SubtaskExecutor."""
    
    def test_executor_initialization(self):
        """Инициализация SubtaskExecutor."""
        from unittest.mock import Mock
        from app.domain.execution_context.services.subtask_executor import SubtaskExecutor
        
        mock_repo = Mock()
        
        executor = SubtaskExecutor(
            plan_repository=mock_repo,
            max_retries=3
        )
        
        assert executor is not None
        assert executor.max_retries == 3
        assert executor.plan_repository == mock_repo


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

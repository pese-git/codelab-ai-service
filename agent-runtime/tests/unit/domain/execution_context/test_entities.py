"""
Unit тесты для Entities в Execution Context.

Тестируют:
- Создание и валидацию Entities
- Бизнес-логику (start, complete, fail)
- Управление зависимостями
- Генерацию Domain Events
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
from app.domain.agent_context.value_objects import AgentId
from app.domain.session_context.value_objects import ConversationId


class TestSubtask:
    """Тесты для Subtask Entity."""
    
    def test_create_subtask(self):
        """Создание подзадачи."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        assert subtask.id.value == "subtask-1"
        assert subtask.description == "Test subtask"
        assert subtask.agent_id == AgentId("coder")
        assert subtask.status == SubtaskStatus.PENDING
        assert subtask.dependencies == []
        assert subtask.result is None
        assert subtask.error is None
    
    def test_start_subtask(self):
        """Запуск подзадачи."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask.start()
        
        assert subtask.status == SubtaskStatus.RUNNING
        assert subtask.started_at is not None
        assert subtask.completed_at is None
    
    def test_complete_subtask(self):
        """Завершение подзадачи."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask.start()
        subtask.complete(result="Task completed successfully")
        
        assert subtask.status == SubtaskStatus.DONE
        assert subtask.result == "Task completed successfully"
        assert subtask.completed_at is not None
        assert subtask.error is None
    
    def test_fail_subtask(self):
        """Провал подзадачи."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask.start()
        subtask.fail(error="Something went wrong")
        
        assert subtask.status == SubtaskStatus.FAILED
        assert subtask.error == "Something went wrong"
        assert subtask.completed_at is not None
        assert subtask.result is None
    
    def test_reset_to_pending(self):
        """Сброс подзадачи в PENDING (для retry)."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask.start()
        subtask.fail(error="Error")
        subtask.reset_to_pending()
        
        assert subtask.status == SubtaskStatus.PENDING
        assert subtask.error is None
        assert subtask.started_at is None
        assert subtask.completed_at is None
    
    def test_cannot_start_already_started_subtask(self):
        """Нельзя запустить уже запущенную подзадачу."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask.start()
        
        with pytest.raises(ValueError, match="Cannot transition"):
            subtask.start()
    
    def test_cannot_complete_pending_subtask(self):
        """Нельзя завершить подзадачу в статусе PENDING."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        with pytest.raises(ValueError, match="Cannot transition"):
            subtask.complete(result="Result")
    
    def test_subtask_with_dependencies(self):
        """Подзадача с зависимостями."""
        dep1 = SubtaskId("subtask-dep-1")
        dep2 = SubtaskId("subtask-dep-2")
        
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[dep1, dep2],
            metadata={}
        )
        
        assert len(subtask.dependencies) == 2
        assert dep1 in subtask.dependencies
        assert dep2 in subtask.dependencies


class TestExecutionPlan:
    """Тесты для ExecutionPlan Entity."""
    
    def test_create_execution_plan(self):
        """Создание плана выполнения."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[],
            metadata={}
        )
        
        assert plan.id.value == "plan-1"
        assert plan.goal == "Complete the project"
        assert plan.status == PlanStatus.DRAFT
        assert len(plan.subtasks) == 0
        assert plan.error is None
    
    def test_start_plan(self):
        """Запуск плана."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder")
                )
            ],
            metadata={}
        )
        
        plan.approve()  # Сначала нужно утвердить
        plan.start_execution()
        
        assert plan.status == PlanStatus.IN_PROGRESS
        assert plan.started_at is not None
        assert plan.completed_at is None
    
    def test_complete_plan(self):
        """Завершение плана."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[
                Subtask(
                    id=SubtaskId("subtask-1"),
                    description="Task 1",
                    agent_id=AgentId("coder")
                )
            ],
            metadata={}
        )
        
        plan.approve()
        plan.start_execution()
        plan.complete()
        
        assert plan.status == PlanStatus.COMPLETED
        assert plan.completed_at is not None
        assert plan.error is None
    
    def test_fail_plan(self):
        """Провал плана."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[],
            metadata={}
        )
        
        plan.start_execution()
        plan.fail(error="Plan execution failed")
        
        assert plan.status == PlanStatus.FAILED
        assert plan.error == "Plan execution failed"
        assert plan.completed_at is not None
    
    def test_cancel_plan(self):
        """Отмена плана."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[],
            metadata={}
        )
        
        plan.start_execution()
        plan.cancel()
        
        assert plan.status == PlanStatus.CANCELLED
        assert plan.completed_at is not None
    
    def test_add_subtask(self):
        """Добавление подзадачи в план."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[],
            metadata={}
        )
        
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        plan.add_subtask(subtask)
        
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].id.value == "subtask-1"
    
    def test_get_subtask_by_id(self):
        """Получение подзадачи по ID."""
        subtask1 = Subtask(
            id=SubtaskId("subtask-1"),
            description="Test subtask 1",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask2 = Subtask(
            id=SubtaskId("subtask-2"),
            description="Test subtask 2",
            agent_id=AgentId("architect"),
            dependencies=[],
            metadata={}
        )
        
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[subtask1, subtask2],
            metadata={}
        )
        
        found = plan.get_subtask_by_id(SubtaskId("subtask-2"))
        
        assert found is not None
        assert found.id.value == "subtask-2"
        assert found.agent_id == AgentId("architect")
    
    def test_get_subtask_by_id_not_found(self):
        """Получение несуществующей подзадачи возвращает None."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[],
            metadata={}
        )
        
        found = plan.get_subtask_by_id(SubtaskId("nonexistent"))
        
        assert found is None
    
    def test_plan_with_multiple_subtasks(self):
        """План с несколькими подзадачами."""
        subtask1 = Subtask(
            id=SubtaskId("subtask-1"),
            description="Task 1",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask2 = Subtask(
            id=SubtaskId("subtask-2"),
            description="Task 2",
            agent_id=AgentId("architect"),
            dependencies=[SubtaskId("subtask-1")],
            metadata={}
        )
        
        subtask3 = Subtask(
            id=SubtaskId("subtask-3"),
            description="Task 3",
            agent_id=AgentId("coder"),
            dependencies=[SubtaskId("subtask-2")],
            metadata={}
        )
        
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[subtask1, subtask2, subtask3],
            metadata={}
        )
        
        assert len(plan.subtasks) == 3
        assert plan.subtasks[1].dependencies[0].value == "subtask-1"
        assert plan.subtasks[2].dependencies[0].value == "subtask-2"
    
    def test_domain_events_are_collected(self):
        """Domain Events собираются в плане."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[],
            metadata={}
        )
        
        # Изначально нет событий
        assert len(plan.domain_events) == 0
        
        # После операций события должны добавляться
        # (это будет делаться в сервисах)
        from app.domain.execution_context.events import PlanStarted
        
        event = PlanStarted(
            plan_id=plan.id,
            goal=plan.goal,
            subtask_count=0,
            started_at=datetime.now(timezone.utc)
        )
        
        plan.add_domain_event(event)
        
        assert len(plan.domain_events) == 1
        assert isinstance(plan.domain_events[0], PlanStarted)
    
    def test_clear_domain_events(self):
        """Очистка Domain Events."""
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[],
            metadata={}
        )
        
        from app.domain.execution_context.events import PlanStarted
        
        event = PlanStarted(
            plan_id=plan.id,
            goal=plan.goal,
            subtask_count=0,
            started_at=datetime.now(timezone.utc)
        )
        
        plan.add_domain_event(event)
        assert len(plan.domain_events) == 1
        
        plan.clear_domain_events()
        assert len(plan.domain_events) == 0


class TestExecutionPlanLifecycle:
    """Интеграционные тесты для жизненного цикла плана."""
    
    def test_complete_plan_lifecycle(self):
        """Полный жизненный цикл плана."""
        # Создать план с подзадачами
        subtask1 = Subtask(
            id=SubtaskId("subtask-1"),
            description="Task 1",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        subtask2 = Subtask(
            id=SubtaskId("subtask-2"),
            description="Task 2",
            agent_id=AgentId("coder"),
            dependencies=[SubtaskId("subtask-1")],
            metadata={}
        )
        
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[subtask1, subtask2],
            metadata={}
        )
        
        # Запустить план
        plan.start_execution()
        assert plan.status == PlanStatus.IN_PROGRESS
        
        # Выполнить первую подзадачу
        subtask1.start()
        subtask1.complete(result="Task 1 done")
        assert subtask1.status == SubtaskStatus.DONE
        
        # Выполнить вторую подзадачу
        subtask2.start()
        subtask2.complete(result="Task 2 done")
        assert subtask2.status == SubtaskStatus.DONE
        
        # Завершить план
        plan.complete()
        assert plan.status == PlanStatus.COMPLETED
        
        # Проверить, что все подзадачи выполнены
        assert all(st.status == SubtaskStatus.DONE for st in plan.subtasks)
    
    def test_plan_lifecycle_with_subtask_failure(self):
        """Жизненный цикл плана с провалом подзадачи."""
        subtask = Subtask(
            id=SubtaskId("subtask-1"),
            description="Task 1",
            agent_id=AgentId("coder"),
            dependencies=[],
            metadata={}
        )
        
        plan = ExecutionPlan(
            id=PlanId("plan-1"),
            conversation_id=ConversationId("test-session"),
            goal="Complete the project",
            subtasks=[subtask],
            metadata={}
        )
        
        # Запустить план
        plan.start_execution()
        
        # Запустить подзадачу
        subtask.start()
        
        # Подзадача провалилась
        subtask.fail(error="Task failed")
        assert subtask.status == SubtaskStatus.FAILED
        
        # План тоже провалился
        plan.fail(error="Subtask failed")
        assert plan.status == PlanStatus.FAILED

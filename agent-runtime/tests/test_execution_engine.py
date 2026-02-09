"""
Unit тесты для ExecutionEngine.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from app.domain.services.execution_engine import (
    ExecutionEngine,
    ExecutionEngineError,
    ExecutionResult
)
from app.domain.execution_context.entities.execution_plan import ExecutionPlan as Plan
from app.domain.execution_context.entities.subtask import Subtask
from app.domain.execution_context.value_objects import PlanStatus, SubtaskStatus
from app.domain.entities.agent_context import AgentType
from app.domain.services.dependency_resolver import DependencyResolver
from app.domain.services.subtask_executor import SubtaskExecutor


@pytest.fixture
def mock_plan_repository():
    """Mock репозитория планов"""
    return AsyncMock()


@pytest.fixture
def mock_subtask_executor():
    """Mock исполнителя подзадач"""
    return AsyncMock(spec=SubtaskExecutor)


@pytest.fixture
def dependency_resolver():
    """Реальный dependency resolver"""
    return DependencyResolver()


@pytest.fixture
def mock_session_service():
    """Mock сервиса сессий"""
    return AsyncMock()


@pytest.fixture
def mock_stream_handler():
    """Mock stream handler"""
    return MagicMock()


@pytest.fixture
def mock_approval_manager():
    """Mock approval manager"""
    return AsyncMock()


@pytest.fixture
def execution_engine(
    mock_plan_repository,
    mock_subtask_executor,
    dependency_resolver,
    mock_approval_manager
):
    """Создать ExecutionEngine"""
    return ExecutionEngine(
        plan_repository=mock_plan_repository,
        subtask_executor=mock_subtask_executor,
        dependency_resolver=dependency_resolver,
        approval_manager=mock_approval_manager,
        max_parallel_tasks=2
    )


@pytest.fixture
def simple_plan():
    """Создать простой план без зависимостей"""
    plan = Plan(
        id=str(uuid.uuid4()),
        session_id="test-session",
        goal="Simple test plan"
    )
    
    subtask1 = Subtask(
        id=str(uuid.uuid4()),
        description="Task 1",
        agent=AgentType.CODER,
        dependencies=[]
    )
    subtask2 = Subtask(
        id=str(uuid.uuid4()),
        description="Task 2",
        agent=AgentType.DEBUG,
        dependencies=[]
    )
    
    plan.add_subtask(subtask1)
    plan.add_subtask(subtask2)
    plan.approve()
    
    return plan


@pytest.fixture
def complex_plan():
    """Создать план с зависимостями"""
    plan = Plan(
        id=str(uuid.uuid4()),
        session_id="test-session",
        goal="Complex test plan"
    )
    
    # Task 1 (no dependencies)
    subtask1 = Subtask(
        id=str(uuid.uuid4()),
        description="Task 1",
        agent=AgentType.CODER,
        dependencies=[]
    )
    
    # Task 2 (no dependencies)
    subtask2 = Subtask(
        id=str(uuid.uuid4()),
        description="Task 2",
        agent=AgentType.CODER,
        dependencies=[]
    )
    
    # Task 3 (depends on 1 and 2)
    subtask3 = Subtask(
        id=str(uuid.uuid4()),
        description="Task 3",
        agent=AgentType.DEBUG,
        dependencies=[subtask1.id, subtask2.id]
    )
    
    plan.add_subtask(subtask1)
    plan.add_subtask(subtask2)
    plan.add_subtask(subtask3)
    plan.approve()
    
    return plan


class TestExecutionEngineInit:
    """Тесты инициализации ExecutionEngine"""
    
    def test_init_default_params(
        self,
        mock_plan_repository,
        mock_subtask_executor,
        dependency_resolver,
        mock_approval_manager
    ):
        """Тест инициализации с параметрами по умолчанию"""
        engine = ExecutionEngine(
            plan_repository=mock_plan_repository,
            subtask_executor=mock_subtask_executor,
            dependency_resolver=dependency_resolver,
            approval_manager=mock_approval_manager
        )
        
        assert engine.plan_repository == mock_plan_repository
        assert engine.subtask_executor == mock_subtask_executor
        assert engine.dependency_resolver == dependency_resolver
        assert engine.approval_manager == mock_approval_manager
        assert engine.max_parallel_tasks == 3
    
    def test_init_custom_parallel_tasks(
        self,
        mock_plan_repository,
        mock_subtask_executor,
        dependency_resolver,
        mock_approval_manager
    ):
        """Тест инициализации с кастомным количеством параллельных задач"""
        engine = ExecutionEngine(
            plan_repository=mock_plan_repository,
            subtask_executor=mock_subtask_executor,
            dependency_resolver=dependency_resolver,
            approval_manager=mock_approval_manager,
            max_parallel_tasks=5
        )
        
        assert engine.max_parallel_tasks == 5


class TestExecutionResult:
    """Тесты ExecutionResult"""
    
    def test_execution_result_to_dict(self):
        """Тест преобразования результата в словарь"""
        result = ExecutionResult(
            plan_id="plan-123",
            status="completed",
            completed_subtasks=3,
            failed_subtasks=0,
            total_subtasks=3,
            results={"task1": {"status": "done"}},
            errors={},
            duration_seconds=10.5
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["plan_id"] == "plan-123"
        assert result_dict["status"] == "completed"
        assert result_dict["completed_subtasks"] == 3
        assert result_dict["failed_subtasks"] == 0
        assert result_dict["total_subtasks"] == 3
        assert result_dict["success_rate"] == 100.0
        assert result_dict["duration_seconds"] == 10.5


class TestGetExecutionOrder:
    """Тесты получения порядка выполнения"""
    
    def test_get_execution_order_no_dependencies(
        self,
        execution_engine,
        simple_plan
    ):
        """Тест порядка выполнения без зависимостей"""
        batches = execution_engine._get_execution_order(simple_plan)
        
        # Все задачи могут выполняться параллельно
        assert len(batches) == 1
        assert len(batches[0]) == 2
    
    def test_get_execution_order_with_dependencies(
        self,
        execution_engine,
        complex_plan
    ):
        """Тест порядка выполнения с зависимостями"""
        batches = execution_engine._get_execution_order(complex_plan)
        
        # Должно быть 2 батча: [task1, task2], [task3]
        assert len(batches) == 2
        assert len(batches[0]) == 2  # task1 и task2 параллельно
        assert len(batches[1]) == 1  # task3 после них
    
    def test_get_execution_order_respects_max_parallel(
        self,
        execution_engine,
        simple_plan
    ):
        """Тест что порядок учитывает max_parallel_tasks"""
        # Добавить еще задачи
        for i in range(3):
            subtask = Subtask(
                id=str(uuid.uuid4()),
                description=f"Task {i+3}",
                agent=AgentType.CODER,
                dependencies=[]
            )
            simple_plan.subtasks.append(subtask)
        
        batches = execution_engine._get_execution_order(simple_plan)
        
        # max_parallel_tasks = 2, всего 5 задач
        # Должно быть 3 батча: [2, 2, 1]
        assert len(batches) == 3
        assert len(batches[0]) <= 2
        assert len(batches[1]) <= 2
    
    def test_get_execution_order_circular_dependencies(
        self,
        execution_engine
    ):
        """Тест обнаружения циклических зависимостей"""
        plan = Plan(
            id=str(uuid.uuid4()),
            session_id="test-session",
            goal="Circular plan"
        )
        
        subtask1 = Subtask(
            id="task1",
            description="Task 1",
            agent=AgentType.CODER,
            dependencies=["task2"]
        )
        subtask2 = Subtask(
            id="task2",
            description="Task 2",
            agent=AgentType.CODER,
            dependencies=["task1"]
        )
        
        plan.subtasks = [subtask1, subtask2]
        plan.approve()
        
        with pytest.raises(ExecutionEngineError, match="circular dependencies"):
            execution_engine._get_execution_order(plan)


class TestExecutePlan:
    """Тесты выполнения плана"""
    
    @pytest.mark.asyncio
    async def test_execute_plan_success(
        self,
        execution_engine,
        mock_plan_repository,
        mock_subtask_executor,
        mock_session_service,
        mock_stream_handler,
        simple_plan
    ):
        """Тест успешного выполнения плана"""
        # Setup
        mock_plan_repository.find_by_id.return_value = simple_plan
        
        # Mock успешного выполнения подзадач - async generator
        async def mock_execute(*args, **kwargs):
            from app.models.schemas import StreamChunk
            yield StreamChunk(type="subtask_completed", content="Done", is_final=True)
        
        mock_subtask_executor.execute_subtask.side_effect = mock_execute
        
        # Execute - собрать chunks
        chunks = []
        async for chunk in execution_engine.execute_plan(
            plan_id=simple_plan.id,
            session_id="test-session",
            session_service=mock_session_service,
            stream_handler=mock_stream_handler
        ):
            chunks.append(chunk)
        
        # Assert - проверить что получены chunks
        assert len(chunks) > 0
        # План должен быть обновлен
        assert mock_plan_repository.save.called
    
    @pytest.mark.asyncio
    async def test_execute_plan_not_found(
        self,
        execution_engine,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler
    ):
        """Тест выполнения несуществующего плана"""
        # Setup
        mock_plan_repository.find_by_id.return_value = None
        
        # Execute & Assert
        with pytest.raises(ExecutionEngineError, match="not found"):
            async for _ in execution_engine.execute_plan(
                plan_id="non-existent",
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            ):
                pass
    
    @pytest.mark.asyncio
    async def test_execute_plan_not_approved(
        self,
        execution_engine,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        simple_plan
    ):
        """Тест выполнения неутвержденного плана"""
        # Setup
        simple_plan.status = PlanStatus.DRAFT
        mock_plan_repository.find_by_id.return_value = simple_plan
        
        # Execute & Assert
        with pytest.raises(ExecutionEngineError, match="cannot be executed"):
            async for _ in execution_engine.execute_plan(
                plan_id=simple_plan.id,
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            ):
                pass
    
    @pytest.mark.asyncio
    async def test_execute_plan_partial_failure(
        self,
        execution_engine,
        mock_plan_repository,
        mock_subtask_executor,
        mock_session_service,
        mock_stream_handler,
        simple_plan
    ):
        """Тест выполнения плана с частичными ошибками"""
        # Setup
        mock_plan_repository.find_by_id.return_value = simple_plan
        
        # Mock: задача с ошибкой - async generator
        async def mock_execute_error(*args, **kwargs):
            from app.models.schemas import StreamChunk
            yield StreamChunk(type="error", error="Task failed", is_final=True)
        
        mock_subtask_executor.execute_subtask.side_effect = mock_execute_error
        
        # Execute - собрать chunks
        chunks = []
        async for chunk in execution_engine.execute_plan(
            plan_id=simple_plan.id,
            session_id="test-session",
            session_service=mock_session_service,
            stream_handler=mock_stream_handler
        ):
            chunks.append(chunk)
        
        # Assert - должен быть error chunk
        assert any(chunk.type == "error" for chunk in chunks)


class TestGetExecutionStatus:
    """Тесты получения статуса выполнения"""
    
    @pytest.mark.asyncio
    async def test_get_execution_status_success(
        self,
        execution_engine,
        mock_plan_repository,
        simple_plan
    ):
        """Тест успешного получения статуса"""
        # Setup
        simple_plan.start_execution()
        mock_plan_repository.find_by_id.return_value = simple_plan
        
        # Execute
        status = await execution_engine.get_execution_status(simple_plan.id)
        
        # Assert
        assert status["plan_id"] == simple_plan.id
        assert status["status"] == PlanStatus.IN_PROGRESS.value
        assert "progress" in status
        assert status["started_at"] is not None
    
    @pytest.mark.asyncio
    async def test_get_execution_status_not_found(
        self,
        execution_engine,
        mock_plan_repository
    ):
        """Тест получения статуса несуществующего плана"""
        # Setup
        mock_plan_repository.find_by_id.return_value = None
        
        # Execute & Assert
        with pytest.raises(ExecutionEngineError, match="not found"):
            await execution_engine.get_execution_status("non-existent")


class TestCancelExecution:
    """Тесты отмены выполнения"""
    
    @pytest.mark.asyncio
    async def test_cancel_execution_success(
        self,
        execution_engine,
        mock_plan_repository,
        simple_plan
    ):
        """Тест успешной отмены выполнения"""
        # Setup
        simple_plan.start_execution()
        mock_plan_repository.find_by_id.return_value = simple_plan
        
        # Execute
        result = await execution_engine.cancel_execution(
            plan_id=simple_plan.id,
            reason="User requested cancellation"
        )
        
        # Assert
        assert result["status"] == "cancelled"
        assert result["reason"] == "User requested cancellation"
        assert simple_plan.status == PlanStatus.CANCELLED
        assert mock_plan_repository.save.called
    
    @pytest.mark.asyncio
    async def test_cancel_execution_not_found(
        self,
        execution_engine,
        mock_plan_repository
    ):
        """Тест отмены несуществующего плана"""
        # Setup
        mock_plan_repository.find_by_id.return_value = None
        
        # Execute & Assert
        with pytest.raises(ExecutionEngineError, match="not found"):
            await execution_engine.cancel_execution(
                plan_id="non-existent",
                reason="Test"
            )
    
    @pytest.mark.asyncio
    async def test_cancel_execution_completed_plan(
        self,
        execution_engine,
        mock_plan_repository
    ):
        """Тест отмены завершенного плана"""
        # Setup - создать новый план и завершить его
        plan = Plan(
            id=str(uuid.uuid4()),
            session_id="test-session",
            goal="Test plan"
        )
        
        subtask1 = Subtask(
            id=str(uuid.uuid4()),
            description="Task 1",
            agent=AgentType.CODER,
            dependencies=[]
        )
        subtask2 = Subtask(
            id=str(uuid.uuid4()),
            description="Task 2",
            agent=AgentType.DEBUG,
            dependencies=[]
        )
        
        plan.add_subtask(subtask1)
        plan.add_subtask(subtask2)
        plan.approve()
        plan.start_execution()
        
        # Завершить подзадачи
        subtask1.start()
        subtask1.complete("Done")
        subtask2.start()
        subtask2.complete("Done")
        
        # Завершить план
        plan.complete()
        
        mock_plan_repository.find_by_id.return_value = plan
        
        # Execute & Assert
        with pytest.raises(ExecutionEngineError, match="Cannot cancel"):
            await execution_engine.cancel_execution(
                plan_id=plan.id,
                reason="Test"
            )



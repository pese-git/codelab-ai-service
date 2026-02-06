"""
Тесты для ExecutionEngineAdapter.

Проверяют корректность адаптации между legacy ExecutionEngine
и новым PlanExecutionService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.domain.adapters.execution_engine_adapter import (
    ExecutionEngineAdapter,
    ExecutionEngineError,
    ExecutionResult
)
from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus
)
from app.domain.execution_context.entities import ExecutionPlan, Subtask
from app.domain.agent_context.value_objects import AgentId
from app.domain.session_context.value_objects import ConversationId
from app.domain.execution_context.services.plan_execution_service import (
    PlanExecutionService,
    PlanExecutionError
)
from app.models.schemas import StreamChunk


@pytest.fixture
def mock_plan_execution_service():
    """Mock PlanExecutionService."""
    service = AsyncMock(spec=PlanExecutionService)
    return service


@pytest.fixture
def execution_engine_adapter(mock_plan_execution_service):
    """Создать ExecutionEngineAdapter с mock сервисом."""
    return ExecutionEngineAdapter(mock_plan_execution_service)


@pytest.fixture
def sample_plan():
    """Создать тестовый план."""
    plan_id = PlanId("test-plan-123")
    subtask1 = Subtask(
        id=SubtaskId("subtask-1"),
        description="Test subtask 1",
        agent_id=AgentId(value="code"),
        dependencies=[],
        status=SubtaskStatus.PENDING
    )
    subtask2 = Subtask(
        id=SubtaskId("subtask-2"),
        description="Test subtask 2",
        agent_id=AgentId(value="architect"),
        dependencies=[SubtaskId(value="subtask-1")],
        status=SubtaskStatus.PENDING
    )
    
    plan = ExecutionPlan(
        id=plan_id,
        conversation_id=ConversationId(value="conv-123"),
        goal="Test goal",
        subtasks=[subtask1, subtask2],
        status=PlanStatus.PENDING
    )
    return plan


class TestExecutionEngineAdapter:
    """Тесты для ExecutionEngineAdapter."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_plan_execution_service):
        """Тест инициализации адаптера."""
        adapter = ExecutionEngineAdapter(mock_plan_execution_service)
        
        assert adapter.plan_execution_service == mock_plan_execution_service
    
    @pytest.mark.asyncio
    async def test_execute_plan_success(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест успешного выполнения плана через адаптер."""
        plan_id = "test-plan-123"
        session_id = "session-456"
        
        # Mock chunks от PlanExecutionService
        chunks = [
            StreamChunk(
                type="status",
                content="Plan started",
                metadata={"plan_id": plan_id},
                is_final=False
            ),
            StreamChunk(
                type="status",
                content="Subtask 1 started",
                metadata={"subtask_id": "subtask-1"},
                is_final=False
            ),
            StreamChunk(
                type="execution_completed",
                content="Plan completed",
                metadata={"plan_id": plan_id},
                is_final=True
            )
        ]
        
        async def mock_generator():
            for chunk in chunks:
                yield chunk
        
        mock_plan_execution_service.start_plan_execution.return_value = mock_generator()
        
        # Выполнить через адаптер
        result_chunks = []
        async for chunk in execution_engine_adapter.execute_plan(
            plan_id=plan_id,
            session_id=session_id,
            session_service=MagicMock(),
            stream_handler=MagicMock()
        ):
            result_chunks.append(chunk)
        
        # Проверки
        assert len(result_chunks) == 3
        assert result_chunks[0].type == "status"
        assert result_chunks[1].type == "status"
        assert result_chunks[2].type == "execution_completed"
        
        # Проверить, что вызван с правильными параметрами
        mock_plan_execution_service.start_plan_execution.assert_called_once()
        call_args = mock_plan_execution_service.start_plan_execution.call_args
        assert call_args.kwargs["plan_id"].value == plan_id
        assert call_args.kwargs["session_id"] == session_id
    
    @pytest.mark.asyncio
    async def test_execute_plan_converts_plan_id(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест конвертации str -> PlanId."""
        plan_id = "test-plan-123"
        
        async def mock_generator():
            yield StreamChunk(type="status", content="test", is_final=True)
        
        mock_plan_execution_service.start_plan_execution.return_value = mock_generator()
        
        # Выполнить
        async for _ in execution_engine_adapter.execute_plan(
            plan_id=plan_id,
            session_id="session-456",
            session_service=MagicMock(),
            stream_handler=MagicMock()
        ):
            pass
        
        # Проверить, что PlanId создан корректно
        call_args = mock_plan_execution_service.start_plan_execution.call_args
        assert isinstance(call_args.kwargs["plan_id"], PlanId)
        assert call_args.kwargs["plan_id"].value == plan_id
    
    @pytest.mark.asyncio
    async def test_execute_plan_handles_plan_execution_error(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест обработки PlanExecutionError."""
        plan_id = "test-plan-123"
        error_message = "Plan not found"
        
        async def mock_generator():
            raise PlanExecutionError(error_message, plan_id=PlanId(plan_id))
            yield  # unreachable
        
        mock_plan_execution_service.start_plan_execution.return_value = mock_generator()
        
        # Проверить, что ошибка конвертируется в ExecutionEngineError
        with pytest.raises(ExecutionEngineError) as exc_info:
            async for _ in execution_engine_adapter.execute_plan(
                plan_id=plan_id,
                session_id="session-456",
                session_service=MagicMock(),
                stream_handler=MagicMock()
            ):
                pass
        
        assert error_message in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_plan_handles_unexpected_error(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест обработки неожиданных ошибок."""
        plan_id = "test-plan-123"
        
        async def mock_generator():
            raise ValueError("Unexpected error")
            yield  # unreachable
        
        mock_plan_execution_service.start_plan_execution.return_value = mock_generator()
        
        # Проверить, что ошибка оборачивается в ExecutionEngineError
        with pytest.raises(ExecutionEngineError) as exc_info:
            async for _ in execution_engine_adapter.execute_plan(
                plan_id=plan_id,
                session_id="session-456",
                session_service=MagicMock(),
                stream_handler=MagicMock()
            ):
                pass
        
        assert "Unexpected error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_execution_status_success(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест получения статуса выполнения."""
        plan_id = "test-plan-123"
        expected_status = {
            "plan_id": plan_id,
            "goal": "Test goal",
            "status": "in_progress",
            "subtask_stats": {
                "total": 2,
                "pending": 1,
                "in_progress": 1,
                "done": 0,
                "failed": 0
            }
        }
        
        mock_plan_execution_service.get_plan_status.return_value = expected_status
        
        # Получить статус
        status = await execution_engine_adapter.get_execution_status(plan_id)
        
        # Проверки
        assert status == expected_status
        mock_plan_execution_service.get_plan_status.assert_called_once()
        call_args = mock_plan_execution_service.get_plan_status.call_args
        assert call_args.args[0].value == plan_id
    
    @pytest.mark.asyncio
    async def test_get_execution_status_handles_error(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест обработки ошибки при получении статуса."""
        plan_id = "test-plan-123"
        
        mock_plan_execution_service.get_plan_status.side_effect = PlanExecutionError(
            "Plan not found",
            plan_id=PlanId(plan_id)
        )
        
        # Проверить, что ошибка конвертируется
        with pytest.raises(ExecutionEngineError) as exc_info:
            await execution_engine_adapter.get_execution_status(plan_id)
        
        assert "Plan not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_cancel_execution_success(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест отмены выполнения плана."""
        plan_id = "test-plan-123"
        reason = "User requested cancellation"
        
        mock_plan_execution_service.cancel_plan_execution.return_value = None
        
        # Отменить выполнение
        await execution_engine_adapter.cancel_execution(plan_id, reason)
        
        # Проверки
        mock_plan_execution_service.cancel_plan_execution.assert_called_once()
        call_args = mock_plan_execution_service.cancel_plan_execution.call_args
        assert call_args.kwargs["plan_id"].value == plan_id
        assert call_args.kwargs["reason"] == reason
    
    @pytest.mark.asyncio
    async def test_cancel_execution_default_reason(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест отмены с дефолтной причиной."""
        plan_id = "test-plan-123"
        
        mock_plan_execution_service.cancel_plan_execution.return_value = None
        
        # Отменить без указания причины
        await execution_engine_adapter.cancel_execution(plan_id)
        
        # Проверить дефолтную причину
        call_args = mock_plan_execution_service.cancel_plan_execution.call_args
        assert call_args.kwargs["reason"] == "User cancelled"
    
    @pytest.mark.asyncio
    async def test_cancel_execution_handles_error(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест обработки ошибки при отмене."""
        plan_id = "test-plan-123"
        
        mock_plan_execution_service.cancel_plan_execution.side_effect = PlanExecutionError(
            "Cannot cancel completed plan",
            plan_id=PlanId(plan_id)
        )
        
        # Проверить, что ошибка конвертируется
        with pytest.raises(ExecutionEngineError) as exc_info:
            await execution_engine_adapter.cancel_execution(plan_id)
        
        assert "Cannot cancel completed plan" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_next_executable_subtasks_success(
        self,
        execution_engine_adapter,
        mock_plan_execution_service,
        sample_plan
    ):
        """Тест получения следующих выполняемых подзадач."""
        plan_id = "test-plan-123"
        
        # Mock возвращает первую подзадачу
        mock_plan_execution_service.get_next_executable_subtasks.return_value = [
            sample_plan.subtasks[0]
        ]
        
        # Получить подзадачи
        subtasks = await execution_engine_adapter.get_next_executable_subtasks(plan_id)
        
        # Проверки
        assert len(subtasks) == 1
        assert subtasks[0].id.value == "subtask-1"
        
        mock_plan_execution_service.get_next_executable_subtasks.assert_called_once()
        call_args = mock_plan_execution_service.get_next_executable_subtasks.call_args
        assert call_args.args[0].value == plan_id
    
    @pytest.mark.asyncio
    async def test_get_next_executable_subtasks_handles_error(
        self,
        execution_engine_adapter,
        mock_plan_execution_service
    ):
        """Тест обработки ошибки при получении подзадач."""
        plan_id = "test-plan-123"
        
        mock_plan_execution_service.get_next_executable_subtasks.side_effect = PlanExecutionError(
            "Plan not found",
            plan_id=PlanId(plan_id)
        )
        
        # Проверить, что ошибка конвертируется
        with pytest.raises(ExecutionEngineError) as exc_info:
            await execution_engine_adapter.get_next_executable_subtasks(plan_id)
        
        assert "Plan not found" in str(exc_info.value)


class TestExecutionResult:
    """Тесты для ExecutionResult (legacy compatibility)."""
    
    def test_execution_result_initialization(self):
        """Тест инициализации ExecutionResult."""
        result = ExecutionResult(
            plan_id="plan-123",
            status="completed",
            completed_subtasks=2,
            failed_subtasks=0,
            total_subtasks=2,
            results={"subtask-1": "result1", "subtask-2": "result2"},
            errors={},
            duration_seconds=10.5
        )
        
        assert result.plan_id == "plan-123"
        assert result.status == "completed"
        assert result.completed_subtasks == 2
        assert result.failed_subtasks == 0
        assert result.total_subtasks == 2
        assert result.duration_seconds == 10.5
    
    def test_execution_result_to_dict(self):
        """Тест конвертации ExecutionResult в словарь."""
        result = ExecutionResult(
            plan_id="plan-123",
            status="completed",
            completed_subtasks=2,
            failed_subtasks=0,
            total_subtasks=2,
            results={"subtask-1": "result1"},
            errors={},
            duration_seconds=10.5
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["plan_id"] == "plan-123"
        assert result_dict["status"] == "completed"
        assert result_dict["completed_subtasks"] == 2
        assert result_dict["success_rate"] == 100.0
        assert result_dict["duration_seconds"] == 10.5
    
    def test_execution_result_success_rate_calculation(self):
        """Тест расчета success_rate."""
        # Полный успех
        result1 = ExecutionResult(
            plan_id="plan-1",
            status="completed",
            completed_subtasks=3,
            failed_subtasks=0,
            total_subtasks=3,
            results={},
            errors={}
        )
        assert result1.to_dict()["success_rate"] == 100.0
        
        # Частичный успех
        result2 = ExecutionResult(
            plan_id="plan-2",
            status="failed",
            completed_subtasks=2,
            failed_subtasks=1,
            total_subtasks=3,
            results={},
            errors={}
        )
        assert result2.to_dict()["success_rate"] == pytest.approx(66.67, rel=0.01)
        
        # Нет подзадач
        result3 = ExecutionResult(
            plan_id="plan-3",
            status="pending",
            completed_subtasks=0,
            failed_subtasks=0,
            total_subtasks=0,
            results={},
            errors={}
        )
        assert result3.to_dict()["success_rate"] == 0.0

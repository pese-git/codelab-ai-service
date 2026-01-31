"""
Unit тесты для SubtaskExecutor.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

from app.domain.services.subtask_executor import (
    SubtaskExecutor,
    SubtaskExecutionError
)
from app.domain.entities.plan import Plan, Subtask, SubtaskStatus, PlanStatus
from app.domain.entities.agent_context import AgentType
from app.models.schemas import StreamChunk


@pytest.fixture
def mock_plan_repository():
    """Mock репозитория планов"""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_session_service():
    """Mock сервиса сессий"""
    service = AsyncMock()
    mock_session = MagicMock()
    mock_session.id = "test-session-id"
    service.get_session.return_value = mock_session
    return service


@pytest.fixture
def mock_stream_handler():
    """Mock stream handler"""
    return MagicMock()


@pytest.fixture
def sample_plan():
    """Создать тестовый план"""
    plan = Plan(
        id=str(uuid.uuid4()),
        session_id="test-session",
        goal="Test goal"
    )
    
    # Добавить подзадачи
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
        dependencies=[subtask1.id]
    )
    
    plan.add_subtask(subtask1)
    plan.add_subtask(subtask2)
    plan.approve()
    plan.start_execution()
    
    return plan


@pytest.fixture
def subtask_executor(mock_plan_repository):
    """Создать SubtaskExecutor"""
    return SubtaskExecutor(
        plan_repository=mock_plan_repository,
        max_retries=3
    )


class TestSubtaskExecutorInit:
    """Тесты инициализации SubtaskExecutor"""
    
    def test_init_default_params(self, mock_plan_repository):
        """Тест инициализации с параметрами по умолчанию"""
        executor = SubtaskExecutor(plan_repository=mock_plan_repository)
        
        assert executor.plan_repository == mock_plan_repository
        assert executor.max_retries == 3
    
    def test_init_custom_retries(self, mock_plan_repository):
        """Тест инициализации с кастомным количеством попыток"""
        executor = SubtaskExecutor(
            plan_repository=mock_plan_repository,
            max_retries=5
        )
        
        assert executor.max_retries == 5


class TestExecuteSubtask:
    """Тесты выполнения подзадач"""
    
    @pytest.mark.asyncio
    async def test_execute_subtask_success(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        sample_plan
    ):
        """Тест успешного выполнения подзадачи"""
        # Setup
        subtask = sample_plan.subtasks[0]
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Mock агента с async generator
        async def mock_process(*args, **kwargs):
            yield StreamChunk(
                type="assistant_message",
                content="Task completed successfully",
                metadata={"status": "done"}
            )
        
        mock_agent = AsyncMock()
        mock_agent.process = mock_process
        
        with patch(
            'app.domain.services.subtask_executor.agent_registry.get_agent',
            return_value=mock_agent
        ):
            # Execute
            result = await subtask_executor.execute_subtask(
                plan_id=sample_plan.id,
                subtask_id=subtask.id,
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            )
        
        # Assert
        assert result["status"] == "completed"
        assert result["subtask_id"] == subtask.id
        assert result["agent"] == AgentType.CODER.value
        assert "result" in result
        
        # Проверить, что статус обновлен
        assert subtask.status == SubtaskStatus.DONE
        assert subtask.result is not None
        
        # Проверить, что план обновлен в репозитории
        assert mock_plan_repository.update.call_count >= 2  # start + complete
    
    @pytest.mark.asyncio
    async def test_execute_subtask_plan_not_found(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler
    ):
        """Тест выполнения подзадачи когда план не найден"""
        # Setup
        mock_plan_repository.get_by_id.return_value = None
        
        # Execute & Assert
        with pytest.raises(SubtaskExecutionError, match="Plan .* not found"):
            await subtask_executor.execute_subtask(
                plan_id="non-existent-plan",
                subtask_id="some-subtask",
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            )
    
    @pytest.mark.asyncio
    async def test_execute_subtask_not_found(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        sample_plan
    ):
        """Тест выполнения несуществующей подзадачи"""
        # Setup
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Execute & Assert
        with pytest.raises(SubtaskExecutionError, match="Subtask .* not found"):
            await subtask_executor.execute_subtask(
                plan_id=sample_plan.id,
                subtask_id="non-existent-subtask",
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            )
    
    @pytest.mark.asyncio
    async def test_execute_subtask_wrong_status(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        sample_plan
    ):
        """Тест выполнения подзадачи с неправильным статусом"""
        # Setup
        subtask = sample_plan.subtasks[0]
        subtask.status = SubtaskStatus.DONE  # Уже выполнена
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Execute & Assert
        with pytest.raises(
            SubtaskExecutionError,
            match="not in PENDING status"
        ):
            await subtask_executor.execute_subtask(
                plan_id=sample_plan.id,
                subtask_id=subtask.id,
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            )
    
    @pytest.mark.asyncio
    async def test_execute_subtask_agent_error(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        sample_plan
    ):
        """Тест обработки ошибки агента"""
        # Setup
        subtask = sample_plan.subtasks[0]
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Mock агента с ошибкой в async generator
        async def mock_process_error(*args, **kwargs):
            raise RuntimeError("Agent error")
            yield  # Unreachable, но нужно для async generator
        
        mock_agent = AsyncMock()
        mock_agent.process = mock_process_error
        
        with patch(
            'app.domain.services.subtask_executor.agent_registry.get_agent',
            return_value=mock_agent
        ):
            # Execute & Assert
            with pytest.raises(SubtaskExecutionError, match="Failed to execute"):
                await subtask_executor.execute_subtask(
                    plan_id=sample_plan.id,
                    subtask_id=subtask.id,
                    session_id="test-session",
                    session_service=mock_session_service,
                    stream_handler=mock_stream_handler
                )
        
        # Проверить, что подзадача помечена как failed
        assert subtask.status == SubtaskStatus.FAILED
        assert subtask.error is not None
        assert "RuntimeError" in subtask.error
    
    @pytest.mark.asyncio
    async def test_execute_subtask_agent_not_available(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        sample_plan
    ):
        """Тест выполнения когда агент недоступен"""
        # Setup
        subtask = sample_plan.subtasks[0]
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        with patch(
            'app.domain.services.subtask_executor.agent_registry.get_agent',
            side_effect=ValueError("Agent not found")
        ):
            # Execute & Assert
            with pytest.raises(
                SubtaskExecutionError,
                match="Agent .* not available"
            ):
                await subtask_executor.execute_subtask(
                    plan_id=sample_plan.id,
                    subtask_id=subtask.id,
                    session_id="test-session",
                    session_service=mock_session_service,
                    stream_handler=mock_stream_handler
                )


class TestPrepareAgentContext:
    """Тесты подготовки контекста для агента"""
    
    def test_prepare_context_no_dependencies(
        self,
        subtask_executor,
        sample_plan
    ):
        """Тест подготовки контекста без зависимостей"""
        subtask = sample_plan.subtasks[0]
        
        context = subtask_executor._prepare_agent_context(subtask, sample_plan)
        
        assert context["subtask_id"] == subtask.id
        assert context["plan_id"] == sample_plan.id
        assert context["plan_goal"] == sample_plan.goal
        assert context["dependencies"] == {}
        assert context["execution_mode"] == "subtask"
    
    def test_prepare_context_with_dependencies(
        self,
        subtask_executor,
        sample_plan
    ):
        """Тест подготовки контекста с зависимостями"""
        # Завершить первую подзадачу
        subtask1 = sample_plan.subtasks[0]
        subtask1.start()
        subtask1.complete("Result 1")
        
        # Подготовить контекст для второй подзадачи
        subtask2 = sample_plan.subtasks[1]
        context = subtask_executor._prepare_agent_context(subtask2, sample_plan)
        
        assert context["subtask_id"] == subtask2.id
        assert len(context["dependencies"]) == 1
        assert subtask1.id in context["dependencies"]
        
        dep_info = context["dependencies"][subtask1.id]
        assert dep_info["description"] == subtask1.description
        assert dep_info["result"] == "Result 1"
        assert dep_info["agent"] == AgentType.CODER.value


class TestCollectResult:
    """Тесты сбора результатов"""
    
    def test_collect_result_single_chunk(self, subtask_executor):
        """Тест сбора результата из одного chunk"""
        chunks = [
            StreamChunk(
                type="assistant_message",
                content="Test result",
                metadata={"key": "value"}
            )
        ]
        
        result = subtask_executor._collect_result(chunks)
        
        assert result["content"] == "Test result"
        assert result["metadata"]["key"] == "value"
        assert result["chunk_count"] == 1
    
    def test_collect_result_multiple_chunks(self, subtask_executor):
        """Тест сбора результата из нескольких chunks"""
        chunks = [
            StreamChunk(type="assistant_message", content="Part 1", metadata={"a": 1}),
            StreamChunk(type="assistant_message", content="Part 2", metadata={"b": 2}),
            StreamChunk(type="assistant_message", content="Part 3", metadata={"c": 3})
        ]
        
        result = subtask_executor._collect_result(chunks)
        
        assert result["content"] == "Part 1\nPart 2\nPart 3"
        assert result["metadata"]["a"] == 1
        assert result["metadata"]["b"] == 2
        assert result["metadata"]["c"] == 3
        assert result["chunk_count"] == 3
    
    def test_collect_result_empty_chunks(self, subtask_executor):
        """Тест сбора результата из пустого списка"""
        result = subtask_executor._collect_result([])
        
        assert result["content"] == ""
        assert result["metadata"] == {}
        assert result["chunk_count"] == 0


class TestCalculateDuration:
    """Тесты вычисления длительности"""
    
    def test_calculate_duration_completed(self, subtask_executor):
        """Тест вычисления длительности для завершенной подзадачи"""
        subtask = Subtask(
            id=str(uuid.uuid4()),
            description="Test",
            agent=AgentType.CODER
        )
        subtask.started_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        subtask.completed_at = datetime(2024, 1, 1, 10, 5, 30, tzinfo=timezone.utc)
        
        duration = subtask_executor._calculate_duration(subtask)
        
        assert duration == 330.0  # 5 минут 30 секунд
    
    def test_calculate_duration_not_started(self, subtask_executor):
        """Тест вычисления длительности для не начатой подзадачи"""
        subtask = Subtask(
            id=str(uuid.uuid4()),
            description="Test",
            agent=AgentType.CODER
        )
        
        duration = subtask_executor._calculate_duration(subtask)
        
        assert duration is None
    
    def test_calculate_duration_running(self, subtask_executor):
        """Тест вычисления длительности для выполняющейся подзадачи"""
        subtask = Subtask(
            id=str(uuid.uuid4()),
            description="Test",
            agent=AgentType.CODER
        )
        subtask.started_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        duration = subtask_executor._calculate_duration(subtask)
        
        assert duration is None


class TestRetryFailedSubtask:
    """Тесты повторного выполнения неудавшихся подзадач"""
    
    @pytest.mark.asyncio
    async def test_retry_failed_subtask_success(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        sample_plan
    ):
        """Тест успешного повтора неудавшейся подзадачи"""
        # Setup - пометить подзадачу как failed
        subtask = sample_plan.subtasks[0]
        subtask.status = SubtaskStatus.FAILED
        subtask.error = "Previous error"
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Mock агента с async generator
        async def mock_process(*args, **kwargs):
            yield StreamChunk(type="assistant_message", content="Retry successful")
        
        mock_agent = AsyncMock()
        mock_agent.process = mock_process
        
        with patch(
            'app.domain.services.subtask_executor.agent_registry.get_agent',
            return_value=mock_agent
        ):
            # Execute
            result = await subtask_executor.retry_failed_subtask(
                plan_id=sample_plan.id,
                subtask_id=subtask.id,
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            )
        
        # Assert
        assert result["status"] == "completed"
        assert subtask.status == SubtaskStatus.DONE
        assert subtask.error is None
    
    @pytest.mark.asyncio
    async def test_retry_subtask_wrong_status(
        self,
        subtask_executor,
        mock_plan_repository,
        mock_session_service,
        mock_stream_handler,
        sample_plan
    ):
        """Тест повтора подзадачи с неправильным статусом"""
        # Setup - подзадача не в статусе FAILED
        subtask = sample_plan.subtasks[0]
        subtask.status = SubtaskStatus.DONE
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Execute & Assert
        with pytest.raises(
            SubtaskExecutionError,
            match="not in FAILED status"
        ):
            await subtask_executor.retry_failed_subtask(
                plan_id=sample_plan.id,
                subtask_id=subtask.id,
                session_id="test-session",
                session_service=mock_session_service,
                stream_handler=mock_stream_handler
            )


class TestGetSubtaskStatus:
    """Тесты получения статуса подзадачи"""
    
    @pytest.mark.asyncio
    async def test_get_subtask_status_success(
        self,
        subtask_executor,
        mock_plan_repository,
        sample_plan
    ):
        """Тест успешного получения статуса подзадачи"""
        # Setup
        subtask = sample_plan.subtasks[0]
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Execute
        status = await subtask_executor.get_subtask_status(
            plan_id=sample_plan.id,
            subtask_id=subtask.id
        )
        
        # Assert
        assert status["subtask_id"] == subtask.id
        assert status["description"] == subtask.description
        assert status["agent"] == AgentType.CODER.value
        assert status["status"] == SubtaskStatus.PENDING.value
        assert status["dependencies"] == []
    
    @pytest.mark.asyncio
    async def test_get_subtask_status_plan_not_found(
        self,
        subtask_executor,
        mock_plan_repository
    ):
        """Тест получения статуса когда план не найден"""
        # Setup
        mock_plan_repository.get_by_id.return_value = None
        
        # Execute & Assert
        with pytest.raises(SubtaskExecutionError, match="Plan .* not found"):
            await subtask_executor.get_subtask_status(
                plan_id="non-existent",
                subtask_id="some-id"
            )
    
    @pytest.mark.asyncio
    async def test_get_subtask_status_subtask_not_found(
        self,
        subtask_executor,
        mock_plan_repository,
        sample_plan
    ):
        """Тест получения статуса несуществующей подзадачи"""
        # Setup
        mock_plan_repository.get_by_id.return_value = sample_plan
        
        # Execute & Assert
        with pytest.raises(SubtaskExecutionError, match="Subtask .* not found"):
            await subtask_executor.get_subtask_status(
                plan_id=sample_plan.id,
                subtask_id="non-existent"
            )

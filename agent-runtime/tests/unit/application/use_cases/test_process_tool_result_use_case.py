"""
Unit тесты для ProcessToolResultUseCase.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

from app.application.use_cases.process_tool_result_use_case import (
    ProcessToolResultUseCase,
    ProcessToolResultRequest
)
from app.models.schemas import StreamChunk
from app.domain.execution_context.value_objects import PlanStatus


@pytest.fixture
def mock_tool_result_handler():
    """Mock для ToolResultHandler."""
    handler = AsyncMock()
    return handler


@pytest.fixture
def mock_lock_manager():
    """Mock для SessionLockManager."""
    manager = MagicMock()
    
    @asynccontextmanager
    async def mock_lock(session_id):
        yield
    
    manager.lock = mock_lock
    return manager


@pytest.fixture
def mock_plan_repository():
    """Mock для PlanRepository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_execution_coordinator():
    """Mock для ExecutionCoordinator."""
    coordinator = AsyncMock()
    return coordinator


@pytest.fixture
def mock_session_service():
    """Mock для ConversationManagementService."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_stream_handler():
    """Mock для IStreamHandler."""
    handler = AsyncMock()
    return handler


@pytest.fixture
def use_case_basic(mock_tool_result_handler, mock_lock_manager):
    """Fixture для базового Use Case без resumable execution."""
    return ProcessToolResultUseCase(
        tool_result_handler=mock_tool_result_handler,
        lock_manager=mock_lock_manager
    )


@pytest.fixture
def use_case_with_resumable(
    mock_tool_result_handler,
    mock_lock_manager,
    mock_plan_repository,
    mock_execution_coordinator,
    mock_session_service,
    mock_stream_handler
):
    """Fixture для Use Case с resumable execution."""
    return ProcessToolResultUseCase(
        tool_result_handler=mock_tool_result_handler,
        lock_manager=mock_lock_manager,
        plan_repository=mock_plan_repository,
        execution_coordinator=mock_execution_coordinator,
        session_service=mock_session_service,
        stream_handler=mock_stream_handler
    )


@pytest.mark.asyncio
async def test_execute_success(use_case_basic, mock_tool_result_handler):
    """Тест успешной обработки tool result."""
    # Arrange
    request = ProcessToolResultRequest(
        session_id="session-123",
        call_id="call-456",
        result="File created successfully"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(type="assistant_message", token="Done", is_final=False)
        yield StreamChunk(type="done", is_final=True)
    
    mock_tool_result_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case_basic.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2
    assert chunks[0].type == "assistant_message"
    assert chunks[1].type == "done"


@pytest.mark.asyncio
async def test_execute_with_error_result(use_case_basic, mock_tool_result_handler):
    """Тест обработки tool result с ошибкой."""
    # Arrange
    request = ProcessToolResultRequest(
        session_id="session-123",
        call_id="call-456",
        error="File not found"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(
            type="assistant_message",
            token="I see there was an error",
            is_final=False
        )
        yield StreamChunk(type="done", is_final=True)
    
    mock_tool_result_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case_basic.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_execute_with_new_tool_call(use_case_basic, mock_tool_result_handler):
    """Тест обработки когда агент делает новый tool call."""
    # Arrange
    request = ProcessToolResultRequest(
        session_id="session-123",
        call_id="call-456",
        result="Success"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(
            type="tool_call",
            metadata={
                "call_id": "call-789",
                "tool_name": "read_file"
            },
            is_final=False
        )
        yield StreamChunk(type="done", is_final=True)
    
    mock_tool_result_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case_basic.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2
    assert chunks[0].type == "tool_call"
    assert chunks[0].metadata["tool_name"] == "read_file"


@pytest.mark.asyncio
async def test_execute_with_resumable_execution_no_active_plan(
    use_case_with_resumable,
    mock_tool_result_handler,
    mock_plan_repository
):
    """Тест когда нет активного плана для resumable execution."""
    # Arrange
    request = ProcessToolResultRequest(
        session_id="session-123",
        call_id="call-456",
        result="Success"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(type="done", is_final=True)
    
    mock_tool_result_handler.handle = mock_handle
    mock_plan_repository.find_by_session_id.return_value = None
    
    # Act
    chunks = []
    async for chunk in use_case_with_resumable.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 1
    mock_plan_repository.find_by_session_id.assert_called_once_with("session-123")


@pytest.mark.asyncio
async def test_execute_with_resumable_execution_active_plan(
    use_case_with_resumable,
    mock_tool_result_handler,
    mock_plan_repository,
    mock_execution_coordinator
):
    """Тест resumable execution с активным планом."""
    # Arrange
    request = ProcessToolResultRequest(
        session_id="session-123",
        call_id="call-456",
        result="Success"
    )
    
    # Mock plan
    mock_plan = MagicMock()
    mock_plan.id = "plan-789"
    mock_plan.status = PlanStatus.IN_PROGRESS
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(type="done", is_final=True)
    
    async def mock_execute_plan(*args, **kwargs):
        yield StreamChunk(type="subtask_started", is_final=False)
        yield StreamChunk(type="done", is_final=True)
    
    mock_tool_result_handler.handle = mock_handle
    mock_plan_repository.find_by_session_id.return_value = mock_plan
    mock_execution_coordinator.execute_plan = mock_execute_plan
    
    # Act
    chunks = []
    async for chunk in use_case_with_resumable.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 3  # done + subtask_started + done
    assert chunks[1].type == "subtask_started"


@pytest.mark.asyncio
async def test_execute_with_exception(use_case_basic, mock_tool_result_handler):
    """Тест обработки исключения."""
    # Arrange
    request = ProcessToolResultRequest(
        session_id="session-123",
        call_id="call-456",
        result="Success"
    )
    
    async def mock_handle(*args, **kwargs):
        raise ValueError("Test error")
    
    mock_tool_result_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case_basic.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 1
    assert chunks[0].type == "error"
    assert "Test error" in chunks[0].error


@pytest.mark.asyncio
async def test_execute_passes_correct_parameters(use_case_basic, mock_tool_result_handler):
    """Тест что Use Case передает правильные параметры."""
    # Arrange
    request = ProcessToolResultRequest(
        session_id="session-123",
        call_id="call-456",
        result="Success result",
        error=None
    )
    
    captured_kwargs = {}
    
    async def mock_handle(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield StreamChunk(type="done", is_final=True)
    
    mock_tool_result_handler.handle = mock_handle
    
    # Act
    async for _ in use_case_basic.execute(request):
        pass
    
    # Assert
    assert captured_kwargs["session_id"] == "session-123"
    assert captured_kwargs["call_id"] == "call-456"
    assert captured_kwargs["result"] == "Success result"
    assert captured_kwargs["error"] is None

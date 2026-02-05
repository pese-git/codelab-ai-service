"""
Unit тесты для HandleApprovalUseCase.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

from app.application.use_cases.handle_approval_use_case import (
    HandleApprovalUseCase,
    HandleApprovalRequest,
    ApprovalType
)
from app.models.schemas import StreamChunk


@pytest.fixture
def mock_hitl_handler():
    """Mock для HITLDecisionHandler."""
    handler = AsyncMock()
    return handler


@pytest.fixture
def mock_plan_approval_handler():
    """Mock для PlanApprovalHandler."""
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
def use_case(mock_hitl_handler, mock_plan_approval_handler, mock_lock_manager):
    """Fixture для HandleApprovalUseCase."""
    return HandleApprovalUseCase(
        hitl_handler=mock_hitl_handler,
        plan_approval_handler=mock_plan_approval_handler,
        lock_manager=mock_lock_manager
    )


@pytest.mark.asyncio
async def test_execute_hitl_approve(use_case, mock_hitl_handler):
    """Тест HITL approval с решением approve."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.HITL,
        approval_id="call-456",
        decision="approve"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(
            type="tool_result",
            metadata={"call_id": "call-456"},
            is_final=False
        )
        yield StreamChunk(type="assistant_message", token="Done", is_final=False)
        yield StreamChunk(type="done", is_final=True)
    
    mock_hitl_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 3
    assert chunks[0].type == "tool_result"
    assert chunks[1].type == "assistant_message"


@pytest.mark.asyncio
async def test_execute_hitl_reject(use_case, mock_hitl_handler):
    """Тест HITL approval с решением reject."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.HITL,
        approval_id="call-456",
        decision="reject",
        feedback="This is not safe"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(type="assistant_message", token="Understood", is_final=False)
        yield StreamChunk(type="done", is_final=True)
    
    mock_hitl_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_execute_hitl_edit(use_case, mock_hitl_handler):
    """Тест HITL approval с решением edit."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.HITL,
        approval_id="call-456",
        decision="edit",
        modified_arguments={"path": "modified.txt"}
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(
            type="tool_result",
            metadata={"call_id": "call-456"},
            is_final=False
        )
        yield StreamChunk(type="done", is_final=True)
    
    mock_hitl_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_execute_plan_approve(use_case, mock_plan_approval_handler):
    """Тест Plan approval с решением approve."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.PLAN,
        approval_id="plan-approval-789",
        decision="approve"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(
            type="plan_execution_started",
            metadata={"plan_id": "plan-123"},
            is_final=False
        )
        yield StreamChunk(type="subtask_started", is_final=False)
        yield StreamChunk(type="done", is_final=True)
    
    mock_plan_approval_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 3
    assert chunks[0].type == "plan_execution_started"


@pytest.mark.asyncio
async def test_execute_plan_reject(use_case, mock_plan_approval_handler):
    """Тест Plan approval с решением reject."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.PLAN,
        approval_id="plan-approval-789",
        decision="reject",
        feedback="Plan is too complex"
    )
    
    async def mock_handle(*args, **kwargs):
        yield StreamChunk(
            type="plan_execution_rejected",
            metadata={"plan_id": "plan-123"},
            is_final=False
        )
        yield StreamChunk(type="done", is_final=True)
    
    mock_plan_approval_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2
    assert chunks[0].type == "plan_execution_rejected"


@pytest.mark.asyncio
async def test_execute_plan_without_handler(mock_hitl_handler, mock_lock_manager):
    """Тест Plan approval когда handler не настроен."""
    # Arrange
    use_case = HandleApprovalUseCase(
        hitl_handler=mock_hitl_handler,
        plan_approval_handler=None,  # No handler
        lock_manager=mock_lock_manager
    )
    
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.PLAN,
        approval_id="plan-approval-789",
        decision="approve"
    )
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 1
    assert chunks[0].type == "error"
    assert "not configured" in chunks[0].error


@pytest.mark.asyncio
async def test_execute_with_exception(use_case, mock_hitl_handler):
    """Тест обработки исключения."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.HITL,
        approval_id="call-456",
        decision="approve"
    )
    
    async def mock_handle(*args, **kwargs):
        raise ValueError("Test error")
    
    mock_hitl_handler.handle = mock_handle
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 1
    assert chunks[0].type == "error"
    assert "Test error" in chunks[0].error


@pytest.mark.asyncio
async def test_execute_hitl_passes_correct_parameters(use_case, mock_hitl_handler):
    """Тест что HITL Use Case передает правильные параметры."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.HITL,
        approval_id="call-456",
        decision="edit",
        modified_arguments={"key": "value"},
        feedback="Some feedback"
    )
    
    captured_kwargs = {}
    
    async def mock_handle(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield StreamChunk(type="done", is_final=True)
    
    mock_hitl_handler.handle = mock_handle
    
    # Act
    async for _ in use_case.execute(request):
        pass
    
    # Assert
    assert captured_kwargs["session_id"] == "session-123"
    assert captured_kwargs["call_id"] == "call-456"
    assert captured_kwargs["decision"] == "edit"
    assert captured_kwargs["modified_arguments"] == {"key": "value"}
    assert captured_kwargs["feedback"] == "Some feedback"


@pytest.mark.asyncio
async def test_execute_plan_passes_correct_parameters(use_case, mock_plan_approval_handler):
    """Тест что Plan Use Case передает правильные параметры."""
    # Arrange
    request = HandleApprovalRequest(
        session_id="session-123",
        approval_type=ApprovalType.PLAN,
        approval_id="plan-approval-789",
        decision="approve",
        feedback=None
    )
    
    captured_kwargs = {}
    
    async def mock_handle(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield StreamChunk(type="done", is_final=True)
    
    mock_plan_approval_handler.handle = mock_handle
    
    # Act
    async for _ in use_case.execute(request):
        pass
    
    # Assert
    assert captured_kwargs["session_id"] == "session-123"
    assert captured_kwargs["approval_request_id"] == "plan-approval-789"
    assert captured_kwargs["decision"] == "approve"
    assert captured_kwargs["feedback"] is None

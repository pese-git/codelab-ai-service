"""
Unit тесты для ProcessMessageUseCase.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from app.application.use_cases.process_message_use_case import (
    ProcessMessageUseCase,
    ProcessMessageRequest
)
from app.models.schemas import StreamChunk
from app.domain.entities.agent_context import AgentType


@pytest.fixture
def mock_message_processor():
    """Mock для MessageProcessor."""
    processor = AsyncMock()
    return processor


@pytest.fixture
def mock_lock_manager():
    """Mock для SessionLockManager."""
    manager = MagicMock()
    
    # Mock для async context manager
    @asynccontextmanager
    async def mock_lock(session_id):
        yield
    
    manager.lock = mock_lock
    return manager


@pytest.fixture
def use_case(mock_message_processor, mock_lock_manager):
    """Fixture для ProcessMessageUseCase."""
    return ProcessMessageUseCase(
        message_processor=mock_message_processor,
        lock_manager=mock_lock_manager
    )


@pytest.mark.asyncio
async def test_execute_success(use_case, mock_message_processor):
    """Тест успешной обработки сообщения."""
    # Arrange
    request = ProcessMessageRequest(
        session_id="session-123",
        message="Hello, world!",
        agent_type=None
    )
    
    # Mock streaming response
    async def mock_process(*args, **kwargs):
        yield StreamChunk(type="assistant_message", token="Hello", is_final=False)
        yield StreamChunk(type="assistant_message", token=" back", is_final=False)
        yield StreamChunk(type="done", is_final=True)
    
    mock_message_processor.process = mock_process
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 3
    assert chunks[0].type == "assistant_message"
    assert chunks[0].token == "Hello"
    assert chunks[1].token == " back"
    assert chunks[2].type == "done"
    assert chunks[2].is_final is True


@pytest.mark.asyncio
async def test_execute_with_agent_type(use_case, mock_message_processor):
    """Тест обработки сообщения с явным типом агента."""
    # Arrange
    request = ProcessMessageRequest(
        session_id="session-123",
        message="Write a function",
        agent_type=AgentType.CODER
    )
    
    async def mock_process(*args, **kwargs):
        yield StreamChunk(type="agent_switched", content="Switched to coder", is_final=False)
        yield StreamChunk(type="assistant_message", token="Sure", is_final=False)
        yield StreamChunk(type="done", is_final=True)
    
    mock_message_processor.process = mock_process
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 3
    assert chunks[0].type == "agent_switched"


@pytest.mark.asyncio
async def test_execute_with_tool_call(use_case, mock_message_processor):
    """Тест обработки сообщения с tool call."""
    # Arrange
    request = ProcessMessageRequest(
        session_id="session-123",
        message="Create a file",
        agent_type=None
    )
    
    async def mock_process(*args, **kwargs):
        yield StreamChunk(
            type="tool_call",
            metadata={
                "call_id": "call-123",
                "tool_name": "write_file"
            },
            is_final=False
        )
        yield StreamChunk(type="done", is_final=True)
    
    mock_message_processor.process = mock_process
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2
    assert chunks[0].type == "tool_call"
    assert chunks[0].metadata["tool_name"] == "write_file"


@pytest.mark.asyncio
async def test_execute_with_plan_approval(use_case, mock_message_processor):
    """Тест обработки сообщения с plan approval."""
    # Arrange
    request = ProcessMessageRequest(
        session_id="session-123",
        message="Create a complex feature",
        agent_type=None
    )
    
    async def mock_process(*args, **kwargs):
        yield StreamChunk(
            type="plan_approval_required",
            metadata={
                "approval_request_id": "approval-123",
                "plan_id": "plan-456"
            },
            is_final=False
        )
        yield StreamChunk(type="done", is_final=True)
    
    mock_message_processor.process = mock_process
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2
    assert chunks[0].type == "plan_approval_required"
    assert chunks[0].metadata["approval_request_id"] == "approval-123"


@pytest.mark.asyncio
async def test_execute_with_error(use_case, mock_message_processor):
    """Тест обработки ошибки."""
    # Arrange
    request = ProcessMessageRequest(
        session_id="session-123",
        message="Test message",
        agent_type=None
    )
    
    async def mock_process(*args, **kwargs):
        raise ValueError("Test error")
    
    mock_message_processor.process = mock_process
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 1
    assert chunks[0].type == "error"
    assert "Test error" in chunks[0].error
    assert chunks[0].is_final is True


@pytest.mark.asyncio
async def test_execute_calls_lock_manager(use_case, mock_lock_manager):
    """Тест что Use Case использует lock manager."""
    # Arrange
    request = ProcessMessageRequest(
        session_id="session-123",
        message="Test",
        agent_type=None
    )
    
    lock_called = False
    
    @asynccontextmanager
    async def track_lock(session_id):
        nonlocal lock_called
        lock_called = True
        assert session_id == "session-123"
        yield
    
    mock_lock_manager.lock = track_lock
    
    # Mock processor
    async def mock_process(*args, **kwargs):
        yield StreamChunk(type="done", is_final=True)
    
    use_case._message_processor.process = mock_process
    
    # Act
    async for _ in use_case.execute(request):
        pass
    
    # Assert
    assert lock_called is True


@pytest.mark.asyncio
async def test_execute_passes_correct_parameters(use_case, mock_message_processor):
    """Тест что Use Case передает правильные параметры в processor."""
    # Arrange
    request = ProcessMessageRequest(
        session_id="session-123",
        message="Test message",
        agent_type=AgentType.CODER
    )
    
    captured_kwargs = {}
    
    async def mock_process(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield StreamChunk(type="done", is_final=True)
    
    mock_message_processor.process = mock_process
    
    # Act
    async for _ in use_case.execute(request):
        pass
    
    # Assert
    assert captured_kwargs["session_id"] == "session-123"
    assert captured_kwargs["message"] == "Test message"
    assert captured_kwargs["agent_type"] == AgentType.CODER

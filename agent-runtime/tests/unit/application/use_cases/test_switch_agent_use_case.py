"""
Unit тесты для SwitchAgentUseCase.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

from app.application.use_cases.switch_agent_use_case import (
    SwitchAgentUseCase,
    SwitchAgentRequest
)
from app.models.schemas import StreamChunk
from app.domain.entities.agent_context import AgentType


@pytest.fixture
def mock_agent_switcher():
    """Mock для AgentSwitcher."""
    switcher = AsyncMock()
    return switcher


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
def use_case(mock_agent_switcher, mock_lock_manager):
    """Fixture для SwitchAgentUseCase."""
    return SwitchAgentUseCase(
        agent_switcher=mock_agent_switcher,
        lock_manager=mock_lock_manager
    )


@pytest.mark.asyncio
async def test_execute_success(use_case, mock_agent_switcher):
    """Тест успешного переключения агента."""
    # Arrange
    request = SwitchAgentRequest(
        session_id="session-123",
        target_agent=AgentType.CODER,
        reason="User requested"
    )
    
    async def mock_switch(*args, **kwargs):
        yield StreamChunk(
            type="agent_switched",
            content="Switched to coder",
            metadata={
                "from_agent": "orchestrator",
                "to_agent": "coder"
            },
            is_final=False
        )
        yield StreamChunk(type="done", is_final=True)
    
    mock_agent_switcher.switch = mock_switch
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 2
    assert chunks[0].type == "agent_switched"
    assert chunks[0].metadata["to_agent"] == "coder"
    assert chunks[1].type == "done"


@pytest.mark.asyncio
async def test_execute_with_error(use_case, mock_agent_switcher):
    """Тест обработки ошибки при переключении."""
    # Arrange
    request = SwitchAgentRequest(
        session_id="session-123",
        target_agent=AgentType.CODER
    )
    
    async def mock_switch(*args, **kwargs):
        raise ValueError("Cannot switch agent")
    
    mock_agent_switcher.switch = mock_switch
    
    # Act
    chunks = []
    async for chunk in use_case.execute(request):
        chunks.append(chunk)
    
    # Assert
    assert len(chunks) == 1
    assert chunks[0].type == "error"
    assert "Cannot switch agent" in chunks[0].error


@pytest.mark.asyncio
async def test_execute_passes_correct_parameters(use_case, mock_agent_switcher):
    """Тест что Use Case передает правильные параметры."""
    # Arrange
    request = SwitchAgentRequest(
        session_id="session-123",
        target_agent=AgentType.ARCHITECT,
        reason="Planning phase"
    )
    
    captured_kwargs = {}
    
    async def mock_switch(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield StreamChunk(type="done", is_final=True)
    
    mock_agent_switcher.switch = mock_switch
    
    # Act
    async for _ in use_case.execute(request):
        pass
    
    # Assert
    assert captured_kwargs["session_id"] == "session-123"
    assert captured_kwargs["target_agent"] == AgentType.ARCHITECT
    assert captured_kwargs["reason"] == "Planning phase"

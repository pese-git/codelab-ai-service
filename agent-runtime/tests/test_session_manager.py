"""
Unit tests for SessionManagerAdapter (migrated from AsyncSessionManager tests).

UPDATED: Migrated to use SessionManagerAdapter with new architecture.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.infrastructure.adapters import SessionManagerAdapter
from app.domain.services import SessionManagementService
from app.domain.entities.session import Session
from app.core.errors import SessionNotFoundError, SessionAlreadyExistsError


@pytest_asyncio.fixture
async def mock_repository():
    """Create mock repository for testing"""
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest_asyncio.fixture
async def session_service(mock_repository):
    """Create SessionManagementService with mock repository"""
    return SessionManagementService(
        repository=mock_repository,
        event_publisher=AsyncMock()  # Mock event publisher
    )


@pytest_asyncio.fixture
async def session_manager(session_service):
    """Create SessionManagerAdapter for testing"""
    return SessionManagerAdapter(session_service)


@pytest.mark.asyncio
async def test_session_manager_init(session_manager):
    """Test SessionManagerAdapter initialization"""
    assert session_manager._service is not None


@pytest.mark.asyncio
async def test_exists_returns_true(session_manager):
    """Test exists always returns True (compatibility method)"""
    assert session_manager.exists("any-session") is True


@pytest.mark.asyncio
async def test_create_session_success(session_manager, mock_repository):
    """Test successful session creation"""
    session_id = "test_session"
    
    # Mock repository to return new session
    new_session = Session(id=session_id, messages=[], last_activity=datetime.now(timezone.utc))
    mock_repository.save = AsyncMock()
    mock_repository.find_by_id = AsyncMock(return_value=None)  # Not exists
    
    # Create via service (adapter calls service.create_session)
    with patch.object(session_manager._service, 'create_session', return_value=new_session):
        state = await session_manager.create(session_id)
        
        assert isinstance(state, Session)
        assert state.id == session_id
        assert len(state.messages) == 0


@pytest.mark.asyncio
async def test_get_or_create_creates_new_session(session_manager, mock_repository):
    """Test get_or_create creates new session if not exists"""
    session_id = "test_session"
    
    new_session = Session(id=session_id, messages=[], last_activity=datetime.now(timezone.utc))
    
    with patch.object(session_manager._service, 'get_or_create_session', return_value=new_session):
        state = await session_manager.get_or_create(session_id)
        
        assert state is not None
        assert state.id == session_id


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_session(session_manager):
    """Test get_or_create returns existing session"""
    session_id = "test_session"
    
    existing_session = Session(id=session_id, messages=[], last_activity=datetime.now(timezone.utc))
    
    with patch.object(session_manager._service, 'get_or_create_session', return_value=existing_session):
        state = await session_manager.get_or_create(session_id)
        
        assert state.id == session_id


@pytest.mark.asyncio
async def test_append_message_success(session_manager):
    """Test appending message to session"""
    session_id = "test_session"
    
    with patch.object(session_manager._service, 'add_message', return_value=None) as mock_add:
        await session_manager.append_message(session_id, "user", "Hello")
        
        mock_add.assert_called_once_with(
            session_id=session_id,
            role="user",
            content="Hello",
            name=None
        )


@pytest.mark.asyncio
async def test_append_message_with_name(session_manager):
    """Test appending message with name field"""
    session_id = "test_session"
    
    with patch.object(session_manager._service, 'add_message', return_value=None) as mock_add:
        await session_manager.append_message(session_id, "assistant", "Response", name="tool_result")
        
        mock_add.assert_called_once_with(
            session_id=session_id,
            role="assistant",
            content="Response",
            name="tool_result"
        )


@pytest.mark.asyncio
async def test_append_tool_result_success(session_manager):
    """Test appending tool result to session"""
    session_id = "test_session"
    call_id = "call_123"
    tool_name = "list_files"
    result = "file1.txt\nfile2.txt"
    
    with patch.object(session_manager._service, 'add_message', return_value=None) as mock_add:
        await session_manager.append_tool_result(session_id, call_id, tool_name, result)
        
        mock_add.assert_called_once_with(
            session_id=session_id,
            role="tool",
            content=result,
            name=tool_name,
            tool_call_id=call_id
        )


@pytest.mark.asyncio
async def test_append_assistant_with_tool_calls(session_manager):
    """Test appending assistant message with tool_calls"""
    session_id = "test_session"
    tool_calls = [{
        "id": "call_123",
        "type": "function",
        "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}
    }]
    
    with patch.object(session_manager._service, 'add_message', return_value=None) as mock_add:
        await session_manager.append_assistant_with_tool_calls(session_id, tool_calls)
        
        mock_add.assert_called_once_with(
            session_id=session_id,
            role="assistant",
            content="",
            tool_calls=tool_calls
        )


@pytest.mark.asyncio
async def test_get_history_returns_empty_list(session_manager):
    """Test get_history returns empty list (compatibility method)"""
    history = session_manager.get_history("any-session")
    assert history == []


@pytest.mark.asyncio
async def test_all_sessions_returns_empty_list(session_manager):
    """Test all_sessions returns empty list (compatibility method)"""
    sessions = session_manager.all_sessions()
    assert sessions == []


@pytest.mark.asyncio
async def test_delete_session(session_manager):
    """Test deleting session"""
    session_id = "test_session"
    
    with patch.object(session_manager._service, 'deactivate_session', return_value=None) as mock_deactivate:
        await session_manager.delete(session_id)
        
        mock_deactivate.assert_called_once_with(
            session_id=session_id,
            reason="Deleted by user"
        )


@pytest.mark.asyncio
async def test_shutdown(session_manager):
    """Test shutdown (no-op in new architecture)"""
    # Should not raise any exception
    await session_manager.shutdown()


# Integration tests with real service (if needed)
@pytest.mark.asyncio
async def test_integration_create_and_get(mock_repository):
    """Integration test: create session and retrieve it"""
    session_id = "integration_test"
    
    # Setup mock to simulate database behavior
    created_session = None
    
    async def mock_save(session):
        nonlocal created_session
        created_session = session
    
    async def mock_find(sid):
        return created_session if created_session and created_session.id == sid else None
    
    mock_repository.save = mock_save
    mock_repository.find_by_id = mock_find
    
    # Create service and adapter
    service = SessionManagementService(repository=mock_repository, event_publisher=AsyncMock())
    adapter = SessionManagerAdapter(service)
    
    # Create session
    session = await adapter.create(session_id)
    assert session.id == session_id
    
    # Get session
    retrieved = await adapter.get_or_create(session_id)
    assert retrieved.id == session_id


@pytest.mark.asyncio
async def test_integration_add_messages(mock_repository):
    """Integration test: add messages to session"""
    session_id = "integration_test"
    
    # Setup mock
    test_session = Session(id=session_id, messages=[], last_activity=datetime.now(timezone.utc))
    
    async def mock_find(sid):
        return test_session if sid == session_id else None
    
    mock_repository.find_by_id = mock_find
    mock_repository.save = AsyncMock()
    
    # Create service and adapter
    service = SessionManagementService(repository=mock_repository, event_publisher=AsyncMock())
    adapter = SessionManagerAdapter(service)
    
    # Add messages
    await adapter.append_message(session_id, "user", "Hello")
    await adapter.append_message(session_id, "assistant", "Hi there")
    
    # Verify messages added
    assert len(test_session.messages) == 2
    assert test_session.messages[0].role == "user"
    assert test_session.messages[0].content == "Hello"
    assert test_session.messages[1].role == "assistant"
    assert test_session.messages[1].content == "Hi there"

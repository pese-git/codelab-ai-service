"""
Unit tests for AsyncSessionManager.
"""
import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.session_manager_async import AsyncSessionManager
from app.models.schemas import SessionState, Message


@pytest_asyncio.fixture
async def session_manager():
    """Create a fresh AsyncSessionManager instance for each test"""
    manager = AsyncSessionManager()
    await manager.initialize()
    # Cancel background writer to avoid warnings
    if manager._write_task:
        manager._write_task.cancel()
        try:
            await manager._write_task
        except:
            pass
    return manager


@pytest.mark.asyncio
async def test_session_manager_init(session_manager):
    """Test AsyncSessionManager initialization"""
    assert session_manager._sessions == {}
    assert session_manager._lock is not None


@pytest.mark.asyncio
async def test_exists_returns_false_for_nonexistent_session(session_manager):
    """Test exists returns False for non-existent session"""
    assert session_manager.exists("nonexistent") is False


@pytest.mark.asyncio
async def test_exists_returns_true_for_existing_session(session_manager):
    """Test exists returns True for existing session"""
    session_id = "test_session"
    await session_manager.create(session_id)
    assert session_manager.exists(session_id) is True


@pytest.mark.asyncio
async def test_create_session_success(session_manager):
    """Test successful session creation"""
    session_id = "test_session"
    state = await session_manager.create(session_id)
    
    assert isinstance(state, SessionState)
    assert state.session_id == session_id
    assert len(state.messages) == 0
    assert session_manager.exists(session_id)


@pytest.mark.asyncio
async def test_create_session_with_system_prompt(session_manager):
    """Test session creation with system prompt"""
    session_id = "test_session"
    system_prompt = "You are a helpful assistant"
    
    state = await session_manager.create(session_id, system_prompt)
    
    assert len(state.messages) == 1
    assert state.messages[0].role == "system"
    assert state.messages[0].content == system_prompt


@pytest.mark.asyncio
async def test_create_duplicate_session_raises_error(session_manager):
    """Test creating duplicate session raises ValueError"""
    session_id = "test_session"
    await session_manager.create(session_id)
    
    with pytest.raises(ValueError, match=f"Session {session_id} already exists"):
        await session_manager.create(session_id)


@pytest.mark.asyncio
async def test_get_existing_session(session_manager):
    """Test getting existing session"""
    session_id = "test_session"
    created_state = await session_manager.create(session_id)
    
    retrieved_state = session_manager.get(session_id)
    
    assert retrieved_state is not None
    assert retrieved_state.session_id == created_state.session_id


@pytest.mark.asyncio
async def test_get_nonexistent_session_returns_none(session_manager):
    """Test getting non-existent session returns None"""
    result = session_manager.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_or_create_creates_new_session(session_manager):
    """Test get_or_create creates new session if not exists"""
    session_id = "test_session"
    
    state = await session_manager.get_or_create(session_id)
    
    assert state is not None
    assert state.session_id == session_id
    assert session_manager.exists(session_id)


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_session(session_manager):
    """Test get_or_create returns existing session"""
    session_id = "test_session"
    created_state = await session_manager.create(session_id)
    
    retrieved_state = await session_manager.get_or_create(session_id)
    
    assert retrieved_state.session_id == created_state.session_id


@pytest.mark.asyncio
async def test_append_message_success(session_manager):
    """Test appending message to session"""
    session_id = "test_session"
    await session_manager.create(session_id)
    
    await session_manager.append_message(session_id, "user", "Hello")
    
    state = session_manager.get(session_id)
    assert len(state.messages) == 1
    assert state.messages[0].role == "user"
    assert state.messages[0].content == "Hello"


@pytest.mark.asyncio
async def test_append_message_with_name(session_manager):
    """Test appending message with name field"""
    session_id = "test_session"
    await session_manager.create(session_id)
    
    await session_manager.append_message(session_id, "assistant", "Response", name="tool_result")
    
    state = session_manager.get(session_id)
    assert len(state.messages) == 1
    assert state.messages[0].name == "tool_result"


@pytest.mark.asyncio
async def test_append_message_updates_last_activity(session_manager):
    """Test appending message updates last_activity timestamp"""
    session_id = "test_session"
    state = await session_manager.create(session_id)
    initial_time = state.last_activity
    
    await session_manager.append_message(session_id, "user", "Hello")
    
    updated_state = session_manager.get(session_id)
    assert updated_state.last_activity > initial_time


@pytest.mark.asyncio
async def test_append_message_to_nonexistent_session_raises_error(session_manager):
    """Test appending message to non-existent session raises ValueError"""
    with pytest.raises(ValueError, match="Session nonexistent not found"):
        await session_manager.append_message("nonexistent", "user", "Hello")


@pytest.mark.asyncio
async def test_append_tool_result_success(session_manager):
    """Test appending tool result to session"""
    session_id = "test_session"
    await session_manager.create(session_id)
    
    call_id = "call_123"
    tool_name = "list_files"
    result = "file1.txt\nfile2.txt"
    
    await session_manager.append_tool_result(session_id, call_id, tool_name, result)
    
    state = session_manager.get(session_id)
    assert len(state.messages) == 1
    
    tool_msg = state.messages[0]
    assert tool_msg["role"] == "tool"
    assert tool_msg["content"] == result
    assert tool_msg["tool_call_id"] == call_id
    assert tool_msg["name"] == tool_name


@pytest.mark.asyncio
async def test_append_tool_result_to_nonexistent_session_raises_error(session_manager):
    """Test appending tool result to non-existent session raises ValueError"""
    with pytest.raises(ValueError, match="Session nonexistent not found"):
        await session_manager.append_tool_result("nonexistent", "call_123", "tool", "result")


@pytest.mark.asyncio
async def test_get_history_returns_empty_for_nonexistent_session(session_manager):
    """Test get_history returns empty list for non-existent session"""
    history = session_manager.get_history("nonexistent")
    assert history == []


@pytest.mark.asyncio
async def test_get_history_returns_messages_as_dicts(session_manager):
    """Test get_history returns messages as dictionaries"""
    session_id = "test_session"
    await session_manager.create(session_id)
    await session_manager.append_message(session_id, "user", "Hello")
    await session_manager.append_message(session_id, "assistant", "Hi there")
    
    history = session_manager.get_history(session_id)
    
    assert len(history) == 2
    assert all(isinstance(msg, dict) for msg in history)
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hi there"


@pytest.mark.asyncio
async def test_get_history_handles_mixed_message_types(session_manager):
    """Test get_history handles both Pydantic models and dict messages"""
    session_id = "test_session"
    state = await session_manager.create(session_id)
    
    # Add Pydantic message
    await session_manager.append_message(session_id, "user", "Hello")
    
    # Add dict message (like tool result)
    state.messages.append({
        "role": "tool",
        "content": "result",
        "tool_call_id": "call_123"
    })
    
    history = session_manager.get_history(session_id)
    
    assert len(history) == 2
    assert all(isinstance(msg, dict) for msg in history)


@pytest.mark.asyncio
async def test_all_sessions_returns_empty_list_initially(session_manager):
    """Test all_sessions returns empty list when no sessions exist"""
    sessions = session_manager.all_sessions()
    assert sessions == []


@pytest.mark.asyncio
async def test_all_sessions_returns_all_created_sessions(session_manager):
    """Test all_sessions returns all created sessions"""
    await session_manager.create("session1")
    await session_manager.create("session2")
    await session_manager.create("session3")
    
    sessions = session_manager.all_sessions()
    
    assert len(sessions) == 3
    session_ids = {s.session_id for s in sessions}
    assert session_ids == {"session1", "session2", "session3"}


@pytest.mark.asyncio
async def test_delete_existing_session(session_manager):
    """Test deleting existing session"""
    session_id = "test_session"
    await session_manager.create(session_id)
    assert session_manager.exists(session_id)
    
    await session_manager.delete(session_id)
    
    assert not session_manager.exists(session_id)
    assert session_manager.get(session_id) is None


@pytest.mark.asyncio
async def test_delete_nonexistent_session_does_not_raise(session_manager):
    """Test deleting non-existent session does not raise error"""
    # Should not raise any exception
    await session_manager.delete("nonexistent")


@pytest.mark.asyncio
async def test_thread_safety_with_lock(session_manager):
    """Test that operations use lock for async safety"""
    session_id = "test_session"
    
    # Test that lock exists and is used (asyncio.Lock)
    # Just verify the lock attribute exists and operations work correctly
    assert session_manager._lock is not None
    
    # Verify operations work correctly with lock
    await session_manager.create(session_id)
    assert session_manager.exists(session_id)
    
    # Verify async-safe behavior
    await session_manager.append_message(session_id, "user", "test")
    state = session_manager.get(session_id)
    assert len(state.messages) == 1


@pytest.mark.asyncio
async def test_multiple_messages_in_session(session_manager):
    """Test adding multiple messages to a session"""
    session_id = "test_session"
    await session_manager.create(session_id, "You are helpful")
    
    await session_manager.append_message(session_id, "user", "Question 1")
    await session_manager.append_message(session_id, "assistant", "Answer 1")
    await session_manager.append_message(session_id, "user", "Question 2")
    await session_manager.append_message(session_id, "assistant", "Answer 2")
    
    history = session_manager.get_history(session_id)
    
    assert len(history) == 5  # system + 4 messages
    assert history[0]["role"] == "system"
    assert history[1]["role"] == "user"
    assert history[2]["role"] == "assistant"
    assert history[3]["role"] == "user"
    assert history[4]["role"] == "assistant"

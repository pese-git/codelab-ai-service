"""
Unit tests for LLMStreamService.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_stream_service import stream_response
from app.infrastructure.adapters import SessionManagerAdapter
from app.models.schemas import StreamChunk, ToolCall


@pytest.fixture
def mock_llm_proxy_client():
    """Mock LLM proxy client"""
    with patch("app.services.llm_stream_service.llm_proxy_client") as mock:
        yield mock


@pytest_asyncio.fixture
async def mock_session_manager():
    """Mock session manager adapter"""
    mock = AsyncMock(spec=SessionManagerAdapter)
    mock.append_message = AsyncMock()
    mock.append_assistant_with_tool_calls = AsyncMock()
    mock.append_message = AsyncMock()
    mock.append_tool_result = AsyncMock()
    mock._schedule_persist = AsyncMock()
    return mock


@pytest.fixture
def mock_parse_tool_calls():
    """Mock parse_tool_calls function"""
    with patch("app.services.llm_stream_service.parse_tool_calls") as mock:
        yield mock


@pytest_asyncio.fixture
async def mock_hitl_manager():
    """Mock HITL manager"""
    with patch("app.services.llm_stream_service.hitl_manager") as mock:
        mock.add_pending = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_stream_response_assistant_message(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test stream_response with simple assistant message"""
    session_id = "test_session"
    history = [{"role": "user", "content": "Hello"}]
    
    # Mock LLM response
    mock_llm_proxy_client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Hi there!"
            }
        }]
    })
    
    # Mock parse_tool_calls to return no tool calls
    mock_parse_tool_calls.return_value = ([], "Hi there!")
    
    # Mock session
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get.return_value = mock_session
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify
    assert len(chunks) == 1
    assert chunks[0].type == "assistant_message"
    assert chunks[0].content == "Hi there!"
    assert chunks[0].is_final is True
    
    # Verify session manager was called
    mock_session_manager.append_message.assert_awaited_once_with(
        session_id, "assistant", "Hi there!"
    )


@pytest.mark.asyncio
async def test_stream_response_tool_call(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test stream_response with tool call"""
    session_id = "test_session"
    history = [{"role": "user", "content": "List files"}]
    
    # Mock LLM response with tool call
    mock_llm_proxy_client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "list_files",
                        "arguments": '{"path": "."}'
                    }
                }]
            }
        }]
    })
    
    # Mock parse_tool_calls to return tool call
    tool_call = ToolCall.model_construct(
        id="call_123",
        tool_name="list_files",
        arguments={"path": "."}
    )
    mock_parse_tool_calls.return_value = ([tool_call], None)
    
    # Mock session
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get.return_value = mock_session
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify
    assert len(chunks) == 1
    assert chunks[0].type == "tool_call"
    assert chunks[0].call_id == "call_123"
    assert chunks[0].tool_name == "list_files"
    assert chunks[0].arguments == {"path": "."}
    assert chunks[0].requires_approval is False
    assert chunks[0].is_final is True
    
    # Verify append_assistant_with_tool_calls was called (not direct message append)
    mock_session_manager.append_assistant_with_tool_calls.assert_awaited_once()
    call_args = mock_session_manager.append_assistant_with_tool_calls.call_args
    assert call_args[1]["session_id"] == session_id
    assert len(call_args[1]["tool_calls"]) == 1
    assert call_args[1]["tool_calls"][0]["id"] == "call_123"


@pytest.mark.asyncio
async def test_stream_response_tool_call_requires_approval(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test stream_response with tool call that requires approval"""
    session_id = "test_session"
    history = [{"role": "user", "content": "Write file"}]
    
    # Mock LLM response with write_file tool call
    mock_llm_proxy_client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_456",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "test.txt", "content": "Hello"}'
                    }
                }]
            }
        }]
    })
    
    # Mock parse_tool_calls
    tool_call = ToolCall.model_construct(
        id="call_456",
        tool_name="write_file",
        arguments={"path": "test.txt", "content": "Hello"}
    )
    mock_parse_tool_calls.return_value = ([tool_call], None)
    
    # Mock session
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get.return_value = mock_session
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify requires_approval is True for write_file
    assert len(chunks) == 1
    assert chunks[0].type == "tool_call"
    assert chunks[0].tool_name == "write_file"
    assert chunks[0].requires_approval is True


@pytest.mark.asyncio
async def test_stream_response_dangerous_command_requires_approval(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test stream_response with dangerous execute_command requires approval"""
    session_id = "test_session"
    history = [{"role": "user", "content": "Delete all files"}]
    
    # Mock LLM response with dangerous command
    mock_llm_proxy_client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_789",
                    "type": "function",
                    "function": {
                        "name": "execute_command",
                        "arguments": '{"command": "rm -rf /"}'
                    }
                }]
            }
        }]
    })
    
    # Mock parse_tool_calls
    tool_call = ToolCall.model_construct(
        id="call_789",
        tool_name="execute_command",
        arguments={"command": "rm -rf /"}
    )
    mock_parse_tool_calls.return_value = ([tool_call], None)
    
    # Mock session
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get.return_value = mock_session
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify requires_approval is True for dangerous command
    assert len(chunks) == 1
    assert chunks[0].type == "tool_call"
    assert chunks[0].tool_name == "execute_command"
    assert chunks[0].requires_approval is True


@pytest.mark.asyncio
async def test_stream_response_multiple_tool_calls_warning(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test stream_response with multiple tool calls (should use only first)"""
    session_id = "test_session"
    history = [{"role": "user", "content": "Do multiple things"}]
    
    # Mock LLM response with multiple tool calls
    mock_llm_proxy_client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "tool1", "arguments": "{}"}
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "tool2", "arguments": "{}"}
                    }
                ]
            }
        }]
    })
    
    # Mock parse_tool_calls to return multiple tool calls
    tool_calls = [
        ToolCall.model_construct(id="call_1", tool_name="tool1", arguments={}),
        ToolCall.model_construct(id="call_2", tool_name="tool2", arguments={})
    ]
    mock_parse_tool_calls.return_value = (tool_calls, None)
    
    # Mock session
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get.return_value = mock_session
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify only first tool call is used
    assert len(chunks) == 1
    assert chunks[0].call_id == "call_1"
    assert chunks[0].tool_name == "tool1"


@pytest.mark.asyncio
async def test_stream_response_error_handling(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test stream_response error handling"""
    session_id = "test_session"
    history = [{"role": "user", "content": "Hello"}]
    
    # Mock LLM client to raise exception
    mock_llm_proxy_client.chat_completion = AsyncMock(
        side_effect=Exception("LLM error")
    )
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify error chunk is returned
    assert len(chunks) == 1
    assert chunks[0].type == "error"
    assert "LLM error" in chunks[0].error
    assert chunks[0].is_final is True


@pytest.mark.asyncio
async def test_stream_response_list_content_handling(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test stream_response with list content format"""
    session_id = "test_session"
    history = [{"role": "user", "content": "Hello"}]
    
    # Mock LLM response with list content
    mock_llm_proxy_client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "role": "assistant",
                "content": [{"content": "Response text"}]
            }
        }]
    })
    
    # Mock parse_tool_calls
    mock_parse_tool_calls.return_value = ([], [{"content": "Response text"}])
    
    # Mock session
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get.return_value = mock_session
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify content is extracted correctly
    assert len(chunks) == 1
    assert chunks[0].type == "assistant_message"
    assert chunks[0].content == "Response text"


@pytest.mark.asyncio
async def test_stream_response_with_tools_spec(
    mock_llm_proxy_client, mock_session_manager, mock_parse_tool_calls, mock_hitl_manager
):
    """Test that stream_response passes TOOLS_SPEC to LLM"""
    session_id = "test_session"
    history = [{"role": "user", "content": "Hello"}]
    
    # Mock LLM response
    mock_llm_proxy_client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Response"
            }
        }]
    })
    
    # Mock parse_tool_calls
    mock_parse_tool_calls.return_value = ([], "Response")
    
    # Mock session
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get.return_value = mock_session
    
    # Execute with session_mgr parameter
    chunks = []
    async for chunk in stream_response(session_id, history, None, mock_session_manager):
        chunks.append(chunk)
    
    # Verify chat_completion was called with tools parameter
    mock_llm_proxy_client.chat_completion.assert_called_once()
    call_kwargs = mock_llm_proxy_client.chat_completion.call_args[1]
    assert "tools" in call_kwargs
    assert call_kwargs["stream"] is False

import pytest

from app.models.schemas import Message, StreamChunk


def test_message_valid():
    m = Message.model_construct(role="user", content="Hello!")
    assert m.role == "user"
    assert m.content == "Hello!"


def test_message_invalid_missing_fields():
    import pydantic

    with pytest.raises((TypeError, pydantic.ValidationError)):
        Message.model_validate({})  # Все поля обязательны


def test_stream_chunk_assistant_message():
    """Test StreamChunk for assistant message"""
    chunk = StreamChunk.model_construct(
        type="assistant_message",
        token="hello",
        is_final=True
    )
    assert chunk.type == "assistant_message"
    assert chunk.token == "hello"
    assert chunk.is_final is True


def test_stream_chunk_tool_call():
    """Test StreamChunk for tool call"""
    chunk = StreamChunk.model_construct(
        type="tool_call",
        call_id="call_123",
        tool_name="read_file",
        arguments={"path": "/src/main.py"},
        is_final=True
    )
    assert chunk.type == "tool_call"
    assert chunk.call_id == "call_123"
    assert chunk.tool_name == "read_file"
    assert chunk.arguments == {"path": "/src/main.py"}


def test_stream_chunk_error():
    """Test StreamChunk for error"""
    chunk = StreamChunk.model_construct(
        type="error",
        error="Something went wrong",
        is_final=True
    )
    assert chunk.type == "error"
    assert chunk.error == "Something went wrong"


def test_stream_chunk_agent_switched():
    """Test StreamChunk for agent switch"""
    chunk = StreamChunk.model_construct(
        type="agent_switched",
        content="Switched to coder agent",
        metadata={"from_agent": "orchestrator", "to_agent": "coder"},
        is_final=False
    )
    assert chunk.type == "agent_switched"
    assert chunk.content == "Switched to coder agent"
    assert chunk.metadata["to_agent"] == "coder"

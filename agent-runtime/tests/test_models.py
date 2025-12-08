import pytest
from agent_runtime.app.main import Message, SSEToken, parse_sse_line


def test_message_valid():
    m = Message(session_id="abc123", type="user_message", content="Hello!")
    assert m.session_id == "abc123"
    assert m.type == "user_message"
    assert m.content == "Hello!"


def test_message_invalid_missing_fields():
    with pytest.raises(TypeError):
        Message()  # Все поля обязательны


def test_ssetoken_valid():
    t = SSEToken(token="hello", is_final=True)
    assert t.token == "hello"
    assert t.is_final is True
    assert t.type == "assistant_message"


def test_ssetoken_invalid_wrong_type():
    with pytest.raises(TypeError):
        SSEToken(token=123, is_final="nope")


def test_parse_sse_line_valid():
    line = 'data: {"token": "foo", "is_final": true, "type": "assistant_message"}'
    token = parse_sse_line(line)
    assert isinstance(token, SSEToken)
    assert token.token == "foo"
    assert token.is_final
    assert token.type == "assistant_message"


def test_parse_sse_line_invalid_prefix():
    line = 'event: {"token": "no", "is_final": false}'
    assert parse_sse_line(line) is None


def test_parse_sse_line_invalid_json():
    bad = "data: this is not json"
    assert parse_sse_line(bad) is None

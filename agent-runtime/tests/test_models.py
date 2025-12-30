import pytest

from app.models.schemas import Message, SSEToken
# Встроенная версия parse_sse_line, соответствующая логике llm_stream_service

def parse_sse_line(line):
    line = line.strip()
    if not line.startswith("data:"):
        return None
    json_str = line[5:].strip()
    if not json_str.startswith("{"):
        return None
    try:
        return SSEToken.model_validate_json(json_str)
    except Exception:
        return None


def test_message_valid():
    m = Message.model_construct(session_id="abc123", type="user_message", content="Hello!")
    assert m.session_id == "abc123"
    assert m.type == "user_message"
    assert m.content == "Hello!"


def test_message_invalid_missing_fields():
    import pydantic

    with pytest.raises((TypeError, pydantic.ValidationError)):
        Message.model_validate({})  # Все поля обязательны


def test_ssetoken_valid():
    t = SSEToken.model_construct(token="hello", is_final=True)
    assert t.token == "hello"
    assert t.is_final is True
    assert t.type == "assistant_message"


def test_ssetoken_invalid_wrong_type():
    import pydantic

    with pytest.raises((TypeError, pydantic.ValidationError)):
        SSEToken.model_validate({"token": 123, "is_final": "nope"})


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

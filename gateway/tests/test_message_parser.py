"""
Unit тесты для WebSocketMessageParser.
"""

import pytest
import json

from app.services.websocket.message_parser import WebSocketMessageParser


@pytest.fixture
def parser():
    """Fixture для создания WebSocketMessageParser."""
    return WebSocketMessageParser()


def test_parse_user_message(parser):
    """Тест парсинга user_message."""
    raw_msg = json.dumps({
        "type": "user_message",
        "content": "Hello",
        "role": "user"
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "user_message"
    assert message.content == "Hello"
    assert message.role == "user"


def test_parse_tool_result(parser):
    """Тест парсинга tool_result."""
    raw_msg = json.dumps({
        "type": "tool_result",
        "call_id": "call_123",
        "result": {"output": "success"}
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "tool_result"
    assert message.call_id == "call_123"
    assert message.result == {"output": "success"}
    assert message.error is None


def test_parse_tool_result_with_error(parser):
    """Тест парсинга tool_result с ошибкой."""
    raw_msg = json.dumps({
        "type": "tool_result",
        "call_id": "call_123",
        "error": "Command failed"
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "tool_result"
    assert message.call_id == "call_123"
    assert message.error == "Command failed"
    assert message.result is None


def test_parse_switch_agent(parser):
    """Тест парсинга switch_agent."""
    raw_msg = json.dumps({
        "type": "switch_agent",
        "agent_type": "debug",
        "content": "Switch to debug mode"
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "switch_agent"
    assert message.agent_type == "debug"
    assert message.content == "Switch to debug mode"


def test_parse_hitl_decision(parser):
    """Тест парсинга hitl_decision."""
    raw_msg = json.dumps({
        "type": "hitl_decision",
        "call_id": "call_456",
        "decision": "approve"
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "hitl_decision"
    assert message.call_id == "call_456"
    assert message.decision == "approve"


def test_parse_hitl_decision_with_feedback(parser):
    """Тест парсинга hitl_decision с feedback."""
    raw_msg = json.dumps({
        "type": "hitl_decision",
        "call_id": "call_456",
        "decision": "reject",
        "feedback": "Too risky"
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "hitl_decision"
    assert message.call_id == "call_456"
    assert message.decision == "reject"
    assert message.feedback == "Too risky"


def test_parse_plan_decision(parser):
    """Тест парсинга plan_decision."""
    raw_msg = json.dumps({
        "type": "plan_decision",
        "approval_request_id": "req_789",
        "decision": "approve"
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "plan_decision"
    assert message.approval_request_id == "req_789"
    assert message.decision == "approve"


def test_parse_plan_decision_with_feedback(parser):
    """Тест парсинга plan_decision с feedback."""
    raw_msg = json.dumps({
        "type": "plan_decision",
        "approval_request_id": "req_789",
        "decision": "reject",
        "feedback": "Need more details"
    })
    
    message = parser.parse(raw_msg)
    
    assert message.type == "plan_decision"
    assert message.approval_request_id == "req_789"
    assert message.decision == "reject"
    assert message.feedback == "Need more details"


def test_parse_invalid_json(parser):
    """Тест обработки невалидного JSON."""
    raw_msg = "not a json"
    
    with pytest.raises(ValueError, match="Invalid JSON"):
        parser.parse(raw_msg)


def test_parse_missing_type(parser):
    """Тест обработки сообщения без type."""
    raw_msg = json.dumps({
        "content": "Hello"
    })
    
    with pytest.raises(ValueError, match="Message type is required"):
        parser.parse(raw_msg)


def test_parse_unknown_type(parser):
    """Тест обработки неизвестного типа сообщения."""
    raw_msg = json.dumps({
        "type": "unknown_type",
        "data": "something"
    })
    
    with pytest.raises(ValueError, match="Unknown message type: unknown_type"):
        parser.parse(raw_msg)


def test_parse_plan_decision_with_call_id_error(parser):
    """Тест специальной обработки ошибки с call_id в plan_decision."""
    # Это распространенная ошибка - использование call_id вместо approval_request_id
    raw_msg = json.dumps({
        "type": "plan_decision",
        "call_id": "call_123",  # Неправильное поле
        "decision": "approve"
    })
    
    # Проверяем что ошибка валидации происходит
    with pytest.raises(ValueError, match="Validation error"):
        parser.parse(raw_msg)


def test_parse_user_message_missing_required_field(parser):
    """Тест валидации обязательных полей."""
    raw_msg = json.dumps({
        "type": "user_message"
        # Отсутствует content и role
    })
    
    with pytest.raises(ValueError, match="Validation error"):
        parser.parse(raw_msg)


def test_parse_tool_result_missing_call_id(parser):
    """Тест валидации call_id в tool_result."""
    raw_msg = json.dumps({
        "type": "tool_result",
        "result": {"output": "success"}
        # Отсутствует call_id
    })
    
    with pytest.raises(ValueError, match="Validation error"):
        parser.parse(raw_msg)

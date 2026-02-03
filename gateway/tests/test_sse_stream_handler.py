"""
Unit тесты для SSEStreamHandler.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.services.websocket.sse_stream_handler import SSEStreamHandler


@pytest.fixture
def handler():
    """Fixture для создания SSEStreamHandler."""
    return SSEStreamHandler()


@pytest.fixture
def mock_websocket():
    """Fixture для мокирования WebSocket."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def mock_response():
    """Fixture для мокирования HTTP response."""
    return MagicMock()


@pytest.mark.asyncio
async def test_process_simple_message(handler, mock_websocket, mock_response):
    """Тест обработки простого SSE сообщения."""
    lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Hello"}',
        "",
        "event: done",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Проверяем что сообщение было отправлено
    mock_websocket.send_json.assert_called_once()
    call_args = mock_websocket.send_json.call_args[0][0]
    assert call_args["type"] == "assistant_message"
    assert call_args["token"] == "Hello"


@pytest.mark.asyncio
async def test_process_multiple_messages(handler, mock_websocket, mock_response):
    """Тест обработки нескольких SSE сообщений."""
    lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Hello"}',
        "",
        "event: message",
        'data: {"type": "assistant_message", "token": " world"}',
        "",
        "event: done",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Проверяем что оба сообщения были отправлены
    assert mock_websocket.send_json.call_count == 2


@pytest.mark.asyncio
async def test_process_done_event(handler, mock_websocket, mock_response):
    """Тест обработки event: done."""
    lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Test"}',
        "",
        "event: done",
        "data: ignored",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Проверяем что обработка остановилась после done
    assert mock_websocket.send_json.call_count == 1


@pytest.mark.asyncio
async def test_process_done_marker(handler, mock_websocket, mock_response):
    """Тест обработки маркера [DONE]."""
    lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Test"}',
        "",
        "data: [DONE]",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Проверяем что обработка остановилась после [DONE]
    assert mock_websocket.send_json.call_count == 1


@pytest.mark.asyncio
async def test_filter_null_values(handler, mock_websocket, mock_response):
    """Тест фильтрации null значений."""
    lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Hello", "metadata": null, "extra": null}',
        "",
        "event: done",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Проверяем что null поля отфильтрованы
    call_args = mock_websocket.send_json.call_args[0][0]
    assert "metadata" not in call_args
    assert "extra" not in call_args
    assert call_args["type"] == "assistant_message"
    assert call_args["token"] == "Hello"


@pytest.mark.asyncio
async def test_process_heartbeat(handler, mock_websocket, mock_response):
    """Тест обработки SSE heartbeat (комментарии)."""
    lines = [
        ": heartbeat",
        "event: message",
        'data: {"type": "assistant_message", "token": "Test"}',
        "",
        ": another heartbeat",
        "event: done",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Heartbeat не должны влиять на обработку
    assert mock_websocket.send_json.call_count == 1


@pytest.mark.asyncio
async def test_process_invalid_json(handler, mock_websocket, mock_response):
    """Тест обработки невалидного JSON в data."""
    lines = [
        "event: message",
        "data: not a json",
        "",
        "event: message",
        'data: {"type": "assistant_message", "token": "Valid"}',
        "",
        "event: done",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Невалидный JSON должен быть пропущен, валидный - обработан
    assert mock_websocket.send_json.call_count == 1
    call_args = mock_websocket.send_json.call_args[0][0]
    assert call_args["token"] == "Valid"


@pytest.mark.asyncio
async def test_process_empty_lines(handler, mock_websocket, mock_response):
    """Тест обработки пустых строк (разделители событий)."""
    lines = [
        "",
        "",
        "event: message",
        'data: {"type": "assistant_message", "token": "Test"}',
        "",
        "",
        "event: done",
        "",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Пустые строки не должны влиять на обработку
    assert mock_websocket.send_json.call_count == 1


@pytest.mark.asyncio
async def test_process_plan_approval_required(handler, mock_websocket, mock_response):
    """Тест обработки plan_approval_required с логированием."""
    lines = [
        "event: message",
        'data: {"type": "plan_approval_required", "approval_request_id": "req_123", "plan_id": "plan_456", "plan_summary": {"goal": "test"}}',
        "",
        "event: done",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Проверяем что сообщение было отправлено
    call_args = mock_websocket.send_json.call_args[0][0]
    assert call_args["type"] == "plan_approval_required"
    assert call_args["approval_request_id"] == "req_123"


@pytest.mark.asyncio
async def test_process_different_event_types(handler, mock_websocket, mock_response):
    """Тест обработки разных типов SSE событий."""
    lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "msg1"}',
        "",
        "event: error",
        'data: {"type": "error", "content": "Error occurred"}',
        "",
        "event: done",
        ""
    ]
    
    async def aiter_lines():
        for line in lines:
            yield line
    
    mock_response.aiter_lines = aiter_lines
    
    await handler.process_stream(mock_response, mock_websocket, "test-session")
    
    # Оба события должны быть обработаны
    assert mock_websocket.send_json.call_count == 2

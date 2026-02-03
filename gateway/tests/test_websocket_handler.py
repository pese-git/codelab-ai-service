"""
Unit тесты для WebSocketHandler.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.websockets import WebSocketDisconnect

from app.services.websocket import WebSocketHandler, WebSocketMessageParser, SSEStreamHandler
from app.models.websocket import WSUserMessage


@pytest.fixture
def mock_parser():
    """Fixture для мокирования MessageParser."""
    parser = MagicMock(spec=WebSocketMessageParser)
    return parser


@pytest.fixture
def mock_sse_handler():
    """Fixture для мокирования SSEStreamHandler."""
    handler = MagicMock(spec=SSEStreamHandler)
    handler.process_stream = AsyncMock()
    return handler


@pytest.fixture
def handler(mock_parser, mock_sse_handler):
    """Fixture для создания WebSocketHandler."""
    return WebSocketHandler(
        message_parser=mock_parser,
        sse_handler=mock_sse_handler,
        agent_runtime_url="http://test-agent:8001",
        internal_api_key="test-key",
        stream_timeout=60.0
    )


@pytest.fixture
def mock_websocket():
    """Fixture для мокирования WebSocket."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_handle_connection_accepts_websocket(handler, mock_websocket, mock_parser):
    """Тест что WebSocket соединение принимается."""
    # Симулируем disconnect после первого сообщения
    mock_websocket.receive_text.side_effect = WebSocketDisconnect()
    
    await handler.handle_connection(mock_websocket, "test-session")
    
    # Проверяем что accept был вызван
    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_handle_connection_parses_message(handler, mock_websocket, mock_parser):
    """Тест что сообщения парсятся через MessageParser."""
    raw_msg = '{"type": "user_message", "content": "Hello", "role": "user"}'
    mock_message = WSUserMessage(type="user_message", content="Hello", role="user")
    
    mock_websocket.receive_text.side_effect = [raw_msg, WebSocketDisconnect()]
    mock_parser.parse.return_value = mock_message
    
    with patch("httpx.AsyncClient"):
        await handler.handle_connection(mock_websocket, "test-session")
    
    # Проверяем что parse был вызван
    mock_parser.parse.assert_called_once_with(raw_msg)


@pytest.mark.asyncio
async def test_handle_connection_sends_error_on_parse_failure(handler, mock_websocket, mock_parser):
    """Тест отправки ошибки при неудачном парсинге."""
    raw_msg = 'invalid json'
    
    mock_websocket.receive_text.side_effect = [raw_msg, WebSocketDisconnect()]
    mock_parser.parse.side_effect = ValueError("Invalid JSON")
    
    await handler.handle_connection(mock_websocket, "test-session")
    
    # Проверяем что error был отправлен
    mock_websocket.send_json.assert_called_once()
    call_args = mock_websocket.send_json.call_args[0][0]
    assert call_args["type"] == "error"
    assert "Invalid JSON" in call_args["content"]


@pytest.mark.asyncio
async def test_handle_connection_forwards_to_agent(handler, mock_websocket, mock_parser, mock_sse_handler):
    """Тест пересылки сообщения в Agent Runtime."""
    raw_msg = '{"type": "user_message", "content": "Hello", "role": "user"}'
    mock_message = WSUserMessage(type="user_message", content="Hello", role="user")
    
    mock_websocket.receive_text.side_effect = [raw_msg, WebSocketDisconnect()]
    mock_parser.parse.return_value = mock_message
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        await handler.handle_connection(mock_websocket, "test-session")
    
    # Проверяем что SSE handler был вызван
    mock_sse_handler.process_stream.assert_called_once()


@pytest.mark.asyncio
async def test_handle_connection_handles_http_error(handler, mock_websocket, mock_parser):
    """Тест обработки HTTP ошибки от Agent Runtime."""
    raw_msg = '{"type": "user_message", "content": "Hello", "role": "user"}'
    mock_message = WSUserMessage(type="user_message", content="Hello", role="user")
    
    mock_websocket.receive_text.side_effect = [raw_msg, WebSocketDisconnect()]
    mock_parser.parse.return_value = mock_message
    
    import httpx
    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    mock_error_response.aread = AsyncMock(return_value=b"Internal error")
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.side_effect = httpx.HTTPStatusError(
            "500 error",
            request=MagicMock(),
            response=mock_error_response
        )
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        await handler.handle_connection(mock_websocket, "test-session")
    
    # Проверяем что error был отправлен
    assert mock_websocket.send_json.call_count >= 1
    # Последний вызов должен быть error
    last_call = mock_websocket.send_json.call_args_list[-1][0][0]
    assert last_call["type"] == "error"


@pytest.mark.asyncio
async def test_handle_connection_handles_generic_error(handler, mock_websocket, mock_parser):
    """Тест обработки общей ошибки."""
    raw_msg = '{"type": "user_message", "content": "Hello", "role": "user"}'
    mock_message = WSUserMessage(type="user_message", content="Hello", role="user")
    
    mock_websocket.receive_text.side_effect = [raw_msg, WebSocketDisconnect()]
    mock_parser.parse.return_value = mock_message
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.side_effect = Exception("Connection failed")
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        await handler.handle_connection(mock_websocket, "test-session")
    
    # Проверяем что error был отправлен
    assert mock_websocket.send_json.call_count >= 1
    last_call = mock_websocket.send_json.call_args_list[-1][0][0]
    assert last_call["type"] == "error"


@pytest.mark.asyncio
async def test_handle_connection_logs_disconnect(handler, mock_websocket):
    """Тест логирования при disconnect."""
    mock_websocket.receive_text.side_effect = WebSocketDisconnect()
    
    # Не должно быть исключения
    await handler.handle_connection(mock_websocket, "test-session")
    
    # WebSocket должен быть принят
    mock_websocket.accept.assert_called_once()

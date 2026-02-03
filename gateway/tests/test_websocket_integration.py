"""
Интеграционные тесты для WebSocket protocol.

Эти тесты проверяют полный flow взаимодействия между IDE и Gateway,
гарантируя что протокол работает корректно после рефакторинга.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Fixture для создания test client."""
    return TestClient(app)


def test_websocket_user_message_flow(client):
    """
    Интеграционный тест: полный flow user_message.
    
    Flow:
    1. IDE подключается к WebSocket
    2. IDE отправляет user_message
    3. Gateway парсит и валидирует сообщение
    4. Gateway пересылает в Agent Runtime (мокируем)
    5. Agent Runtime отвечает через SSE (мокируем)
    6. Gateway пересылает ответ в IDE через WebSocket
    """
    # Мокируем HTTP streaming response от Agent Runtime
    mock_sse_lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Hello", "is_final": false}',
        "",
        "event: message",
        'data: {"type": "assistant_message", "token": " world", "is_final": false}',
        "",
        "event: message",
        'data: {"type": "assistant_message", "token": "!", "is_final": true}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    async def mock_aiter_lines():
        for line in mock_sse_lines:
            yield line
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        # Подключаемся к WebSocket
        with client.websocket_connect("/api/v1/ws/test-session-123") as websocket:
            # Отправляем user_message
            websocket.send_json({
                "type": "user_message",
                "content": "Hello",
                "role": "user"
            })
            
            # Получаем assistant_message chunks
            response1 = websocket.receive_json()
            assert response1["type"] == "assistant_message"
            assert response1["token"] == "Hello"
            assert response1["is_final"] is False
            
            response2 = websocket.receive_json()
            assert response2["type"] == "assistant_message"
            assert response2["token"] == " world"
            
            response3 = websocket.receive_json()
            assert response3["type"] == "assistant_message"
            assert response3["token"] == "!"
            assert response3["is_final"] is True


def test_websocket_tool_call_flow(client):
    """
    Интеграционный тест: flow с tool_call и tool_result.
    
    Flow:
    1. IDE отправляет user_message
    2. Agent отвечает tool_call
    3. IDE отправляет tool_result
    4. Agent отвечает assistant_message
    """
    # Первый SSE stream - tool_call
    mock_sse_lines_1 = [
        "event: message",
        'data: {"type": "tool_call", "call_id": "call_abc123", "tool_name": "read_file", "arguments": {"path": "test.py"}}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    # Второй SSE stream - assistant_message после tool_result
    mock_sse_lines_2 = [
        "event: message",
        'data: {"type": "assistant_message", "token": "File content received", "is_final": true}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    call_count = [0]
    
    async def mock_aiter_lines():
        call_count[0] += 1
        lines = mock_sse_lines_1 if call_count[0] == 1 else mock_sse_lines_2
        for line in lines:
            yield line
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        with client.websocket_connect("/api/v1/ws/test-session-456") as websocket:
            # 1. Отправляем user_message
            websocket.send_json({
                "type": "user_message",
                "content": "Read test.py",
                "role": "user"
            })
            
            # 2. Получаем tool_call
            response = websocket.receive_json()
            assert response["type"] == "tool_call"
            assert response["call_id"] == "call_abc123"
            assert response["tool_name"] == "read_file"
            
            # 3. Отправляем tool_result
            websocket.send_json({
                "type": "tool_result",
                "call_id": "call_abc123",
                "result": {"content": "file content"}
            })
            
            # 4. Получаем assistant_message
            response = websocket.receive_json()
            assert response["type"] == "assistant_message"
            assert response["token"] == "File content received"


def test_websocket_invalid_message(client):
    """
    Интеграционный тест: обработка невалидного сообщения.
    
    Gateway должен отправить error response и продолжить работу.
    """
    with client.websocket_connect("/api/v1/ws/test-session-789") as websocket:
        # Отправляем невалидное сообщение (без type)
        websocket.send_text('{"content": "Hello"}')
        
        # Должны получить error
        response = websocket.receive_json()
        assert response["type"] == "error"
        assert "Message type is required" in response["content"]


def test_websocket_unknown_message_type(client):
    """
    Интеграционный тест: обработка неизвестного типа сообщения.
    """
    with client.websocket_connect("/api/v1/ws/test-session-999") as websocket:
        # Отправляем сообщение с неизвестным типом
        websocket.send_json({
            "type": "unknown_type",
            "data": "something"
        })
        
        # Должны получить error
        response = websocket.receive_json()
        assert response["type"] == "error"
        assert "Unknown message type" in response["content"]


def test_websocket_plan_decision_flow(client):
    """
    Интеграционный тест: flow с plan approval.
    
    Flow:
    1. IDE отправляет user_message
    2. Agent отвечает plan_approval_required
    3. IDE отправляет plan_decision
    4. Agent продолжает выполнение
    """
    # Первый SSE stream - plan_approval_required
    mock_sse_lines_1 = [
        "event: message",
        'data: {"type": "plan_approval_required", "content": "Plan requires approval", "approval_request_id": "plan_req_123", "plan_id": "plan_456", "plan_summary": {"goal": "Create login form"}}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    # Второй SSE stream - продолжение после approval
    mock_sse_lines_2 = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Executing plan...", "is_final": true}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    call_count = [0]
    
    async def mock_aiter_lines():
        call_count[0] += 1
        lines = mock_sse_lines_1 if call_count[0] == 1 else mock_sse_lines_2
        for line in lines:
            yield line
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        with client.websocket_connect("/api/v1/ws/test-plan-session") as websocket:
            # 1. Отправляем user_message
            websocket.send_json({
                "type": "user_message",
                "content": "Create login form",
                "role": "user"
            })
            
            # 2. Получаем plan_approval_required
            response = websocket.receive_json()
            assert response["type"] == "plan_approval_required"
            assert response["approval_request_id"] == "plan_req_123"
            assert response["plan_id"] == "plan_456"
            
            # 3. Отправляем plan_decision
            websocket.send_json({
                "type": "plan_decision",
                "approval_request_id": "plan_req_123",
                "decision": "approve"
            })
            
            # 4. Получаем продолжение
            response = websocket.receive_json()
            assert response["type"] == "assistant_message"
            assert "Executing plan" in response["token"]


def test_websocket_hitl_decision_flow(client):
    """
    Интеграционный тест: flow с HITL approval.
    
    Flow:
    1. IDE отправляет user_message
    2. Agent отвечает tool_call с requires_approval=true
    3. IDE отправляет hitl_decision
    4. Agent выполняет tool
    """
    # Первый SSE stream - tool_call с approval
    mock_sse_lines_1 = [
        "event: message",
        'data: {"type": "tool_call", "call_id": "call_hitl_123", "tool_name": "execute_command", "arguments": {"command": "rm -rf /"}, "requires_approval": true}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    # Второй SSE stream - результат после approval
    mock_sse_lines_2 = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Command approved and executed", "is_final": true}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    call_count = [0]
    
    async def mock_aiter_lines():
        call_count[0] += 1
        lines = mock_sse_lines_1 if call_count[0] == 1 else mock_sse_lines_2
        for line in lines:
            yield line
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        with client.websocket_connect("/api/v1/ws/test-hitl-session") as websocket:
            # 1. Отправляем user_message
            websocket.send_json({
                "type": "user_message",
                "content": "Delete all files",
                "role": "user"
            })
            
            # 2. Получаем tool_call с requires_approval
            response = websocket.receive_json()
            assert response["type"] == "tool_call"
            assert response["call_id"] == "call_hitl_123"
            assert response["requires_approval"] is True
            
            # 3. Отправляем hitl_decision
            websocket.send_json({
                "type": "hitl_decision",
                "call_id": "call_hitl_123",
                "decision": "approve"
            })
            
            # 4. Получаем результат
            response = websocket.receive_json()
            assert response["type"] == "assistant_message"


def test_websocket_switch_agent_flow(client):
    """
    Интеграционный тест: переключение агента.
    
    Flow:
    1. IDE отправляет switch_agent
    2. Agent отвечает agent_switched
    """
    mock_sse_lines = [
        "event: message",
        'data: {"type": "agent_switched", "content": "Switched to debug agent", "from_agent": "code", "to_agent": "debug", "reason": "User requested"}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    async def mock_aiter_lines():
        for line in mock_sse_lines:
            yield line
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        with client.websocket_connect("/api/v1/ws/test-switch-session") as websocket:
            # Отправляем switch_agent
            websocket.send_json({
                "type": "switch_agent",
                "agent_type": "debug",
                "content": "Switch to debug mode"
            })
            
            # Получаем agent_switched
            response = websocket.receive_json()
            assert response["type"] == "agent_switched"
            assert response["from_agent"] == "code"
            assert response["to_agent"] == "debug"


def test_websocket_error_handling(client):
    """
    Интеграционный тест: обработка ошибок от Agent Runtime.
    """
    mock_response = MagicMock()
    mock_response.status_code = 500
    
    async def mock_aread():
        return b'{"error": "Internal server error"}'
    
    mock_response.aread = mock_aread
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.side_effect = Exception("Connection failed")
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        with client.websocket_connect("/api/v1/ws/test-error-session") as websocket:
            # Отправляем сообщение
            websocket.send_json({
                "type": "user_message",
                "content": "Test",
                "role": "user"
            })
            
            # Должны получить error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "error" in response["content"].lower()


def test_websocket_null_filtering(client):
    """
    Интеграционный тест: фильтрация null значений.
    
    Gateway должен фильтровать null значения перед отправкой в IDE.
    """
    mock_sse_lines = [
        "event: message",
        'data: {"type": "assistant_message", "token": "Hello", "is_final": false, "metadata": null, "extra": null}',
        "",
        "event: done",
        "data: [DONE]",
        ""
    ]
    
    async def mock_aiter_lines():
        for line in mock_sse_lines:
            yield line
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None
        
        mock_client.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_context
        )
        
        with client.websocket_connect("/api/v1/ws/test-filter-session") as websocket:
            websocket.send_json({
                "type": "user_message",
                "content": "Test",
                "role": "user"
            })
            
            response = websocket.receive_json()
            
            # Проверяем что null поля отфильтрованы
            assert response["type"] == "assistant_message"
            assert response["token"] == "Hello"
            assert "metadata" not in response
            assert "extra" not in response

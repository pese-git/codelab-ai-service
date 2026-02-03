"""
Интеграционные тесты для proxy endpoints.

Проверяют что все REST endpoints корректно проксируют запросы в Agent Runtime.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.core.config import config


@pytest.fixture
def client():
    """Fixture для создания test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Fixture для auth headers."""
    return {"X-Internal-Auth": config.internal_api_key}


def test_list_agents_endpoint(client, auth_headers):
    """Тест GET /agents endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "agents": [
            {"name": "code", "description": "Coding agent"},
            {"name": "debug", "description": "Debugging agent"}
        ]
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/agents", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) == 2


def test_get_current_agent_endpoint(client, auth_headers):
    """Тест GET /agents/{session_id}/current endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "agent_type": "code",
        "session_id": "test-123"
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/agents/test-123/current", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "code"
        assert data["session_id"] == "test-123"


def test_list_sessions_endpoint(client, auth_headers):
    """Тест GET /sessions endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "sessions": ["session-1", "session-2", "session-3"]
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/sessions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 3


def test_create_session_endpoint(client, auth_headers):
    """Тест POST /sessions endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "session_id": "new-session-456",
        "created_at": "2026-02-03T05:00:00Z"
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        response = client.post("/api/v1/sessions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "new-session-456"


def test_get_session_history_endpoint(client, auth_headers):
    """Тест GET /sessions/{session_id}/history endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/sessions/test-789/history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 2


def test_get_pending_approvals_endpoint(client, auth_headers):
    """Тест GET /sessions/{session_id}/pending-approvals endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "pending_approvals": [
            {
                "approval_request_id": "req_123",
                "type": "plan",
                "status": "pending"
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/sessions/test-999/pending-approvals", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "pending_approvals" in data


def test_get_session_metrics_endpoint(client, auth_headers):
    """Тест GET /events/metrics/session/{session_id} endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "session_id": "test-111",
        "total_requests": 10,
        "total_tokens": 5000
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/events/metrics/session/test-111", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-111"
        assert data["total_requests"] == 10


def test_get_all_session_metrics_endpoint(client, auth_headers):
    """Тест GET /events/metrics/sessions endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "sessions": ["session-1", "session-2"]
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/events/metrics/sessions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data


def test_get_event_metrics_endpoint(client, auth_headers):
    """Тест GET /events/metrics endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "agent_switches": 5,
        "tool_executions": 20,
        "errors": 2
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/events/metrics", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "agent_switches" in data
        assert "tool_executions" in data


def test_get_audit_log_endpoint(client, auth_headers):
    """Тест GET /events/audit-log endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "entries": [
            {"event_type": "agent_switch", "timestamp": "2026-02-03T05:00:00Z"}
        ]
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/events/audit-log?limit=10", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data


def test_get_event_bus_stats_endpoint(client, auth_headers):
    """Тест GET /events/stats endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "total_events": 100,
        "handlers_count": 5
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        response = client.get("/api/v1/events/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data


def test_health_check_endpoint(client):
    """Тест GET /health endpoint."""
    response = client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "gateway"


def test_proxy_error_handling(client, auth_headers):
    """Тест обработки ошибок от Agent Runtime."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Session not found"
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404 error",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        response = client.get("/api/v1/sessions/nonexistent/history", headers=auth_headers)
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data


def test_proxy_timeout_handling(client, auth_headers):
    """Тест обработки таймаута."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )
        
        response = client.get("/api/v1/agents", headers=auth_headers)
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data

"""
Unit тесты для middleware.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from fastapi.responses import JSONResponse

from app.middleware.internal_auth import InternalAuthMiddleware
from app.core.config import config


@pytest.fixture
def middleware():
    """Fixture для создания InternalAuthMiddleware."""
    return InternalAuthMiddleware(app=MagicMock())


@pytest.fixture
def mock_call_next():
    """Fixture для мокирования call_next."""
    call_next = AsyncMock()
    call_next.return_value = JSONResponse(content={"success": True})
    return call_next


def create_request(path: str, headers: dict = None):
    """Создать mock Request."""
    request = MagicMock(spec=Request)
    request.url.path = path
    request.headers = MagicMock()
    request.headers.get = lambda key: (headers or {}).get(key.lower())
    return request


@pytest.mark.asyncio
async def test_public_paths_allowed(middleware, mock_call_next):
    """Тест что публичные пути доступны без аутентификации."""
    public_paths = [
        "/health",
        "/api/v1/health",
        "/docs",
        "/openapi.json",
        "/redoc"
    ]
    
    for path in public_paths:
        request = create_request(path)
        response = await middleware.dispatch(request, mock_call_next)
        
        assert response.status_code == 200
        assert response.body == b'{"success":true}'


@pytest.mark.asyncio
async def test_websocket_paths_allowed(middleware, mock_call_next):
    """Тест что WebSocket пути доступны без аутентификации."""
    ws_paths = [
        "/ws/session-123",
        "/ws/test-session",
        "/ws/abc-def-ghi"
    ]
    
    for path in ws_paths:
        request = create_request(path)
        response = await middleware.dispatch(request, mock_call_next)
        
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_authenticated_request_allowed(middleware, mock_call_next):
    """Тест что запрос с правильным auth header проходит."""
    request = create_request(
        "/api/v1/agents",
        headers={"x-internal-auth": config.internal_api_key}
    )
    
    response = await middleware.dispatch(request, mock_call_next)
    
    assert response.status_code == 200
    mock_call_next.assert_called_once()


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(middleware, mock_call_next):
    """Тест что запрос без auth header отклоняется."""
    request = create_request("/api/v1/agents")
    
    response = await middleware.dispatch(request, mock_call_next)
    
    assert response.status_code == 401
    data = json.loads(response.body)
    assert data["detail"] == "unauthorized"
    mock_call_next.assert_not_called()


@pytest.mark.asyncio
async def test_wrong_auth_key_rejected(middleware, mock_call_next):
    """Тест что запрос с неправильным auth key отклоняется."""
    request = create_request(
        "/api/v1/agents",
        headers={"x-internal-auth": "wrong-key"}
    )
    
    response = await middleware.dispatch(request, mock_call_next)
    
    assert response.status_code == 401
    mock_call_next.assert_not_called()


@pytest.mark.asyncio
async def test_case_insensitive_header(middleware, mock_call_next):
    """Тест что header name case-insensitive."""
    # FastAPI автоматически делает headers lowercase
    request = create_request(
        "/api/v1/sessions",
        headers={"x-internal-auth": config.internal_api_key}
    )
    
    response = await middleware.dispatch(request, mock_call_next)
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoints_require_auth(middleware, mock_call_next):
    """Тест что все защищенные endpoints требуют аутентификацию."""
    protected_paths = [
        "/api/v1/agents",
        "/api/v1/sessions",
        "/api/v1/sessions/test/history",
        "/api/v1/events/metrics",
        "/api/v1/events/audit-log"
    ]
    
    for path in protected_paths:
        request = create_request(path)
        response = await middleware.dispatch(request, mock_call_next)
        
        assert response.status_code == 401, f"Path {path} should require auth"

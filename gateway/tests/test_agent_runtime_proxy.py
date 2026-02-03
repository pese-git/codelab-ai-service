"""
Unit тесты для AgentRuntimeProxy.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from fastapi.responses import JSONResponse

from app.services.agent_runtime_proxy import AgentRuntimeProxy


@pytest.fixture
def proxy():
    """Fixture для создания AgentRuntimeProxy."""
    return AgentRuntimeProxy(
        base_url="http://test-agent:8001",
        internal_api_key="test-key",
        timeout=10.0
    )


@pytest.mark.asyncio
async def test_get_success(proxy):
    """Тест успешного GET запроса."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"agents": ["code", "debug"]}
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        result = await proxy.get("/agents")
        
        assert result == {"agents": ["code", "debug"]}
        mock_client.return_value.__aenter__.return_value.get.assert_called_once_with(
            "http://test-agent:8001/agents",
            params=None,
            headers={"X-Internal-Auth": "test-key"}
        )


@pytest.mark.asyncio
async def test_get_with_params(proxy):
    """Тест GET запроса с параметрами."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"sessions": []}
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        result = await proxy.get("/sessions", params={"limit": 10})
        
        assert result == {"sessions": []}
        mock_client.return_value.__aenter__.return_value.get.assert_called_once_with(
            "http://test-agent:8001/sessions",
            params={"limit": 10},
            headers={"X-Internal-Auth": "test-key"}
        )


@pytest.mark.asyncio
async def test_post_success(proxy):
    """Тест успешного POST запроса."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"session_id": "test-123"}
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        result = await proxy.post("/sessions")
        
        assert result == {"session_id": "test-123"}
        mock_client.return_value.__aenter__.return_value.post.assert_called_once_with(
            "http://test-agent:8001/sessions",
            json=None,
            headers={"X-Internal-Auth": "test-key"}
        )


@pytest.mark.asyncio
async def test_post_with_json(proxy):
    """Тест POST запроса с JSON данными."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "created"}
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        result = await proxy.post("/sessions", json={"name": "test"})
        
        assert result == {"status": "created"}
        mock_client.return_value.__aenter__.return_value.post.assert_called_once_with(
            "http://test-agent:8001/sessions",
            json={"name": "test"},
            headers={"X-Internal-Auth": "test-key"}
        )


@pytest.mark.asyncio
async def test_get_http_error(proxy):
    """Тест обработки HTTP ошибки."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404 error",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        result = await proxy.get("/agents/unknown")
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 404


@pytest.mark.asyncio
async def test_get_generic_error(proxy):
    """Тест обработки общей ошибки."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Connection error")
        )
        
        result = await proxy.get("/agents")
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


@pytest.mark.asyncio
async def test_post_http_error(proxy):
    """Тест обработки HTTP ошибки в POST."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "400 error",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        result = await proxy.post("/sessions", json={"invalid": "data"})
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 400


@pytest.mark.asyncio
async def test_base_url_trailing_slash(proxy):
    """Тест что trailing slash в base_url удаляется."""
    proxy_with_slash = AgentRuntimeProxy(
        base_url="http://test-agent:8001/",
        internal_api_key="test-key",
        timeout=10.0
    )
    
    assert proxy_with_slash._base_url == "http://test-agent:8001"

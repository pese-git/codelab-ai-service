"""
Unit tests for InternalAuthMiddleware.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from app.middleware.internal_auth import InternalAuthMiddleware


@pytest.fixture
def app():
    """Create a test FastAPI app with middleware"""
    app = FastAPI()
    
    @app.get("/protected")
    async def protected_endpoint():
        return {"message": "success"}
    
    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}
    
    return app


@pytest.fixture
def client_with_middleware(app):
    """Create test client with middleware"""
    app.add_middleware(InternalAuthMiddleware)
    return TestClient(app)


def test_public_path_health_no_auth_required(client_with_middleware):
    """Test that /health endpoint does not require authentication"""
    response = client_with_middleware.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_protected_endpoint_with_valid_auth(client_with_middleware):
    """Test protected endpoint with valid authentication"""
    response = client_with_middleware.get(
        "/protected",
        headers={"X-Internal-Auth": "test-key"}
    )
    
    assert response.status_code == 200
    assert response.json() == {"message": "success"}


def test_protected_endpoint_without_auth_header(client_with_middleware):
    """Test protected endpoint without authentication header"""
    response = client_with_middleware.get("/protected")
    
    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_protected_endpoint_with_invalid_auth(client_with_middleware):
    """Test protected endpoint with invalid authentication"""
    response = client_with_middleware.get(
        "/protected",
        headers={"X-Internal-Auth": "wrong-key"}
    )
    
    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_protected_endpoint_with_empty_auth(client_with_middleware):
    """Test protected endpoint with empty authentication header"""
    response = client_with_middleware.get(
        "/protected",
        headers={"X-Internal-Auth": ""}
    )
    
    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_case_insensitive_header_name(client_with_middleware):
    """Test that header name is case-insensitive"""
    # FastAPI/Starlette normalizes headers to lowercase
    response = client_with_middleware.get(
        "/protected",
        headers={"x-internal-auth": "test-key"}
    )
    
    assert response.status_code == 200


def test_all_public_paths():
    """Test all defined public paths"""
    public_paths = [
        "/health",
        "/llm/models",
        "/openapi.json",
        "/redoc",
        "/favicon.ico"
    ]
    
    app = FastAPI()
    
    # Add dummy endpoints for all public paths
    for path in public_paths:
        # Use closure to capture path
        def make_endpoint(p):
            @app.get(p)
            async def endpoint():
                return {"ok": True}
            return endpoint
        make_endpoint(path)
    
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        app.add_middleware(InternalAuthMiddleware)
        client = TestClient(app)
        
        # All public paths should be accessible without auth
        for path in public_paths:
            response = client.get(path)
            assert response.status_code == 200, f"Path {path} should be public"


@pytest.mark.asyncio
async def test_middleware_dispatch_calls_next():
    """Test that middleware calls next handler for valid requests"""
    middleware = InternalAuthMiddleware(app=MagicMock())
    
    # Mock request with valid auth
    request = MagicMock(spec=Request)
    request.url.path = "/protected"
    request.headers.get.return_value = "test-key"
    
    # Mock call_next
    call_next = AsyncMock(return_value=JSONResponse({"success": True}))
    
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        response = await middleware.dispatch(request, call_next)
    
    # Verify call_next was called
    call_next.assert_called_once_with(request)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_middleware_dispatch_public_path():
    """Test middleware dispatch for public path"""
    middleware = InternalAuthMiddleware(app=MagicMock())
    
    # Mock request to public path
    request = MagicMock(spec=Request)
    request.url.path = "/health"
    
    # Mock call_next
    call_next = AsyncMock(return_value=JSONResponse({"status": "healthy"}))
    
    response = await middleware.dispatch(request, call_next)
    
    # Should call next without checking auth
    call_next.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_middleware_dispatch_invalid_auth():
    """Test middleware dispatch with invalid auth"""
    middleware = InternalAuthMiddleware(app=MagicMock())
    
    # Mock request with invalid auth
    request = MagicMock(spec=Request)
    request.url.path = "/protected"
    request.headers.get.return_value = "wrong-key"
    
    # Mock call_next (should not be called)
    call_next = AsyncMock()
    
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        response = await middleware.dispatch(request, call_next)
    
    # Verify call_next was NOT called
    call_next.assert_not_called()
    
    # Verify 401 response
    assert response.status_code == 401
    assert isinstance(response, JSONResponse)


@pytest.mark.asyncio
async def test_middleware_dispatch_none_auth_header():
    """Test middleware dispatch when auth header is None"""
    middleware = InternalAuthMiddleware(app=MagicMock())
    
    # Mock request with no auth header
    request = MagicMock(spec=Request)
    request.url.path = "/protected"
    request.headers.get.return_value = None
    
    call_next = AsyncMock()
    
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        response = await middleware.dispatch(request, call_next)
    
    # Should return 401
    assert response.status_code == 401
    call_next.assert_not_called()


def test_middleware_with_different_api_keys():
    """Test middleware with different API key configurations"""
    test_keys = [
        "simple-key",
        "complex-key-with-dashes-123",
        "key_with_underscores",
        "VeryLongKeyWith1234567890AndSpecialChars"
    ]
    
    for test_key in test_keys:
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}
        
        with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", test_key):
            app.add_middleware(InternalAuthMiddleware)
            client = TestClient(app)
            
            # Should work with correct key
            response = client.get("/test", headers={"X-Internal-Auth": test_key})
            assert response.status_code == 200, f"Failed for key: {test_key}"
            
            # Should fail with wrong key
            response = client.get("/test", headers={"X-Internal-Auth": "wrong"})
            assert response.status_code == 401, f"Should fail for wrong key: {test_key}"


def test_middleware_logging(client_with_middleware, caplog):
    """Test that middleware logs authentication attempts"""
    import logging
    
    with caplog.at_level(logging.DEBUG):
        # Valid auth
        client_with_middleware.get(
            "/protected",
            headers={"X-Internal-Auth": "test-key"}
        )
        
        # Check for debug log
        assert any("AUTH" in record.message for record in caplog.records)
    
    caplog.clear()
    
    with caplog.at_level(logging.WARNING):
        # Invalid auth
        client_with_middleware.get(
            "/protected",
            headers={"X-Internal-Auth": "wrong-key"}
        )
        
        # Check for warning log
        assert any("AUTH_FAIL" in record.message for record in caplog.records)


def test_middleware_preserves_response_content(client_with_middleware):
    """Test that middleware preserves response content from endpoint"""
    response = client_with_middleware.get(
        "/protected",
        headers={"X-Internal-Auth": "test-key"}
    )
    
    # Should return the actual endpoint response
    assert response.json() == {"message": "success"}


def test_middleware_with_post_request():
    """Test middleware with POST request"""
    app = FastAPI()
    
    @app.post("/protected")
    async def protected_post():
        return {"created": True}
    
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        app.add_middleware(InternalAuthMiddleware)
        client = TestClient(app)
        
        # Should require auth for POST too
        response = client.post("/protected")
        assert response.status_code == 401
        
        # Should work with valid auth
        response = client.post(
            "/protected",
            headers={"X-Internal-Auth": "test-key"}
        )
        assert response.status_code == 200

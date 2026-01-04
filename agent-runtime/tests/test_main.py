"""
Unit tests for main endpoints with mocks.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import Message, StreamChunk


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def mock_session_manager():
    """Mock session manager"""
    with patch("app.api.v1.endpoints.session_manager") as mock:
        yield mock


@pytest.fixture
def mock_stream_response():
    """Mock stream_response function"""
    with patch("app.api.v1.endpoints.stream_response") as mock:
        yield mock


def test_health(client):
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "agent-runtime"


def test_agent_message_stream_success(client, mock_session_manager, mock_stream_response):
    """Test successful agent message stream with mocked dependencies"""
    # Setup mocks
    session_id = "test_session"
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session_manager.get_or_create.return_value = mock_session
    mock_session_manager.get_history.return_value = [
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock stream response
    async def mock_stream():
        yield StreamChunk(
            type="assistant_message",
            content="Test response",
            token="Test response",
            is_final=True
        )
    
    mock_stream_response.return_value = mock_stream()
    
    # Make request
    payload = {
        "session_id": session_id,
        "message": {
            "type": "user_message",
            "content": "Hello"
        }
    }
    
    # SSE endpoint returns 200 immediately and streams data
    response = client.post(
        "/agent/message/stream",
        json=payload,
        headers={"X-Internal-Auth": "test-key"},
    )
    
    # SSE endpoint should return 200 and start streaming
    assert response.status_code == 200


def test_agent_message_stream_missing_session_id(client):
    """Test agent message stream with missing session_id"""
    payload = {
        "message": {
            "type": "user_message",
            "content": "Hello"
        }
    }
    
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        response = client.post(
            "/agent/message/stream",
            json=payload,
            headers={"X-Internal-Auth": "test-key"},
        )
    
    assert response.status_code == 422


def test_agent_message_stream_unauthorized(client):
    """Test agent message stream without auth header"""
    payload = {
        "session_id": "test_session",
        "message": {
            "type": "user_message",
            "content": "Hello"
        }
    }
    
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        response = client.post(
            "/agent/message/stream",
            json=payload,
            headers={"X-Internal-Auth": "wrong-key"},
        )
    
    assert response.status_code == 401


# Note: SSE streaming tests are complex with TestClient due to async event loop issues
# The streaming functionality is covered by unit tests in test_llm_stream_service.py

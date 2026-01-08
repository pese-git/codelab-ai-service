"""
Pytest configuration and fixtures.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture(scope="session", autouse=True)
def mock_internal_api_key():
    """Mock INTERNAL_API_KEY for all tests"""
    with patch("app.core.config.AppConfig.INTERNAL_API_KEY", "test-key"):
        yield


@pytest_asyncio.fixture(scope="function", autouse=True)
async def mock_database():
    """Mock database for all tests to avoid DB initialization errors"""
    # Mock get_db to return a mock database session
    mock_db = AsyncMock()
    
    # Mock execute to return a mock result with proper methods
    # scalar_one_or_none should return None directly (not a coroutine)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    mock_result.all = MagicMock(return_value=[])
    
    # execute returns the mock_result directly (not async)
    async def mock_execute(*args, **kwargs):
        return mock_result
    
    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.add = MagicMock()
    
    async def mock_get_db():
        yield mock_db
    
    # Mock database service methods
    mock_db_service = AsyncMock()
    mock_db_service.list_all_sessions = AsyncMock(return_value=[])
    mock_db_service.load_session = AsyncMock(return_value=None)
    mock_db_service.save_session = AsyncMock()
    mock_db_service.delete_session = AsyncMock()
    mock_db_service.load_agent_context = AsyncMock(return_value=None)
    mock_db_service.save_agent_context = AsyncMock()
    
    with patch("app.services.database.get_db", mock_get_db):
        with patch("app.services.session_manager_async.get_db", mock_get_db):
            with patch("app.services.agent_context_async.get_db", mock_get_db):
                with patch("app.services.database.get_database_service", return_value=mock_db_service):
                    with patch("app.services.session_manager_async.get_database_service", return_value=mock_db_service):
                        with patch("app.services.agent_context_async.get_database_service", return_value=mock_db_service):
                            yield mock_db

"""
Pytest configuration and fixtures.
"""
import pytest
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def mock_internal_api_key():
    """Mock INTERNAL_API_KEY for all tests"""
    with patch("app.core.config.AppConfig.INTERNAL_API_KEY", "test-key"):
        yield

"""
Unit тесты для AppConfig.
"""

import pytest
import os
from pydantic import ValidationError

from app.core.config import AppConfig


def test_config_defaults(monkeypatch):
    """Тест значений по умолчанию."""
    # Очищаем все env переменные для чистого теста
    for key in list(os.environ.keys()):
        if key.startswith("GATEWAY__"):
            monkeypatch.delenv(key, raising=False)
    
    # Отключаем загрузку .env файла
    config = AppConfig(_env_file=None)
    
    assert config.agent_url == "http://localhost:8001"
    assert config.internal_api_key == "change-me-internal-key"
    assert config.request_timeout == 30.0
    assert config.agent_stream_timeout == 60.0
    assert config.log_level == "INFO"
    assert config.use_jwt_auth is False
    assert config.version == "0.1.0"


def test_config_from_env(monkeypatch):
    """Тест загрузки конфигурации из переменных окружения."""
    monkeypatch.setenv("GATEWAY__AGENT_URL", "http://custom-agent:9000")
    monkeypatch.setenv("GATEWAY__INTERNAL_API_KEY", "custom-key")
    monkeypatch.setenv("GATEWAY__REQUEST_TIMEOUT", "45.0")
    monkeypatch.setenv("GATEWAY__LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("GATEWAY__USE_JWT_AUTH", "true")
    
    config = AppConfig()
    
    assert config.agent_url == "http://custom-agent:9000"
    assert config.internal_api_key == "custom-key"
    assert config.request_timeout == 45.0
    assert config.log_level == "DEBUG"
    assert config.use_jwt_auth is True


def test_config_timeout_validation():
    """Тест валидации таймаутов."""
    # Слишком маленький таймаут
    with pytest.raises(ValidationError):
        AppConfig(request_timeout=0.5)
    
    # Слишком большой таймаут
    with pytest.raises(ValidationError):
        AppConfig(request_timeout=400.0)
    
    # Валидные значения
    config = AppConfig(request_timeout=1.0)
    assert config.request_timeout == 1.0
    
    config = AppConfig(request_timeout=300.0)
    assert config.request_timeout == 300.0


def test_config_log_level_validation():
    """Тест валидации уровня логирования."""
    # Валидные уровни
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        config = AppConfig(log_level=level)
        assert config.log_level == level
    
    # Невалидный уровень
    with pytest.raises(ValidationError):
        AppConfig(log_level="INVALID")


def test_config_jwks_url_property():
    """Тест property jwks_url."""
    config = AppConfig(auth_service_url="http://auth:8003")
    
    assert config.jwks_url == "http://auth:8003/.well-known/jwks.json"


def test_config_backward_compatibility():
    """Тест обратной совместимости (uppercase properties)."""
    config = AppConfig(
        agent_url="http://test:8001",
        internal_api_key="test-key",
        version="1.0.0"
    )
    
    # Lowercase (новый стиль)
    assert config.agent_url == "http://test:8001"
    assert config.internal_api_key == "test-key"
    assert config.version == "1.0.0"
    
    # Uppercase (старый стиль, для обратной совместимости)
    assert config.AGENT_URL == "http://test:8001"
    assert config.INTERNAL_API_KEY == "test-key"
    assert config.VERSION == "1.0.0"


def test_config_case_insensitive_env(monkeypatch):
    """Тест case-insensitive загрузки из env."""
    # Pydantic Settings поддерживает case-insensitive env vars
    monkeypatch.setenv("gateway__agent_url", "http://lowercase:8001")
    
    config = AppConfig()
    
    assert config.agent_url == "http://lowercase:8001"


def test_config_extra_fields_ignored():
    """Тест что extra поля игнорируются."""
    # extra="ignore" в model_config
    config = AppConfig(unknown_field="value")
    
    # Не должно быть ошибки, поле просто игнорируется
    assert not hasattr(config, "unknown_field")


def test_config_stream_timeout_validation():
    """Тест валидации stream таймаута."""
    # Валидные значения
    config = AppConfig(agent_stream_timeout=60.0)
    assert config.agent_stream_timeout == 60.0
    
    config = AppConfig(agent_stream_timeout=600.0)
    assert config.agent_stream_timeout == 600.0
    
    # Невалидные значения
    with pytest.raises(ValidationError):
        AppConfig(agent_stream_timeout=0.5)
    
    with pytest.raises(ValidationError):
        AppConfig(agent_stream_timeout=700.0)


def test_config_boolean_parsing(monkeypatch):
    """Тест парсинга boolean значений из env."""
    # True варианты
    for value in ["true", "True", "TRUE", "1", "yes"]:
        monkeypatch.setenv("GATEWAY__USE_JWT_AUTH", value)
        config = AppConfig()
        assert config.use_jwt_auth is True
    
    # False варианты
    for value in ["false", "False", "FALSE", "0", "no"]:
        monkeypatch.setenv("GATEWAY__USE_JWT_AUTH", value)
        config = AppConfig()
        assert config.use_jwt_auth is False

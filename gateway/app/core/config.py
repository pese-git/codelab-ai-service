import logging
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Конфигурация Gateway сервиса с валидацией через Pydantic."""
    
    model_config = SettingsConfigDict(
        env_prefix="GATEWAY__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Agent Runtime
    agent_url: str = Field(
        default="http://localhost:8001",
        description="URL Agent Runtime сервиса"
    )
    internal_api_key: str = Field(
        default="change-me-internal-key",
        description="Ключ для внутренней аутентификации"
    )
    
    # Timeouts
    request_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Таймаут для обычных запросов (сек)"
    )
    agent_stream_timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=600.0,
        description="Таймаут для streaming запросов (сек)"
    )
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Уровень логирования"
    )
    
    # Auth
    use_jwt_auth: bool = Field(
        default=False,
        description="Использовать JWT аутентификацию"
    )
    jwt_issuer: str = Field(
        default="https://auth.codelab.local",
        description="JWT issuer"
    )
    jwt_audience: str = Field(
        default="codelab-api",
        description="JWT audience"
    )
    auth_service_url: str = Field(
        default="http://auth-service:8003",
        description="URL Auth сервиса"
    )
    
    # Version
    version: str = Field(
        default="0.1.0",
        description="Версия сервиса"
    )
    
    @property
    def jwks_url(self) -> str:
        """URL для получения JWKS."""
        return f"{self.auth_service_url}/.well-known/jwks.json"
    
    # Backward compatibility properties (uppercase)
    @property
    def AGENT_URL(self) -> str:
        return self.agent_url
    
    @property
    def INTERNAL_API_KEY(self) -> str:
        return self.internal_api_key
    
    @property
    def LOG_LEVEL(self) -> str:
        return self.log_level
    
    @property
    def REQUEST_TIMEOUT(self) -> float:
        return self.request_timeout
    
    @property
    def AGENT_STREAM_TIMEOUT(self) -> float:
        return self.agent_stream_timeout
    
    @property
    def VERSION(self) -> str:
        return self.version
    
    @property
    def AUTH_SERVICE_URL(self) -> str:
        return self.auth_service_url
    
    @property
    def USE_JWT_AUTH(self) -> bool:
        return self.use_jwt_auth
    
    @property
    def JWT_ISSUER(self) -> str:
        return self.jwt_issuer
    
    @property
    def JWT_AUDIENCE(self) -> str:
        return self.jwt_audience
    
    @property
    def JWKS_URL(self) -> str:
        return self.jwks_url


# Создаем singleton instance
config = AppConfig()

# Настраиваем логирование
logging.basicConfig(level=config.log_level)
logger = logging.getLogger("gateway")

"""Application configuration"""

import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_prefix="AUTH_SERVICE__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: str = "development"
    port: int = 8003

    # Database
    db_url: str = "sqlite:///data/auth.db"

    # Redis
    redis_url: str = "redis://localhost:6379/1"

    # JWT Settings
    jwt_issuer: str = "https://auth.codelab.local"
    jwt_audience: str = "codelab-api"
    access_token_lifetime: int = 900  # 15 minutes
    refresh_token_lifetime: int = 2592000  # 30 days

    # RSA Keys
    private_key_path: str = "/app/keys/private_key.pem"
    public_key_path: str = "/app/keys/public_key.pem"

    # Security
    enable_rate_limiting: bool = True  # Enable/disable rate limiting
    rate_limit_per_ip: int = 5  # requests per minute
    rate_limit_per_username: int = 10  # requests per hour
    brute_force_threshold: int = 5  # failed attempts
    brute_force_lockout_duration: int = 900  # 15 minutes in seconds

    # Logging
    log_level: str = "DEBUG"

    # Version
    version: str = "0.1.0"

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"


# Create settings instance
settings = Settings()

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("auth-service")

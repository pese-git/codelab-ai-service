"""
Application configuration for agent runtime service.

Loads configuration from environment variables with sensible defaults.
"""
import logging
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class AppConfig:
    """Application configuration loaded from environment variables"""
    
    # Service URLs
    LLM_PROXY_URL: str = os.getenv(
        "AGENT_RUNTIME__LLM_PROXY_URL",
        "http://localhost:8002"
    )
    GATEWAY_URL: str = os.getenv(
        "AGENT_RUNTIME__GATEWAY_URL",
        "http://localhost:8000"
    )
    
    # LLM Configuration
    LLM_MODEL: str = os.getenv(
        "AGENT_RUNTIME__LLM_MODEL",
        "fake-llm"
    )
    
    # Database Configuration
    # Supports both SQLite and PostgreSQL
    # SQLite example: sqlite:///data/agent_runtime.db
    # PostgreSQL example: postgresql://user:password@localhost:5432/agent_runtime
    # PostgreSQL async example: postgresql+asyncpg://user:password@localhost:5432/agent_runtime
    DB_URL: str = os.getenv(
        "AGENT_RUNTIME__DB_URL",
        "sqlite:///data/agent_runtime.db"
    )
    
    # Security
    INTERNAL_API_KEY: str = os.getenv(
        "AGENT_RUNTIME__INTERNAL_API_KEY",
        "change-me-internal-key"
    )
    
    # Logging
    LOG_LEVEL: str = os.getenv(
        "AGENT_RUNTIME__LOG_LEVEL",
        "INFO"
    )
    
    # Multi-Agent configuration
    MULTI_AGENT_MODE: bool = os.getenv(
        "AGENT_RUNTIME__MULTI_AGENT_MODE",
        "true"
    ).lower() in ("true", "1", "yes")
    
    # Event-Driven Architecture feature flags (Phase 3)
    # These flags control gradual migration to event-driven approach
    USE_EVENT_DRIVEN_CONTEXT: bool = os.getenv(
        "AGENT_RUNTIME__USE_EVENT_DRIVEN_CONTEXT",
        "true"
    ).lower() in ("true", "1", "yes")
    
    USE_EVENT_DRIVEN_PERSISTENCE: bool = os.getenv(
        "AGENT_RUNTIME__USE_EVENT_DRIVEN_PERSISTENCE",
        "false"
    ).lower() in ("true", "1", "yes")
    
    # Service metadata
    VERSION: str = os.getenv(
        "AGENT_RUNTIME__VERSION",
        "0.2.0"
    )


# Configure logging
logging.basicConfig(
    level=AppConfig.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("agent-runtime")

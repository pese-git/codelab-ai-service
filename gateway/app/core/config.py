import logging
import os


class AppConfig:
    AGENT_URL: str = os.getenv("AGENT_URL", "http://localhost:8001")
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "30.0"))
    VERSION: str = os.getenv("VERSION", "0.1.0")


logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("gateway")

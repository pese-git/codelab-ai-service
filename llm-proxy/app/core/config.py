import os
import logging

class AppConfig:
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    VERSION: str = os.getenv("VERSION", "0.1.0")

# Logging setup
logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("llm-proxy")
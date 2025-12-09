import os
import logging

class AppConfig:
    LLM_PROXY_URL: str = os.getenv("LLM_PROXY_URL", "http://localhost:8002")
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    VERSION: str = os.getenv("VERSION", "0.1.0")

logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("agent-runtime")
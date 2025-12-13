import logging
import os

from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    AGENT_URL: str = os.getenv("GATEWAY__AGENT_URL", "http://localhost:8001")
    INTERNAL_API_KEY: str = os.getenv("GATEWAY__INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("GATEWAY__LOG_LEVEL", "DEBUG")
    REQUEST_TIMEOUT: float = float(os.getenv("GATEWAY__REQUEST_TIMEOUT", "30.0"))
    VERSION: str = os.getenv("GATEWAY__VERSION", "0.1.0")


logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("gateway")

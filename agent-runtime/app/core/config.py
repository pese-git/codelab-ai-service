import logging
import os

from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    LLM_PROXY_URL: str = os.getenv("AGENT_RUNTIME__LLM_PROXY_URL", "http://localhost:8002")
    GATEWAY_URL: str = os.getenv("AGENT_RUNTIME__GATEWAY_URL", "http://localhost:8000")
    LLM_MODEL: str = os.getenv("AGENT_RUNTIME__LLM_MODEL", "fake-llm")
    INTERNAL_API_KEY: str = os.getenv("AGENT_RUNTIME__INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("AGENT_RUNTIME__LOG_LEVEL", "INFO")
    VERSION: str = os.getenv("AGENT_RUNTIME__VERSION", "0.1.0")


logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("agent-runtime")

import logging
import os
from dotenv import load_dotenv

load_dotenv()

class AppConfig:
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    VERSION: str = os.getenv("VERSION", "0.1.0")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    LLM_MODE: str = os.getenv("LLM_MODE", "mock")  # mock | openai


# Logging setup
logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("llm-proxy")

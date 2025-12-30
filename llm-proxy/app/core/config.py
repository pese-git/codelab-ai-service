import logging
import os

from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    INTERNAL_API_KEY: str = os.getenv("LLM_PROXY__INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("LLM_PROXY__LOG_LEVEL", "INFO")
    VERSION: str = os.getenv("LLM_PROXY__VERSION", "0.1.0")

    # LiteLLM proxy настройки
    LITELLM_PROXY_URL: str = os.getenv("LLM_PROXY__LITELLM_PROXY_URL", "http://localhost:4000")
    LITELLM_API_KEY: str = os.getenv("LLM_PROXY__LITELLM_API_KEY", "")
    DEFAULT_MODEL: str = os.getenv("LLM_PROXY__DEFAULT_MODEL", "gpt-3.5-turbo")

    # Режим работы: mock для тестов, litellm для продакшена
    LLM_MODE: str = os.getenv("LLM_PROXY__LLM_MODE", "litellm")  # mock | litellm


# Logging setup
logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("llm-proxy")

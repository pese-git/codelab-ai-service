import logging
import os

from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    INTERNAL_API_KEY: str = os.getenv("LLM_PROXY__INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("LLM_PROXY__LOG_LEVEL", "INFO")
    VERSION: str = os.getenv("LLM_PROXY__VERSION", "0.1.0")
    OPENAI_API_KEY: str = os.getenv("LLM_PROXY__OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("LLM_PROXY__OPENAI_BASE_URL", "https://api.openai.com/v1")
    VLLM_BASE_URL: str = os.getenv("LLM_PROXY__VLLM_BASE_URL", "http://localhost:8000/v1")
    VLLM_API_KEY: str = os.getenv("LLM_PROXY__VLLM_API_KEY", "")
    LLM_MODE: str = os.getenv("LLM_PROXY__LLM_MODE", "mock")  # mock | openai | vllm


# Logging setup
logging.basicConfig(level=AppConfig.LOG_LEVEL)
logger = logging.getLogger("llm-proxy")

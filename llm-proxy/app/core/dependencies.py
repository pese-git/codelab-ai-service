from app.core.config import AppConfig
from app.services.llm_adapters.fake import FakeLLMAdapter
from app.services.llm_adapters.openai import OpenAIAdapter


def get_llm_adapter():
    llm_mode = (getattr(AppConfig, "LLM_MODE", "mock") or "mock").lower()
    if llm_mode == "openai":
        return OpenAIAdapter()
    return FakeLLMAdapter()

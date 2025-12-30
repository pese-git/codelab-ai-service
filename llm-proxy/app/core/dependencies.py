from app.core.config import AppConfig
from app.services.llm_adapters.fake import FakeLLMAdapter
from app.services.llm_adapters.litellm_adapter import LiteLLMAdapter


def get_llm_adapter():
    """
    Возвращает адаптер LLM в зависимости от режима работы.
    - mock: FakeLLMAdapter для тестирования
    - litellm: LiteLLMAdapter для работы с LiteLLM proxy
    """
    llm_mode = (getattr(AppConfig, "LLM_MODE", "litellm") or "litellm").lower()
    if llm_mode == "mock":
        return FakeLLMAdapter()
    return LiteLLMAdapter()

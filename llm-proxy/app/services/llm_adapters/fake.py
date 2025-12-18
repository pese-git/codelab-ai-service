import asyncio
import logging
import pprint

from app.models.schemas import ChatCompletionRequest

from .base import BaseLLMAdapter

logger = logging.getLogger("llm-proxy.fake_adapter")


class FakeLLMAdapter(BaseLLMAdapter):
    async def get_models(self) -> list:
        # Можно возвращать структуры, совместимые с LLMModel
        models = [
            {
                "id": "mock-llm",
                "name": "FakeLLM Echo",
                "provider": "Fake",
                "context_length": 4096,
                "is_available": True,
            }
        ]
        logger.debug(
            f"[FakeLLMAdapter] get_models returns: {pprint.pformat(models, indent=2, width=120)}"
        )
        return models

    async def chat(self, request: ChatCompletionRequest):
        logger.debug(
            f"[FakeLLMAdapter] chat called with: {pprint.pformat(request.model_dump(), indent=2, width=120)}"
        )
        # Для теста: всегда возвращаем детерминированный mock-ответ, не зависящий от ввода
        if not getattr(request, "stream", False):
            result = {
                "id": "chatcmpl-fake-echo-1",
                "object": "chat.completion",
                "created": 1234567890,
                "model": getattr(request, "model", "mock-llm"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "role": "assistant",
                                    "content": "Mock LLM response (static)",
                                }
                            ],
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": None,
            }
            logger.debug(f"[FakeLLMAdapter] chat result (not streamed): {result}")
            return result

        # stream mode
        async def token_gen():
            words = last_message.split()
            for word in words:
                logger.debug(f"[FakeLLMAdapter][stream] yield token: {word}")
                yield word + " "
                await asyncio.sleep(0.2)

        return token_gen()

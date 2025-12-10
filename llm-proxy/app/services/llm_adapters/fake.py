import asyncio

from app.models.schemas import ChatRequest

from .base import BaseLLMAdapter


class FakeLLMAdapter(BaseLLMAdapter):
    async def get_models(self) -> list:
        # Можно возвращать структуры, совместимые с LLMModel
        return [
            {
                "id": "mock-llm",
                "name": "FakeLLM Echo",
                "provider": "Fake",
                "context_length": 4096,
                "is_available": True,
            }
        ]

    async def chat(self, request: ChatRequest):
        last_message = request.messages[-1]["content"] if request.messages else ""
        if not getattr(request, "stream", False):
            return f"Echo from LLM: {last_message}"

        # stream mode
        async def token_gen():
            words = last_message.split()
            for word in words:
                yield word + " "
                await asyncio.sleep(0.2)

        return token_gen()

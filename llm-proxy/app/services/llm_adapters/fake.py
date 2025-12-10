import asyncio
from typing import AsyncGenerator

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

    async def chat(self, request: ChatRequest) -> str:
        last_message = request.messages[-1]["content"] if request.messages else ""
        return f"Echo from LLM: {last_message}"

    async def streaming_generator(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        last_message = request.messages[-1]["content"] if request.messages else ""
        words = last_message.split()
        for word in words:
            yield word + " "
            await asyncio.sleep(0.2)

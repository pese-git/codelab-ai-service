import abc
from typing import AsyncGenerator

from app.models.schemas import ChatRequest


class BaseLLMAdapter(abc.ABC):
    @abc.abstractmethod
    async def chat(self, request: ChatRequest) -> str:
        pass

    @abc.abstractmethod
    async def streaming_generator(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        pass

    @abc.abstractmethod
    async def get_models(self) -> list:
        """Асинхронно возвращает список поддерживаемых моделей (list of dicts or LLMModel fields)"""
        pass

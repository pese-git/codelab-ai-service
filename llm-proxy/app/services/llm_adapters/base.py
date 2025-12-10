import abc
import typing
from typing import AsyncGenerator

from app.models.schemas_openai import ChatCompletionRequest


class BaseLLMAdapter(abc.ABC):
    @abc.abstractmethod
    async def chat(
        self, request: ChatCompletionRequest
    ) -> typing.Union[str, AsyncGenerator[str, None]]:
        """
        Если stream=False: возвращает полный текст (str)
        Если stream=True: возвращает async-генератор токенов
        """
        pass

    @abc.abstractmethod
    async def get_models(self) -> list:
        """Асинхронно возвращает список поддерживаемых моделей (list of dicts or LLMModel fields)"""
        pass

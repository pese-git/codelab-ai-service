import abc
import typing
from typing import AsyncGenerator

from app.models.schemas import ChatCompletionRequest


class BaseLLMAdapter(abc.ABC):
    """
    Базовый класс для всех LLM адаптеров.
    Определяет интерфейс для работы с различными LLM провайдерами.
    """

    @abc.abstractmethod
    async def chat(
        self, request: ChatCompletionRequest
    ) -> typing.Union[str, list, AsyncGenerator[str, None]]:
        """
        Выполняет chat completion запрос.
        
        Если stream=False: возвращает список сообщений (list of dicts) или строку с ошибкой
        Если stream=True: возвращает async-генератор токенов (AsyncGenerator[str, None])
        
        Args:
            request: ChatCompletionRequest с параметрами запроса
            
        Returns:
            - list[dict]: список сообщений в non-streaming режиме
            - str: сообщение об ошибке
            - AsyncGenerator[str, None]: генератор токенов в streaming режиме
        """
        pass

    @abc.abstractmethod
    async def get_models(self) -> list:
        """
        Асинхронно возвращает список поддерживаемых моделей.
        
        Returns:
            list: список словарей с информацией о моделях (совместимо с LLMModel)
                Каждый словарь должен содержать:
                - id: str - идентификатор модели
                - name: str - название модели
                - provider: str - провайдер (OpenAI, LiteLLM, etc.)
                - context_length: int - размер контекста
                - is_available: bool - доступность модели
        """
        pass

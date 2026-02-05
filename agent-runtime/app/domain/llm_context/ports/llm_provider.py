"""
Port для LLM провайдера.

Определяет контракт для взаимодействия с LLM API.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from ..entities.llm_request import LLMRequest
from ...entities.llm_response import LLMResponse
from ..value_objects.model_name import ModelName


class ILLMProvider(ABC):
    """
    Port (интерфейс) для LLM провайдера.
    
    Абстракция над конкретными реализациями LLM API
    (OpenAI, Anthropic, Google, etc.).
    
    Реализации этого интерфейса находятся в infrastructure слое.
    
    Examples:
        >>> class OpenAIProvider(ILLMProvider):
        ...     async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        ...         # Реализация для OpenAI API
        ...         pass
        
        >>> provider = OpenAIProvider()
        >>> request = LLMRequest.create(...)
        >>> response = await provider.chat_completion(request)
    """
    
    @abstractmethod
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """
        Выполнить chat completion запрос.
        
        Args:
            request: LLM запрос с параметрами
            
        Returns:
            LLMResponse с результатом генерации
            
        Raises:
            LLMProviderError: При ошибке взаимодействия с API
            
        Example:
            >>> request = LLMRequest.create(
            ...     model=ModelName(value="gpt-4"),
            ...     messages=[{"role": "user", "content": "Hello"}]
            ... )
            >>> response = await provider.chat_completion(request)
            >>> print(response.content)
        """
        pass
    
    @abstractmethod
    async def validate_model(self, model: ModelName) -> bool:
        """
        Проверить доступность модели.
        
        Args:
            model: Имя модели для проверки
            
        Returns:
            True если модель доступна
            
        Example:
            >>> model = ModelName(value="gpt-4")
            >>> is_available = await provider.validate_model(model)
            >>> if not is_available:
            ...     print("Model not available")
        """
        pass
    
    @abstractmethod
    async def get_model_info(self, model: ModelName) -> Dict[str, Any]:
        """
        Получить информацию о модели.
        
        Args:
            model: Имя модели
            
        Returns:
            Словарь с информацией о модели:
            - max_tokens: Максимальное количество токенов
            - supports_tools: Поддержка function calling
            - context_window: Размер контекстного окна
            - pricing: Информация о ценах (опционально)
            
        Example:
            >>> model = ModelName(value="gpt-4")
            >>> info = await provider.get_model_info(model)
            >>> print(f"Max tokens: {info['max_tokens']}")
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить доступность провайдера.
        
        Returns:
            True если провайдер доступен
            
        Example:
            >>> is_healthy = await provider.health_check()
            >>> if not is_healthy:
            ...     print("Provider is down")
        """
        pass

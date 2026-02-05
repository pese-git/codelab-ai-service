"""
Port для подсчета токенов.

Определяет контракт для подсчета токенов в тексте и сообщениях.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..value_objects.model_name import ModelName


class ITokenCounter(ABC):
    """
    Port (интерфейс) для подсчета токенов.
    
    Абстракция над конкретными реализациями tokenizer'ов
    (tiktoken для OpenAI, anthropic tokenizer, etc.).
    
    Реализации этого интерфейса находятся в infrastructure слое.
    
    Examples:
        >>> class TiktokenCounter(ITokenCounter):
        ...     def count_tokens(self, text: str, model: ModelName) -> int:
        ...         # Реализация с использованием tiktoken
        ...         pass
        
        >>> counter = TiktokenCounter()
        >>> model = ModelName(value="gpt-4")
        >>> tokens = counter.count_tokens("Hello, world!", model)
        >>> print(f"Tokens: {tokens}")
    """
    
    @abstractmethod
    def count_tokens(self, text: str, model: ModelName) -> int:
        """
        Подсчитать токены в тексте.
        
        Args:
            text: Текст для подсчета
            model: Модель для определения tokenizer'а
            
        Returns:
            Количество токенов
            
        Example:
            >>> model = ModelName(value="gpt-4")
            >>> tokens = counter.count_tokens("Hello, world!", model)
            >>> print(f"Tokens: {tokens}")
        """
        pass
    
    @abstractmethod
    def count_messages(
        self,
        messages: List[Dict[str, Any]],
        model: ModelName
    ) -> int:
        """
        Подсчитать токены в сообщениях.
        
        Учитывает служебные токены для форматирования сообщений
        (role, separators, etc.).
        
        Args:
            messages: Список сообщений в формате OpenAI
            model: Модель для определения tokenizer'а
            
        Returns:
            Количество токенов
            
        Example:
            >>> messages = [
            ...     {"role": "user", "content": "Hello"},
            ...     {"role": "assistant", "content": "Hi there!"}
            ... ]
            >>> model = ModelName(value="gpt-4")
            >>> tokens = counter.count_messages(messages, model)
            >>> print(f"Total tokens: {tokens}")
        """
        pass
    
    @abstractmethod
    def estimate_completion_tokens(
        self,
        prompt_tokens: int,
        max_tokens: int
    ) -> int:
        """
        Оценить количество токенов в ответе.
        
        Args:
            prompt_tokens: Количество токенов в промпте
            max_tokens: Максимальное количество токенов
            
        Returns:
            Оценка количества токенов в ответе
            
        Example:
            >>> estimated = counter.estimate_completion_tokens(
            ...     prompt_tokens=100,
            ...     max_tokens=1000
            ... )
        """
        pass

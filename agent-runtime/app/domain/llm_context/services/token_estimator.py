"""
Domain Service для оценки использования токенов.

Предоставляет эвристические методы для оценки токенов без точного подсчета.
"""

from typing import List, Dict, Any

from ..value_objects.model_name import ModelName
from ..value_objects.token_limit import TokenLimit
from ..entities.llm_request import LLMRequest


class TokenEstimator:
    """
    Domain Service для оценки использования токенов.
    
    Использует эвристики для быстрой оценки без точного подсчета.
    Для точного подсчета используйте ITokenCounter port.
    
    Эвристика: ~4 символа = 1 токен (для английского текста)
    
    Examples:
        >>> estimator = TokenEstimator()
        >>> tokens = estimator.estimate_messages(messages, model)
        >>> print(f"Estimated: {tokens} tokens")
        
        >>> will_exceed = estimator.will_exceed_limit(request, limit)
        >>> if will_exceed:
        ...     print("Request will exceed token limit!")
    """
    
    def __init__(self):
        """Инициализация estimator."""
        # Эвристические константы
        self.CHARS_PER_TOKEN = 4  # Среднее для английского текста
        self.OVERHEAD_PER_MESSAGE = 4  # Служебные токены на сообщение
        self.OVERHEAD_PER_TOOL = 100  # Примерный размер tool definition
    
    def estimate_text(self, text: str) -> int:
        """
        Оценить количество токенов в тексте.
        
        Args:
            text: Текст для оценки
            
        Returns:
            Приблизительное количество токенов
            
        Example:
            >>> estimator = TokenEstimator()
            >>> tokens = estimator.estimate_text("Hello, world!")
            >>> print(tokens)  # ~3
        """
        if not text:
            return 0
        
        # Простая эвристика: количество символов / 4
        return len(text) // self.CHARS_PER_TOKEN
    
    def estimate_message(self, message: Dict[str, Any]) -> int:
        """
        Оценить количество токенов в одном сообщении.
        
        Args:
            message: Сообщение в формате OpenAI
            
        Returns:
            Приблизительное количество токенов
            
        Example:
            >>> estimator = TokenEstimator()
            >>> message = {"role": "user", "content": "Hello"}
            >>> tokens = estimator.estimate_message(message)
        """
        tokens = self.OVERHEAD_PER_MESSAGE  # Служебные токены
        
        # Токены в content
        if "content" in message and message["content"]:
            tokens += self.estimate_text(str(message["content"]))
        
        # Токены в tool_calls
        if "tool_calls" in message and message["tool_calls"]:
            for tool_call in message["tool_calls"]:
                # Имя функции
                if "function" in tool_call and "name" in tool_call["function"]:
                    tokens += len(tool_call["function"]["name"]) // self.CHARS_PER_TOKEN
                
                # Аргументы
                if "function" in tool_call and "arguments" in tool_call["function"]:
                    args_str = str(tool_call["function"]["arguments"])
                    tokens += len(args_str) // self.CHARS_PER_TOKEN
        
        return tokens
    
    def estimate_messages(
        self,
        messages: List[Dict[str, Any]],
        model: ModelName
    ) -> int:
        """
        Оценить количество токенов в списке сообщений.
        
        Args:
            messages: Список сообщений
            model: Модель (для учета специфики)
            
        Returns:
            Приблизительное количество токенов
            
        Example:
            >>> estimator = TokenEstimator()
            >>> messages = [
            ...     {"role": "user", "content": "Hello"},
            ...     {"role": "assistant", "content": "Hi there!"}
            ... ]
            >>> model = ModelName(value="gpt-4")
            >>> tokens = estimator.estimate_messages(messages, model)
        """
        total_tokens = 0
        
        for message in messages:
            total_tokens += self.estimate_message(message)
        
        # Дополнительные токены для форматирования (зависит от модели)
        if model.is_openai():
            total_tokens += 3  # Токены для начала/конца диалога
        
        return total_tokens
    
    def estimate_tools(self, tools: List[Dict[str, Any]]) -> int:
        """
        Оценить количество токенов в определениях инструментов.
        
        Args:
            tools: Список инструментов
            
        Returns:
            Приблизительное количество токенов
            
        Example:
            >>> estimator = TokenEstimator()
            >>> tools = [{"type": "function", "function": {...}}]
            >>> tokens = estimator.estimate_tools(tools)
        """
        if not tools:
            return 0
        
        # Простая эвристика: каждый tool ~100 токенов
        return len(tools) * self.OVERHEAD_PER_TOOL
    
    def estimate_total(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model: ModelName
    ) -> int:
        """
        Оценить общее количество токенов в запросе.
        
        Args:
            messages: Список сообщений
            tools: Список инструментов
            model: Модель
            
        Returns:
            Приблизительное общее количество токенов
            
        Example:
            >>> estimator = TokenEstimator()
            >>> total = estimator.estimate_total(messages, tools, model)
        """
        message_tokens = self.estimate_messages(messages, model)
        tool_tokens = self.estimate_tools(tools)
        
        return message_tokens + tool_tokens
    
    def will_exceed_limit(
        self,
        request: LLMRequest,
        limit: TokenLimit
    ) -> bool:
        """
        Проверить, превысит ли запрос лимит токенов.
        
        Args:
            request: LLM запрос
            limit: Лимит токенов
            
        Returns:
            True если запрос превысит лимит
            
        Example:
            >>> estimator = TokenEstimator()
            >>> request = LLMRequest.create(...)
            >>> limit = TokenLimit.for_gpt4()
            >>> if estimator.will_exceed_limit(request, limit):
            ...     print("Request too large!")
        """
        estimated = self.estimate_total(
            request.messages,
            request.tools,
            request.model
        )
        
        # Оставляем запас для ответа (минимум 100 токенов)
        return estimated + 100 > limit.value
    
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
            >>> estimator = TokenEstimator()
            >>> estimated = estimator.estimate_completion_tokens(100, 1000)
        """
        # Простая эвристика: используем 50% от доступного лимита
        available = max_tokens - prompt_tokens
        return min(available // 2, available)
    
    def get_recommended_max_tokens(
        self,
        messages: List[Dict[str, Any]],
        model: ModelName
    ) -> int:
        """
        Получить рекомендуемый max_tokens для запроса.
        
        Args:
            messages: Список сообщений
            model: Модель
            
        Returns:
            Рекомендуемое значение max_tokens
            
        Example:
            >>> estimator = TokenEstimator()
            >>> max_tokens = estimator.get_recommended_max_tokens(messages, model)
        """
        # Оценка токенов в промпте
        prompt_tokens = self.estimate_messages(messages, model)
        
        # Лимит модели
        model_limit = TokenLimit.for_model(model)
        
        # Оставляем место для ответа (минимум 500 токенов)
        available = model_limit.value - prompt_tokens
        recommended = max(500, available // 2)
        
        return min(recommended, model_limit.value)

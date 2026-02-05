"""
Domain Service для построения LLM запросов.

Инкапсулирует логику создания и валидации LLM запросов.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from ..entities.llm_request import LLMRequest
from ..value_objects.model_name import ModelName
from ..value_objects.temperature import Temperature
from ..value_objects.token_limit import TokenLimit


class LLMRequestBuilder:
    """
    Domain Service для построения LLM запросов.
    
    Предоставляет удобные методы для создания различных типов запросов
    с автоматической настройкой параметров.
    
    Examples:
        >>> builder = LLMRequestBuilder()
        >>> request = builder.build_chat_request(
        ...     model=ModelName(value="gpt-4"),
        ...     messages=[{"role": "user", "content": "Hello"}]
        ... )
        
        >>> request = builder.build_tool_request(
        ...     model=ModelName(value="gpt-4"),
        ...     messages=[...],
        ...     tools=[...]
        ... )
    """
    
    def build_chat_request(
        self,
        model: ModelName,
        messages: List[Dict[str, Any]],
        temperature: Optional[Temperature] = None,
        max_tokens: Optional[TokenLimit] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LLMRequest:
        """
        Построить запрос для обычного чата.
        
        Args:
            model: Модель для использования
            messages: История сообщений
            temperature: Температура (по умолчанию balanced)
            max_tokens: Максимум токенов (по умолчанию для модели)
            metadata: Дополнительные метаданные
            
        Returns:
            Готовый LLMRequest
            
        Example:
            >>> builder = LLMRequestBuilder()
            >>> request = builder.build_chat_request(
            ...     model=ModelName(value="gpt-4"),
            ...     messages=[{"role": "user", "content": "Hello"}]
            ... )
        """
        # Установка значений по умолчанию
        if temperature is None:
            temperature = Temperature.balanced()
        
        if max_tokens is None:
            max_tokens = TokenLimit.for_model(model)
        
        # Создание запроса
        request = LLMRequest.create(
            model=model,
            messages=messages,
            tools=[],
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata or {}
        )
        
        return request
    
    def build_tool_request(
        self,
        model: ModelName,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: Optional[Temperature] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LLMRequest:
        """
        Построить запрос с инструментами (function calling).
        
        Args:
            model: Модель для использования
            messages: История сообщений
            tools: Список инструментов
            temperature: Температура (по умолчанию conservative для точности)
            metadata: Дополнительные метаданные
            
        Returns:
            Готовый LLMRequest
            
        Raises:
            ValueError: Если модель не поддерживает инструменты
            
        Example:
            >>> builder = LLMRequestBuilder()
            >>> request = builder.build_tool_request(
            ...     model=ModelName(value="gpt-4"),
            ...     messages=[...],
            ...     tools=[{"type": "function", "function": {...}}]
            ... )
        """
        # Проверка поддержки инструментов
        if not model.supports_tools():
            raise ValueError(
                f"Model '{model.value}' does not support function calling"
            )
        
        # Для tool calls используем более консервативную температуру
        if temperature is None:
            temperature = Temperature.conservative()
        
        # Создание запроса
        request = LLMRequest.create(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=None,  # Для tool calls не ограничиваем
            metadata=metadata or {}
        )
        
        return request
    
    def build_code_generation_request(
        self,
        model: ModelName,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> LLMRequest:
        """
        Построить запрос для генерации кода.
        
        Использует консервативную температуру для детерминированности.
        
        Args:
            model: Модель для использования
            messages: История сообщений
            metadata: Дополнительные метаданные
            
        Returns:
            Готовый LLMRequest
            
        Example:
            >>> builder = LLMRequestBuilder()
            >>> request = builder.build_code_generation_request(
            ...     model=ModelName(value="gpt-4"),
            ...     messages=[{"role": "user", "content": "Write a function..."}]
            ... )
        """
        return self.build_chat_request(
            model=model,
            messages=messages,
            temperature=Temperature.conservative(),
            metadata={**(metadata or {}), "task_type": "code_generation"}
        )
    
    def validate_messages(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Валидировать формат сообщений.
        
        Args:
            messages: Список сообщений для валидации
            
        Returns:
            True если все сообщения валидны
            
        Example:
            >>> builder = LLMRequestBuilder()
            >>> messages = [{"role": "user", "content": "Hello"}]
            >>> builder.validate_messages(messages)
            True
        """
        if not messages:
            return False
        
        for msg in messages:
            if not isinstance(msg, dict):
                return False
            
            if "role" not in msg:
                return False
            
            # Должно быть либо content, либо tool_calls
            if "content" not in msg and "tool_calls" not in msg:
                return False
        
        return True
    
    def optimize_context(
        self,
        messages: List[Dict[str, Any]],
        max_messages: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Оптимизировать контекст, оставляя только последние сообщения.
        
        Всегда сохраняет system message если есть.
        
        Args:
            messages: Исходные сообщения
            max_messages: Максимальное количество сообщений
            
        Returns:
            Оптимизированный список сообщений
            
        Example:
            >>> builder = LLMRequestBuilder()
            >>> messages = [{"role": "system", "content": "..."}, ...]
            >>> optimized = builder.optimize_context(messages, max_messages=10)
        """
        if len(messages) <= max_messages:
            return messages
        
        # Сохраняем system message если есть
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        other_messages = [msg for msg in messages if msg.get("role") != "system"]
        
        # Берем последние N сообщений
        recent_messages = other_messages[-(max_messages - len(system_messages)):]
        
        return system_messages + recent_messages

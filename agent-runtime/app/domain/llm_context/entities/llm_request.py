"""
Entity для LLM запроса.

Инкапсулирует бизнес-логику создания и валидации LLM запросов.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import Field

from ...shared.base_entity import BaseEntity
from ..value_objects.llm_request_id import LLMRequestId
from ..value_objects.model_name import ModelName
from ..value_objects.temperature import Temperature
from ..value_objects.token_limit import TokenLimit


class LLMRequest(BaseEntity):
    """
    Entity для LLM запроса.
    
    Представляет запрос к LLM провайдеру с валидацией и бизнес-правилами.
    
    Атрибуты:
        id: Уникальный идентификатор запроса
        model: Имя модели для использования
        messages: История сообщений в формате OpenAI
        tools: Список доступных инструментов
        temperature: Температура генерации (опционально)
        max_tokens: Максимальное количество токенов (опционально)
        created_at: Время создания запроса
        metadata: Дополнительные метаданные
    
    Examples:
        >>> request = LLMRequest.create(
        ...     model=ModelName(value="gpt-4"),
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     tools=[]
        ... )
        >>> request.validate()
        (True, None)
        
        >>> api_format = request.to_api_format()
        >>> api_format["model"]
        'gpt-4'
    """
    
    id: LLMRequestId = Field(
        default_factory=LLMRequestId.generate,
        description="Уникальный идентификатор запроса"
    )
    
    model: ModelName = Field(
        ...,
        description="Имя модели для использования"
    )
    
    messages: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="История сообщений в формате OpenAI"
    )
    
    tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Список доступных инструментов"
    )
    
    temperature: Optional[Temperature] = Field(
        default=None,
        description="Температура генерации"
    )
    
    max_tokens: Optional[TokenLimit] = Field(
        default=None,
        description="Максимальное количество токенов"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время создания запроса"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные"
    )
    
    @staticmethod
    def create(
        model: ModelName,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[Temperature] = None,
        max_tokens: Optional[TokenLimit] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "LLMRequest":
        """
        Создать новый LLM запрос.
        
        Args:
            model: Имя модели
            messages: История сообщений
            tools: Список инструментов (опционально)
            temperature: Температура генерации (опционально)
            max_tokens: Максимум токенов (опционально)
            metadata: Дополнительные метаданные (опционально)
            
        Returns:
            Новый LLMRequest
            
        Example:
            >>> request = LLMRequest.create(
            ...     model=ModelName(value="gpt-4"),
            ...     messages=[{"role": "user", "content": "Hello"}]
            ... )
        """
        request = LLMRequest(
            model=model,
            messages=messages or [],
            tools=tools or [],
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata or {}
        )
        
        # Генерация Domain Event
        from ..events.llm_events import LLMRequestCreated
        request.add_domain_event(LLMRequestCreated(
            request_id=request.id.value,
            model=request.model.value,
            message_count=len(request.messages),
            tool_count=len(request.tools),
            timestamp=request.created_at
        ))
        
        return request
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Валидировать запрос.
        
        Проверяет:
        - Наличие сообщений
        - Корректность формата сообщений
        - Совместимость инструментов с моделью
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            
        Example:
            >>> request = LLMRequest.create(...)
            >>> is_valid, error = request.validate()
            >>> if not is_valid:
            ...     print(f"Validation error: {error}")
        """
        # Проверка наличия сообщений
        if not self.messages:
            return False, "Request must contain at least one message"
        
        # Проверка формата сообщений
        for i, msg in enumerate(self.messages):
            if not isinstance(msg, dict):
                return False, f"Message {i} must be a dictionary"
            
            if "role" not in msg:
                return False, f"Message {i} missing 'role' field"
            
            if "content" not in msg and "tool_calls" not in msg:
                return False, f"Message {i} must have 'content' or 'tool_calls'"
        
        # Проверка совместимости инструментов с моделью
        if self.tools and not self.model.supports_tools():
            return False, f"Model '{self.model.value}' does not support tools"
        
        # Генерация Domain Event
        from ..events.llm_events import LLMRequestValidated
        self.add_domain_event(LLMRequestValidated(
            request_id=self.id.value,
            is_valid=True,
            timestamp=datetime.utcnow()
        ))
        
        return True, None
    
    def estimate_tokens(self) -> int:
        """
        Оценить количество токенов в запросе.
        
        Простая эвристика: ~4 символа = 1 токен.
        Для точной оценки используйте TokenEstimator service.
        
        Returns:
            Приблизительное количество токенов
            
        Example:
            >>> request = LLMRequest.create(...)
            >>> estimated = request.estimate_tokens()
        """
        total_chars = 0
        
        # Подсчет символов в сообщениях
        for msg in self.messages:
            if "content" in msg and msg["content"]:
                total_chars += len(str(msg["content"]))
        
        # Подсчет символов в инструментах (примерно)
        for tool in self.tools:
            # Примерная оценка размера tool definition
            total_chars += 100
        
        # Эвристика: ~4 символа = 1 токен
        return total_chars // 4
    
    def to_api_format(self) -> Dict[str, Any]:
        """
        Преобразовать в формат для LLM API.
        
        Returns:
            Словарь в формате OpenAI API
            
        Example:
            >>> request = LLMRequest.create(...)
            >>> api_data = request.to_api_format()
            >>> # Отправить в LLM API
        """
        result: Dict[str, Any] = {
            "model": self.model.value,
            "messages": self.messages,
        }
        
        if self.tools:
            result["tools"] = self.tools
        
        if self.temperature is not None:
            result["temperature"] = self.temperature.value
        
        if self.max_tokens is not None:
            result["max_tokens"] = self.max_tokens.value
        
        return result
    
    def add_message(self, role: str, content: str) -> None:
        """
        Добавить сообщение к запросу.
        
        Args:
            role: Роль отправителя (user, assistant, system)
            content: Содержимое сообщения
            
        Example:
            >>> request = LLMRequest.create(...)
            >>> request.add_message("user", "Hello!")
        """
        self.messages.append({
            "role": role,
            "content": content
        })
    
    def has_tools(self) -> bool:
        """
        Проверить, содержит ли запрос инструменты.
        
        Returns:
            True если есть хотя бы один инструмент
        """
        return len(self.tools) > 0
    
    def get_message_count(self) -> int:
        """
        Получить количество сообщений.
        
        Returns:
            Количество сообщений в запросе
        """
        return len(self.messages)
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        return (
            f"<LLMRequest(id='{self.id.value}', "
            f"model='{self.model.value}', "
            f"messages={len(self.messages)}, "
            f"tools={len(self.tools)})>"
        )

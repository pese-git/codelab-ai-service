"""
Доменные сущности для работы с LLM ответами.

Представляют ответы от LLM в доменной модели,
независимо от конкретного провайдера (OpenAI, Anthropic, etc.).
"""

import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """
    Value Object для информации об использовании токенов.
    
    Атрибуты:
        prompt_tokens: Количество токенов в промпте
        completion_tokens: Количество токенов в ответе
        total_tokens: Общее количество токенов
    """
    
    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Количество токенов в промпте"
    )
    
    completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Количество токенов в ответе"
    )
    
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Общее количество токенов"
    )
    
    def __post_init__(self):
        """Валидация: total должен быть суммой prompt и completion"""
        if self.total_tokens == 0 and (self.prompt_tokens > 0 or self.completion_tokens > 0):
            self.total_tokens = self.prompt_tokens + self.completion_tokens


class ToolCall(BaseModel):
    """
    Value Object для вызова инструмента.
    
    Представляет запрос LLM на выполнение инструмента.
    
    Атрибуты:
        id: Уникальный идентификатор вызова
        tool_name: Имя инструмента
        arguments: Аргументы для инструмента
    
    Пример:
        >>> tool_call = ToolCall(
        ...     id="call-123",
        ...     tool_name="write_file",
        ...     arguments={"path": "test.py", "content": "print('hello')"}
        ... )
    """
    
    id: str = Field(
        ...,
        description="Уникальный идентификатор вызова инструмента"
    )
    
    tool_name: str = Field(
        ...,
        description="Имя инструмента для вызова"
    )
    
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Аргументы для инструмента"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь для LLM API формата.
        
        Returns:
            Словарь в формате OpenAI tool_calls
        """
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.tool_name,
                "arguments": json.dumps(self.arguments) if isinstance(self.arguments, dict) else self.arguments
            }
        }
    
    def __repr__(self) -> str:
        return f"<ToolCall(id='{self.id}', tool='{self.tool_name}')>"


class LLMResponse(BaseModel):
    """
    Доменная сущность ответа от LLM.
    
    Представляет сырой ответ от LLM провайдера,
    преобразованный в доменную модель.
    
    Атрибуты:
        content: Текстовое содержимое ответа
        tool_calls: Список вызовов инструментов
        usage: Информация об использовании токенов
        model: Имя модели, которая сгенерировала ответ
        finish_reason: Причина завершения генерации
    
    Пример:
        >>> response = LLMResponse(
        ...     content="Hello, world!",
        ...     tool_calls=[],
        ...     usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        ...     model="gpt-4"
        ... )
    """
    
    content: str = Field(
        default="",
        description="Текстовое содержимое ответа"
    )
    
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description="Список вызовов инструментов"
    )
    
    usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Информация об использовании токенов"
    )
    
    model: str = Field(
        ...,
        description="Имя модели, которая сгенерировала ответ"
    )
    
    finish_reason: Optional[str] = Field(
        default=None,
        description="Причина завершения генерации (stop, length, tool_calls, etc.)"
    )
    
    def has_tool_calls(self) -> bool:
        """
        Проверить, содержит ли ответ вызовы инструментов.
        
        Returns:
            True если есть хотя бы один tool call
        """
        return len(self.tool_calls) > 0
    
    def has_content(self) -> bool:
        """
        Проверить, содержит ли ответ текстовое содержимое.
        
        Returns:
            True если content не пустой
        """
        return bool(self.content.strip())
    
    def get_first_tool_call(self) -> Optional[ToolCall]:
        """
        Получить первый вызов инструмента.
        
        Returns:
            Первый ToolCall или None если нет вызовов
        """
        return self.tool_calls[0] if self.tool_calls else None
    
    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (
            f"<LLMResponse(model='{self.model}', "
            f"content='{content_preview}', "
            f"tool_calls={len(self.tool_calls)})>"
        )


class ProcessedResponse(BaseModel):
    """
    Обработанный ответ LLM после применения бизнес-правил.
    
    Содержит результат обработки LLMResponse доменным сервисом,
    включая информацию о необходимости одобрения (HITL).
    
    Атрибуты:
        content: Текстовое содержимое (очищенное)
        tool_calls: Список вызовов инструментов (валидированный)
        usage: Информация об использовании токенов
        model: Имя модели
        requires_approval: Требуется ли одобрение пользователя
        approval_reason: Причина необходимости одобрения
        validation_warnings: Предупреждения валидации
    
    Пример:
        >>> processed = ProcessedResponse(
        ...     content="",
        ...     tool_calls=[tool_call],
        ...     usage=usage,
        ...     model="gpt-4",
        ...     requires_approval=True,
        ...     approval_reason="File modification requires approval"
        ... )
    """
    
    content: str = Field(
        default="",
        description="Текстовое содержимое ответа"
    )
    
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description="Список вызовов инструментов (валидированный)"
    )
    
    usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Информация об использовании токенов"
    )
    
    model: str = Field(
        ...,
        description="Имя модели"
    )
    
    requires_approval: bool = Field(
        default=False,
        description="Требуется ли одобрение пользователя (HITL)"
    )
    
    approval_reason: Optional[str] = Field(
        default=None,
        description="Причина необходимости одобрения"
    )
    
    validation_warnings: List[str] = Field(
        default_factory=list,
        description="Предупреждения валидации"
    )
    
    def has_tool_calls(self) -> bool:
        """Проверить наличие tool calls"""
        return len(self.tool_calls) > 0
    
    def has_content(self) -> bool:
        """Проверить наличие текстового содержимого"""
        return bool(self.content.strip())
    
    def get_first_tool_call(self) -> Optional[ToolCall]:
        """Получить первый tool call"""
        return self.tool_calls[0] if self.tool_calls else None
    
    def __repr__(self) -> str:
        return (
            f"<ProcessedResponse(model='{self.model}', "
            f"tool_calls={len(self.tool_calls)}, "
            f"requires_approval={self.requires_approval})>"
        )

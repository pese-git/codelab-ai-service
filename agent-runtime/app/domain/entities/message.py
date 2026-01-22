"""
Доменная сущность Message (Сообщение).

Представляет сообщение в диалоге между пользователем и AI агентом.
"""

from typing import Optional, Dict, Any, Literal
from datetime import datetime, timezone
from pydantic import Field, field_validator

from .base import Entity


class Message(Entity):
    """
    Доменная сущность сообщения.
    
    Сообщение - это единица коммуникации в диалоге.
    Может быть от пользователя, ассистента, системы или инструмента.
    
    Атрибуты:
        role: Роль отправителя (user, assistant, system, tool)
        content: Текстовое содержимое сообщения
        name: Имя отправителя (опционально, для tool сообщений)
        tool_call_id: ID вызова инструмента (для tool сообщений)
        tool_calls: Список вызовов инструментов (для assistant сообщений)
        metadata: Дополнительные метаданные
    
    Пример:
        >>> # Сообщение пользователя
        >>> msg = Message(
        ...     id="msg-1",
        ...     role="user",
        ...     content="Создай новый файл"
        ... )
        >>> 
        >>> # Сообщение с вызовом инструмента
        >>> msg = Message(
        ...     id="msg-2",
        ...     role="assistant",
        ...     content="",
        ...     tool_calls=[{
        ...         "id": "call-1",
        ...         "tool_name": "write_file",
        ...         "arguments": {"path": "test.py", "content": "print('hello')"}
        ...     }]
        ... )
    """
    
    role: Literal["user", "assistant", "system", "tool"] = Field(
        ...,
        description="Роль отправителя сообщения"
    )
    
    content: str = Field(
        default="",
        description="Текстовое содержимое сообщения"
    )
    
    name: Optional[str] = Field(
        default=None,
        description="Имя отправителя (например, имя инструмента для tool сообщений)"
    )
    
    tool_call_id: Optional[str] = Field(
        default=None,
        description="ID вызова инструмента (для tool сообщений)"
    )
    
    tool_calls: Optional[list[Dict[str, Any]]] = Field(
        default=None,
        description="Список вызовов инструментов (для assistant сообщений)"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные сообщения"
    )
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str, info) -> str:
        """
        Валидация содержимого сообщения.
        
        Правила:
        - Для user и system сообщений content обязателен
        - Для assistant с tool_calls content может быть пустым
        - Для tool сообщений content обязателен
        
        Args:
            v: Значение content
            info: Контекст валидации
            
        Returns:
            Валидированное значение
            
        Raises:
            ValueError: Если content не соответствует правилам
        """
        # Получаем role из контекста валидации
        data = info.data
        role = data.get('role')
        tool_calls = data.get('tool_calls')
        
        # Для assistant с tool_calls content может быть пустым
        if role == 'assistant' and tool_calls:
            return v
        
        # Для остальных ролей content не должен быть пустым
        if role in ('user', 'system', 'tool') and not v.strip():
            raise ValueError(
                f"Содержимое сообщения не может быть пустым для роли '{role}'"
            )
        
        return v
    
    def is_user_message(self) -> bool:
        """
        Проверить, является ли сообщение пользовательским.
        
        Returns:
            True если сообщение от пользователя
        """
        return self.role == "user"
    
    def is_assistant_message(self) -> bool:
        """
        Проверить, является ли сообщение от ассистента.
        
        Returns:
            True если сообщение от ассистента
        """
        return self.role == "assistant"
    
    def is_tool_message(self) -> bool:
        """
        Проверить, является ли сообщение результатом инструмента.
        
        Returns:
            True если сообщение от инструмента
        """
        return self.role == "tool"
    
    def has_tool_calls(self) -> bool:
        """
        Проверить, содержит ли сообщение вызовы инструментов.
        
        Returns:
            True если сообщение содержит вызовы инструментов
        """
        return bool(self.tool_calls)
    
    def get_content_length(self) -> int:
        """
        Получить длину содержимого сообщения.
        
        Returns:
            Количество символов в content
        """
        return len(self.content)
    
    def to_llm_format(self) -> Dict[str, Any]:
        """
        Преобразовать сообщение в формат для LLM API.
        
        Формат совместим с OpenAI Chat Completions API.
        
        Returns:
            Словарь в формате LLM API
            
        Пример:
            >>> msg = Message(id="msg-1", role="user", content="Hello")
            >>> msg.to_llm_format()
            {'role': 'user', 'content': 'Hello'}
        """
        result: Dict[str, Any] = {
            "role": self.role,
        }
        
        # Content может быть None для assistant с tool_calls
        if self.content or self.role != "assistant":
            result["content"] = self.content
        
        # Добавить name если есть
        if self.name:
            result["name"] = self.name
        
        # Добавить tool_call_id для tool сообщений
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        
        # Добавить tool_calls для assistant сообщений
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        
        return result
    
    @classmethod
    def from_llm_format(cls, data: Dict[str, Any], message_id: str) -> "Message":
        """
        Создать сообщение из формата LLM API.
        
        Args:
            data: Данные в формате LLM API
            message_id: ID для нового сообщения
            
        Returns:
            Новый экземпляр Message
            
        Пример:
            >>> data = {'role': 'user', 'content': 'Hello'}
            >>> msg = Message.from_llm_format(data, "msg-1")
            >>> msg.role
            'user'
        """
        return cls(
            id=message_id,
            role=data.get("role", "user"),
            content=data.get("content", ""),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls")
        )
    
    def __repr__(self) -> str:
        """Строковое представление сообщения"""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (
            f"<Message(id='{self.id}', role='{self.role}', "
            f"content='{content_preview}')>"
        )

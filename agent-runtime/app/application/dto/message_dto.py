"""
Data Transfer Objects для сообщений.

DTO для передачи данных сообщений между слоями.
"""

from typing import Optional, Dict, Any, Literal, List
from datetime import datetime
from pydantic import BaseModel, Field

from ...domain.entities.message import Message


class MessageDTO(BaseModel):
    """
    DTO для сообщения.
    
    Используется для передачи данных сообщения между слоями.
    Совместим с форматом LLM API.
    
    Атрибуты:
        id: ID сообщения
        role: Роль отправителя
        content: Содержимое сообщения
        name: Имя отправителя (опционально)
        tool_call_id: ID вызова инструмента (опционально)
        tool_calls: Вызовы инструментов (опционально)
        created_at: Время создания
    
    Пример:
        >>> dto = MessageDTO(
        ...     id="msg-1",
        ...     role="user",
        ...     content="Привет!",
        ...     created_at=datetime.now()
        ... )
    """
    
    id: str = Field(description="ID сообщения")
    role: Literal["user", "assistant", "system", "tool"] = Field(
        description="Роль отправителя"
    )
    content: str = Field(description="Содержимое сообщения")
    name: Optional[str] = Field(default=None, description="Имя отправителя")
    tool_call_id: Optional[str] = Field(
        default=None,
        description="ID вызова инструмента"
    )
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Вызовы инструментов"
    )
    created_at: datetime = Field(description="Время создания сообщения")
    
    @classmethod
    def from_entity(cls, message: Message) -> "MessageDTO":
        """
        Создать DTO из доменной сущности.
        
        Args:
            message: Доменная сущность сообщения
            
        Returns:
            DTO сообщения
            
        Пример:
            >>> message = Message(id="msg-1", role="user", content="Hi")
            >>> dto = MessageDTO.from_entity(message)
        """
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            name=message.name,
            tool_call_id=message.tool_call_id,
            tool_calls=message.tool_calls,
            created_at=message.created_at
        )
    
    def to_llm_format(self) -> Dict[str, Any]:
        """
        Преобразовать в формат LLM API.
        
        Returns:
            Словарь в формате LLM API
            
        Пример:
            >>> dto = MessageDTO(id="msg-1", role="user", content="Hi", ...)
            >>> llm_format = dto.to_llm_format()
            >>> llm_format['role']
            'user'
        """
        result: Dict[str, Any] = {
            "role": self.role,
        }
        
        if self.content or self.role != "assistant":
            result["content"] = self.content
        
        if self.name:
            result["name"] = self.name
        
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        
        return result

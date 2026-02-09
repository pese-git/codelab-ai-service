"""
API схемы для операций с сообщениями.

Определяет структуру запросов для работы с сообщениями.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AddMessageRequest(BaseModel):
    """
    Запрос на добавление сообщения.
    
    Атрибуты:
        session_id: ID сессии
        role: Роль отправителя
        content: Содержимое сообщения
    
    Пример:
        {
            "session_id": "session-123",
            "role": "user",
            "content": "Создай новый файл"
        }
    """
    
    session_id: str = Field(description="ID сессии")
    role: str = Field(description="Роль отправителя (user, assistant, system, tool)")
    content: str = Field(description="Содержимое сообщения")


class MessageStreamRequest(BaseModel):
    """
    Запрос для streaming endpoint.
    
    Совместим с существующим протоколом Gateway ↔ Agent Runtime.
    
    Атрибуты:
        session_id: ID сессии (опционально, если не указан - создается новая сессия)
        message: Данные сообщения (может быть user_message, tool_result, switch_agent)
    
    Примеры:
        # Новая сессия (session_id не указан)
        {
            "message": {
                "type": "user_message",
                "content": "Привет!"
            }
        }
        
        # Существующая сессия
        {
            "session_id": "session-123",
            "message": {
                "type": "user_message",
                "content": "Продолжаем диалог"
            }
        }
    """
    
    session_id: Optional[str] = Field(
        default=None,
        description="ID сессии (если None, создается новая сессия автоматически)"
    )
    message: Dict[str, Any] = Field(
        description="Данные сообщения (user_message, tool_result, switch_agent, hitl_decision)"
    )

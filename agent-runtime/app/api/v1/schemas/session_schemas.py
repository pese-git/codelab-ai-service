"""
API схемы для операций с сессиями.

Определяет структуру запросов и ответов для endpoints сессий.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from ....application.dto import SessionDTO, SessionListItemDTO, MessageDTO


class CreateSessionRequest(BaseModel):
    """
    Запрос на создание новой сессии.
    
    Атрибуты:
        session_id: ID сессии (опционально, генерируется автоматически)
    
    Пример:
        {
            "session_id": "session-123"
        }
    """
    
    session_id: Optional[str] = Field(
        default=None,
        description="ID сессии (если не указан, генерируется автоматически)"
    )


class CreateSessionResponse(BaseModel):
    """
    Ответ на создание сессии.
    
    Атрибуты:
        id: ID созданной сессии
        message_count: Количество сообщений (всегда 0 для новой сессии)
        created_at: Время создания
        is_active: Флаг активности
        current_agent: Текущий агент
    
    Пример:
        {
            "id": "session-123",
            "message_count": 0,
            "created_at": "2026-01-18T21:00:00Z",
            "is_active": true,
            "current_agent": "orchestrator"
        }
    """
    
    id: str = Field(description="ID созданной сессии")
    message_count: int = Field(default=0, description="Количество сообщений")
    created_at: datetime = Field(description="Время создания")
    is_active: bool = Field(description="Флаг активности")
    current_agent: str = Field(description="Текущий агент")


class GetSessionResponse(BaseModel):
    """
    Ответ на получение сессии.
    
    Содержит полную информацию о сессии включая сообщения.
    
    Атрибуты:
        session: Данные сессии
    """
    
    session: SessionDTO = Field(description="Данные сессии")


class ListSessionsResponse(BaseModel):
    """
    Ответ на получение списка сессий.
    
    Атрибуты:
        sessions: Список сессий
        total: Общее количество
        limit: Лимит на странице
        offset: Смещение
    
    Пример:
        {
            "sessions": [...],
            "total": 25,
            "limit": 10,
            "offset": 0
        }
    """
    
    sessions: List[SessionListItemDTO] = Field(description="Список сессий")
    total: int = Field(description="Общее количество сессий")
    limit: int = Field(description="Лимит на странице")
    offset: int = Field(description="Смещение")

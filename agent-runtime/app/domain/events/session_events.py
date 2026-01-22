"""
Доменные события для сессий.

События описывают важные бизнес-события, связанные с сессиями диалога.
"""

from typing import Optional
from .base import DomainEvent


class SessionCreated(DomainEvent):
    """
    Событие: сессия создана.
    
    Публикуется когда создается новая сессия диалога.
    
    Атрибуты:
        session_id: ID созданной сессии
        created_by: Кто создал сессию (user, system и т.д.)
    
    Пример:
        >>> event = SessionCreated(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     created_by="user"
        ... )
    """
    
    session_id: str
    created_by: str = "system"


class MessageReceived(DomainEvent):
    """
    Событие: получено сообщение.
    
    Публикуется когда в сессию добавляется новое сообщение.
    
    Атрибуты:
        session_id: ID сессии
        message_id: ID сообщения
        role: Роль отправителя (user, assistant, system, tool)
        content_length: Длина содержимого сообщения
    
    Пример:
        >>> event = MessageReceived(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     message_id="msg-1",
        ...     role="user",
        ...     content_length=100
        ... )
    """
    
    session_id: str
    message_id: str
    role: str
    content_length: int


class ConversationCompleted(DomainEvent):
    """
    Событие: разговор завершен.
    
    Публикуется когда агент завершает обработку сообщения
    и отправляет финальный ответ.
    
    Атрибуты:
        session_id: ID сессии
        total_messages: Общее количество сообщений в сессии
        duration_seconds: Длительность разговора в секундах
        final_agent: Агент, который завершил разговор
    
    Пример:
        >>> event = ConversationCompleted(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     total_messages=10,
        ...     duration_seconds=120.5,
        ...     final_agent="coder"
        ... )
    """
    
    session_id: str
    total_messages: int
    duration_seconds: float
    final_agent: str


class SessionDeactivated(DomainEvent):
    """
    Событие: сессия деактивирована.
    
    Публикуется когда сессия деактивируется (закрывается).
    
    Атрибуты:
        session_id: ID сессии
        reason: Причина деактивации
        message_count: Количество сообщений на момент деактивации
    
    Пример:
        >>> event = SessionDeactivated(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     reason="User logged out",
        ...     message_count=15
        ... )
    """
    
    session_id: str
    reason: str
    message_count: int


class SessionExpired(DomainEvent):
    """
    Событие: сессия истекла.
    
    Публикуется когда сессия автоматически истекает
    из-за неактивности.
    
    Атрибуты:
        session_id: ID сессии
        reason: Причина истечения
        inactive_hours: Количество часов неактивности
    
    Пример:
        >>> event = SessionExpired(
        ...     aggregate_id="session-1",
        ...     session_id="session-1",
        ...     reason="Inactive for 24 hours",
        ...     inactive_hours=24
        ... )
    """
    
    session_id: str
    reason: str
    inactive_hours: float

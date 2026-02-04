"""
Conversation Domain Events.

События жизненного цикла Conversation entity.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from ...shared.domain_event import DomainEvent


class ConversationStarted(DomainEvent):
    """
    Событие: Conversation создан.
    
    Публикуется при создании новой conversation.
    
    Атрибуты:
        conversation_id: ID conversation
        title: Заголовок (если установлен)
        metadata: Дополнительные метаданные
    """
    
    conversation_id: str
    title: Optional[str]
    metadata: Dict[str, Any]
    
    def __init__(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None
    ):
        super().__init__(occurred_at=occurred_at)
        self.conversation_id = conversation_id
        self.title = title
        self.metadata = metadata or {}


class MessageAdded(DomainEvent):
    """
    Событие: Сообщение добавлено в conversation.
    
    Публикуется при добавлении нового сообщения.
    
    Атрибуты:
        conversation_id: ID conversation
        message_id: ID добавленного сообщения
        role: Роль сообщения (user, assistant, system, tool)
        content_length: Длина содержимого
        has_tool_calls: Содержит ли tool calls
    """
    
    conversation_id: str
    message_id: str
    role: str
    content_length: int
    has_tool_calls: bool
    
    def __init__(
        self,
        conversation_id: str,
        message_id: str,
        role: str,
        content_length: int,
        has_tool_calls: bool = False,
        occurred_at: Optional[datetime] = None
    ):
        super().__init__(occurred_at=occurred_at)
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.role = role
        self.content_length = content_length
        self.has_tool_calls = has_tool_calls


class ConversationDeactivated(DomainEvent):
    """
    Событие: Conversation деактивирован.
    
    Публикуется при деактивации conversation.
    
    Атрибуты:
        conversation_id: ID conversation
        reason: Причина деактивации
    """
    
    conversation_id: str
    reason: Optional[str]
    
    def __init__(
        self,
        conversation_id: str,
        reason: Optional[str] = None,
        occurred_at: Optional[datetime] = None
    ):
        super().__init__(occurred_at=occurred_at)
        self.conversation_id = conversation_id
        self.reason = reason


class ConversationActivated(DomainEvent):
    """
    Событие: Conversation активирован.
    
    Публикуется при активации conversation.
    
    Атрибуты:
        conversation_id: ID conversation
    """
    
    conversation_id: str
    
    def __init__(
        self,
        conversation_id: str,
        occurred_at: Optional[datetime] = None
    ):
        super().__init__(occurred_at=occurred_at)
        self.conversation_id = conversation_id


class MessagesCleared(DomainEvent):
    """
    Событие: Все сообщения очищены.
    
    Публикуется при очистке всех сообщений из conversation.
    
    Атрибуты:
        conversation_id: ID conversation
        cleared_count: Количество удаленных сообщений
    """
    
    conversation_id: str
    cleared_count: int
    
    def __init__(
        self,
        conversation_id: str,
        cleared_count: int,
        occurred_at: Optional[datetime] = None
    ):
        super().__init__(occurred_at=occurred_at)
        self.conversation_id = conversation_id
        self.cleared_count = cleared_count


class ToolMessagesCleared(DomainEvent):
    """
    Событие: Tool messages очищены.
    
    Публикуется при очистке tool-related сообщений.
    
    Атрибуты:
        conversation_id: ID conversation
        cleared_count: Количество удаленных сообщений
        preserved_result: Сохраненный результат (если есть)
    """
    
    conversation_id: str
    cleared_count: int
    preserved_result: Optional[str]
    
    def __init__(
        self,
        conversation_id: str,
        cleared_count: int,
        preserved_result: Optional[str] = None,
        occurred_at: Optional[datetime] = None
    ):
        super().__init__(occurred_at=occurred_at)
        self.conversation_id = conversation_id
        self.cleared_count = cleared_count
        self.preserved_result = preserved_result

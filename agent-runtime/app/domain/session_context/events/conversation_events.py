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
    title: Optional[str] = None
    metadata: Dict[str, Any] = {}


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
    has_tool_calls: bool = False


class ConversationDeactivated(DomainEvent):
    """
    Событие: Conversation деактивирован.
    
    Публикуется при деактивации conversation.
    
    Атрибуты:
        conversation_id: ID conversation
        reason: Причина деактивации
    """
    
    conversation_id: str
    reason: Optional[str] = None


class ConversationActivated(DomainEvent):
    """
    Событие: Conversation активирован.
    
    Публикуется при активации conversation.
    
    Атрибуты:
        conversation_id: ID conversation
    """
    
    conversation_id: str


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
    preserved_result: Optional[str] = None


class SnapshotCreated(DomainEvent):
    """
    Событие: Snapshot создан.
    
    Публикуется при создании snapshot conversation.
    
    Атрибуты:
        conversation_id: ID conversation
        snapshot_id: ID созданного snapshot
        message_count: Количество сообщений в snapshot
    """
    
    conversation_id: str
    snapshot_id: str
    message_count: int


class SnapshotRestored(DomainEvent):
    """
    Событие: Snapshot восстановлен.
    
    Публикуется при восстановлении conversation из snapshot.
    
    Атрибуты:
        conversation_id: ID conversation
        snapshot_id: ID восстановленного snapshot
        restored_message_count: Количество восстановленных сообщений
    """
    
    conversation_id: str
    snapshot_id: str
    restored_message_count: int

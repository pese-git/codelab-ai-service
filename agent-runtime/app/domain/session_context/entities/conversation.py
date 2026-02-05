"""
Conversation Entity (рефакторинг Session).

Упрощенная версия Session с использованием DDD паттернов:
- Value Objects вместо примитивов
- Domain Events для отслеживания изменений
- Делегирование сложной логики в Domain Services
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import Field

from ...shared.base_entity import Entity, BaseEntity
from ..value_objects import ConversationId, MessageCollection
from ..events import (
    ConversationStarted,
    MessageAdded,
    ConversationDeactivated,
    ConversationActivated,
    MessagesCleared,
)
from ...entities.message import Message


class Conversation(BaseEntity):
    """
    Conversation Entity - упрощенная версия Session.
    
    Основные изменения:
    - Использует ConversationId вместо str
    - Использует MessageCollection вместо List[Message]
    - Генерирует Domain Events
    - Делегирует snapshot/cleanup логику в Services
    
    Размер: ~120 строк (вместо 501 в Session)
    Сложность: Низкая (основные операции)
    Зависимости: 3 (BaseEntity, Value Objects, Events)
    
    Атрибуты:
        conversation_id: Typed ID conversation
        messages: Коллекция сообщений (Value Object)
        title: Заголовок conversation
        description: Описание
        last_activity: Время последней активности
        is_active: Флаг активности
        metadata: Дополнительные метаданные
    
    Пример:
        >>> conv_id = ConversationId.generate()
        >>> conv = Conversation.create(conv_id)
        >>> msg = Message(id="msg-1", role="user", content="Hello")
        >>> conv.add_message(msg)
    """
    
    conversation_id: ConversationId = Field(
        ...,
        description="Typed ID conversation"
    )
    
    messages: MessageCollection = Field(
        default_factory=lambda: MessageCollection.empty(),
        description="Коллекция сообщений"
    )
    
    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Заголовок conversation"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Описание conversation"
    )
    
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время последней активности"
    )
    
    is_active: bool = Field(
        default=True,
        description="Флаг активности"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные"
    )
    
    @classmethod
    def create(
        cls,
        conversation_id: ConversationId,
        title: Optional[str] = None,
        description: Optional[str] = None,
        max_messages: int = 1000
    ) -> "Conversation":
        """
        Создать новый conversation.
        
        Args:
            conversation_id: ID conversation
            title: Заголовок (опционально)
            description: Описание (опционально)
            max_messages: Максимум сообщений
            
        Returns:
            Новый conversation с ConversationStarted event
        """
        conversation = cls(
            id=conversation_id.value,
            conversation_id=conversation_id,
            messages=MessageCollection.empty(max_size=max_messages),
            title=title,
            description=description
        )
        
        # Генерируем domain event
        conversation.record_event(
            ConversationStarted(
                conversation_id=conversation_id.value,
                title=title,
                metadata=conversation.metadata.copy()
            )
        )
        
        return conversation
    
    def add_message(self, message: Message) -> None:
        """
        Добавить сообщение в conversation.
        
        Args:
            message: Сообщение для добавления
            
        Raises:
            ValueError: Если conversation неактивен или превышен лимит
        """
        # Проверка активности
        if not self.is_active:
            raise ValueError(
                f"Невозможно добавить сообщение в неактивный conversation '{self.conversation_id.value}'"
            )
        
        # Добавить через MessageCollection (с валидацией лимита)
        self.messages = self.messages.add(message)
        
        # Обновить активность
        self.last_activity = datetime.now(timezone.utc)
        self.mark_updated()
        
        # Автоматически установить title из первого user message
        if not self.title and message.is_user_message():
            self._set_title_from_message(message)
        
        # Генерируем domain event
        self.record_event(
            MessageAdded(
                conversation_id=self.conversation_id.value,
                message_id=message.id,
                role=message.role,
                content_length=message.get_content_length(),
                has_tool_calls=message.has_tool_calls()
            )
        )
    
    def _set_title_from_message(self, message: Message) -> None:
        """
        Установить заголовок из сообщения.
        
        Args:
            message: Сообщение для извлечения заголовка
        """
        content = message.content.strip()
        if content:
            self.title = content[:500] if len(content) > 500 else content
    
    def get_message_count(self) -> int:
        """
        Получить количество сообщений.
        
        Returns:
            Количество сообщений
        """
        # Если есть кэшированное значение, используем его
        if '_message_count' in self.metadata:
            return self.metadata['_message_count']
        
        return self.messages.count()
    
    def is_empty(self) -> bool:
        """
        Проверить, пуст ли conversation.
        
        Returns:
            True если нет сообщений
        """
        return self.messages.is_empty()
    
    def deactivate(self, reason: Optional[str] = None) -> None:
        """
        Деактивировать conversation.
        
        Args:
            reason: Причина деактивации
        """
        self.is_active = False
        self.mark_updated()
        
        if reason:
            self.metadata["deactivation_reason"] = reason
            self.metadata["deactivated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Генерируем domain event
        self.record_event(
            ConversationDeactivated(
                conversation_id=self.conversation_id.value,
                reason=reason
            )
        )
    
    def activate(self) -> None:
        """
        Активировать conversation.
        """
        self.is_active = True
        self.mark_updated()
        
        # Генерируем domain event
        self.record_event(
            ConversationActivated(
                conversation_id=self.conversation_id.value
            )
        )
    
    def clear_messages(self) -> int:
        """
        Очистить все сообщения.
        
        Returns:
            Количество удаленных сообщений
        """
        count = self.messages.count()
        self.messages = self.messages.clear()
        self.mark_updated()
        
        # Генерируем domain event
        if count > 0:
            self.record_event(
                MessagesCleared(
                    conversation_id=self.conversation_id.value,
                    cleared_count=count
                )
            )
        
        return count
    
    def get_duration_seconds(self) -> float:
        """
        Получить длительность conversation в секундах.
        
        Returns:
            Длительность в секундах
        """
        return (self.last_activity - self.created_at).total_seconds()
    
    def __repr__(self) -> str:
        """Строковое представление"""
        title_preview = self.title[:30] + "..." if self.title and len(self.title) > 30 else self.title
        return (
            f"<Conversation(id='{self.conversation_id.value}', "
            f"title='{title_preview}', "
            f"messages={self.messages.count()}, "
            f"active={self.is_active})>"
        )

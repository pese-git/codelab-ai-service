"""
Доменная сущность Session (Сессия).

Представляет сессию диалога между пользователем и AI агентом.
Содержит историю сообщений и метаданные сессии.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import Field, field_validator

from .base import Entity
from .message import Message
from ...core.errors import MessageValidationError


class Session(Entity):
    """
    Доменная сущность сессии.
    
    Сессия представляет собой диалог между пользователем и AI агентом.
    Содержит историю всех сообщений и отслеживает активность.
    
    Атрибуты:
        messages: Список сообщений в сессии
        title: Заголовок сессии (генерируется из первого сообщения)
        description: Описание сессии (опционально)
        last_activity: Время последней активности
        is_active: Флаг активности сессии
        max_messages: Максимальное количество сообщений (для предотвращения переполнения)
    
    Бизнес-правила:
        - Сессия не может содержать более max_messages сообщений
        - При добавлении сообщения обновляется last_activity
        - Заголовок автоматически генерируется из первого пользовательского сообщения
        - Неактивные сессии не могут принимать новые сообщения
    
    Пример:
        >>> session = Session(id="session-1")
        >>> msg = Message(id="msg-1", role="user", content="Привет")
        >>> session.add_message(msg)
        >>> session.get_message_count()
        1
    """
    
    messages: List[Message] = Field(
        default_factory=list,
        description="Список сообщений в сессии"
    )
    
    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Заголовок сессии"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Описание сессии"
    )
    
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время последней активности в сессии"
    )
    
    is_active: bool = Field(
        default=True,
        description="Флаг активности сессии"
    )
    
    max_messages: int = Field(
        default=1000,
        description="Максимальное количество сообщений в сессии"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные сессии"
    )
    
    def add_message(self, message: Message) -> None:
        """
        Добавить сообщение в сессию.
        
        Обновляет last_activity и автоматически генерирует title
        из первого пользовательского сообщения.
        
        Args:
            message: Сообщение для добавления
            
        Raises:
            ValueError: Если сессия неактивна
            MessageValidationError: Если превышен лимит сообщений
            
        Пример:
            >>> session = Session(id="session-1")
            >>> msg = Message(id="msg-1", role="user", content="Привет")
            >>> session.add_message(msg)
        """
        # Проверка активности сессии
        if not self.is_active:
            raise ValueError(
                f"Невозможно добавить сообщение в неактивную сессию '{self.id}'"
            )
        
        # Проверка лимита сообщений
        if len(self.messages) >= self.max_messages:
            raise MessageValidationError(
                field="messages",
                reason=f"Превышен лимит сообщений ({self.max_messages})",
                details={"session_id": self.id, "current_count": len(self.messages)}
            )
        
        # Добавить сообщение
        self.messages.append(message)
        
        # Обновить время активности
        self.last_activity = datetime.now(timezone.utc)
        self.mark_updated()
        
        # Автоматически установить title из первого пользовательского сообщения
        if not self.title and message.is_user_message():
            self._set_title_from_message(message)
    
    def _set_title_from_message(self, message: Message) -> None:
        """
        Установить заголовок сессии из сообщения.
        
        Берет первые 500 символов содержимого сообщения.
        
        Args:
            message: Сообщение для извлечения заголовка
        """
        content = message.content.strip()
        if content:
            self.title = content[:500] if len(content) > 500 else content
    
    def get_message_count(self) -> int:
        """
        Получить количество сообщений в сессии.
        
        Если сообщения не загружены (например, при получении списка сессий),
        использует кэшированное значение из метаданных.
        
        Returns:
            Количество сообщений
        """
        # Если есть кэшированное значение в метаданных, используем его
        if '_message_count' in self.metadata:
            return self.metadata['_message_count']
        
        # Иначе считаем из загруженных сообщений
        return len(self.messages)
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """
        Получить последние N сообщений.
        
        Полезно для контекста LLM с ограниченным окном.
        
        Args:
            limit: Максимальное количество сообщений
            
        Returns:
            Список последних сообщений
            
        Пример:
            >>> recent = session.get_recent_messages(limit=5)
            >>> len(recent) <= 5
            True
        """
        return self.messages[-limit:] if self.messages else []
    
    def get_messages_by_role(self, role: str) -> List[Message]:
        """
        Получить все сообщения определенной роли.
        
        Args:
            role: Роль сообщений (user, assistant, system, tool)
            
        Returns:
            Список сообщений с указанной ролью
            
        Пример:
            >>> user_messages = session.get_messages_by_role("user")
        """
        return [msg for msg in self.messages if msg.role == role]
    
    def get_history_for_llm(self, max_messages: Optional[int] = None) -> List[Dict]:
        """
        Получить историю сообщений в формате для LLM.
        
        Args:
            max_messages: Максимальное количество сообщений (None = все)
            
        Returns:
            Список сообщений в формате LLM API
            
        Пример:
            >>> history = session.get_history_for_llm(max_messages=10)
            >>> history[0]['role']
            'user'
        """
        messages = self.messages
        if max_messages:
            messages = self.get_recent_messages(max_messages)
        
        return [msg.to_llm_format() for msg in messages]
    
    def deactivate(self, reason: Optional[str] = None) -> None:
        """
        Деактивировать сессию.
        
        Деактивированная сессия не может принимать новые сообщения.
        
        Args:
            reason: Причина деактивации (опционально)
            
        Пример:
            >>> session.deactivate(reason="User logged out")
            >>> session.is_active
            False
        """
        self.is_active = False
        self.mark_updated()
        
        if reason:
            self.metadata["deactivation_reason"] = reason
            self.metadata["deactivated_at"] = datetime.now(timezone.utc).isoformat()
    
    def activate(self) -> None:
        """
        Активировать сессию.
        
        Позволяет снова добавлять сообщения в сессию.
        
        Пример:
            >>> session.activate()
            >>> session.is_active
            True
        """
        self.is_active = True
        self.mark_updated()
    
    def clear_messages(self) -> int:
        """
        Очистить все сообщения из сессии.
        
        Полезно для сброса контекста при сохранении сессии.
        
        Returns:
            Количество удаленных сообщений
            
        Пример:
            >>> count = session.clear_messages()
            >>> session.get_message_count()
            0
        """
        count = len(self.messages)
        self.messages.clear()
        self.mark_updated()
        return count
    
    def is_empty(self) -> bool:
        """
        Проверить, пуста ли сессия (нет сообщений).
        
        Returns:
            True если сессия не содержит сообщений
        """
        return len(self.messages) == 0
    
    def get_duration_seconds(self) -> float:
        """
        Получить длительность сессии в секундах.
        
        Вычисляется как разница между last_activity и created_at.
        
        Returns:
            Длительность сессии в секундах
            
        Пример:
            >>> duration = session.get_duration_seconds()
            >>> duration > 0
            True
        """
        return (self.last_activity - self.created_at).total_seconds()
    
    def __repr__(self) -> str:
        """Строковое представление сессии"""
        title_preview = self.title[:30] + "..." if self.title and len(self.title) > 30 else self.title
        return (
            f"<Session(id='{self.id}', "
            f"title='{title_preview}', "
            f"messages={len(self.messages)}, "
            f"active={self.is_active})>"
        )

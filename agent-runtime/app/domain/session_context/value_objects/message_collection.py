"""
MessageCollection Value Object.

Инкапсулирует логику работы с коллекцией сообщений в conversation.
Решает проблему Primitive Obsession для List[Message].
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, timezone

from ...shared.value_object import ValueObject
# Import from entities to avoid circular dependency with __init__.py
from ...entities.message import Message


class MessageCollection(ValueObject):
    """
    Value Object для коллекции сообщений.
    
    Инкапсулирует:
    - Валидацию лимитов
    - Фильтрацию по роли
    - Получение последних сообщений
    - Конвертацию в LLM формат
    - Очистку tool messages
    
    Атрибуты:
        messages: Список сообщений
        max_size: Максимальный размер коллекции
    
    Пример:
        >>> collection = MessageCollection.empty(max_size=1000)
        >>> msg = Message(id="msg-1", role="user", content="Hello")
        >>> new_collection = collection.add(msg)
        >>> new_collection.count()
        1
    """
    
    messages: List[Message]
    max_size: int
    
    def __init__(self, messages: List[Message], max_size: int = 1000):
        """
        Создать коллекцию сообщений.
        
        Args:
            messages: Список сообщений
            max_size: Максимальный размер коллекции
            
        Raises:
            ValueError: Если размер превышает max_size
        """
        if len(messages) > max_size:
            raise ValueError(
                f"Размер коллекции ({len(messages)}) превышает максимум ({max_size})"
            )
        
        super().__init__(messages=messages, max_size=max_size)
    
    @classmethod
    def empty(cls, max_size: int = 1000) -> "MessageCollection":
        """
        Создать пустую коллекцию.
        
        Args:
            max_size: Максимальный размер коллекции
            
        Returns:
            Пустая коллекция
        """
        return cls(messages=[], max_size=max_size)
    
    @classmethod
    def from_list(
        cls,
        messages: List[Message],
        max_size: int = 1000
    ) -> "MessageCollection":
        """
        Создать коллекцию из списка сообщений.
        
        Args:
            messages: Список сообщений
            max_size: Максимальный размер коллекции
            
        Returns:
            Новая коллекция
        """
        return cls(messages=messages.copy(), max_size=max_size)
    
    def add(self, message: Message) -> "MessageCollection":
        """
        Добавить сообщение в коллекцию.
        
        Возвращает новую коллекцию (immutable).
        
        Args:
            message: Сообщение для добавления
            
        Returns:
            Новая коллекция с добавленным сообщением
            
        Raises:
            ValueError: Если превышен лимит
        """
        if len(self.messages) >= self.max_size:
            raise ValueError(
                f"Невозможно добавить сообщение: достигнут лимит ({self.max_size})"
            )
        
        new_messages = self.messages.copy()
        new_messages.append(message)
        return MessageCollection(messages=new_messages, max_size=self.max_size)
    
    def count(self) -> int:
        """
        Получить количество сообщений.
        
        Returns:
            Количество сообщений в коллекции
        """
        return len(self.messages)
    
    def is_empty(self) -> bool:
        """
        Проверить, пуста ли коллекция.
        
        Returns:
            True если коллекция пуста
        """
        return len(self.messages) == 0
    
    def is_full(self) -> bool:
        """
        Проверить, заполнена ли коллекция.
        
        Returns:
            True если достигнут max_size
        """
        return len(self.messages) >= self.max_size
    
    def get_recent(self, limit: int) -> List[Message]:
        """
        Получить последние N сообщений.
        
        Args:
            limit: Максимальное количество сообщений
            
        Returns:
            Список последних сообщений
        """
        if limit <= 0:
            return []
        return self.messages[-limit:] if self.messages else []
    
    def filter_by_role(
        self,
        role: Literal["user", "assistant", "system", "tool"]
    ) -> List[Message]:
        """
        Получить сообщения определенной роли.
        
        Args:
            role: Роль для фильтрации
            
        Returns:
            Список сообщений с указанной ролью
        """
        return [msg for msg in self.messages if msg.role == role]
    
    def get_last_assistant_message(self) -> Optional[Message]:
        """
        Получить последнее assistant message без tool_calls.
        
        Returns:
            Последнее assistant message или None
        """
        for msg in reversed(self.messages):
            if msg.role == "assistant" and not msg.tool_calls:
                return msg
        return None
    
    def to_llm_format(self, max_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Конвертировать в формат для LLM API.
        
        Args:
            max_messages: Максимальное количество сообщений (None = все)
            
        Returns:
            Список сообщений в формате LLM API
        """
        messages = self.messages
        if max_messages is not None and max_messages > 0:
            messages = self.get_recent(max_messages)
        
        return [msg.to_llm_format() for msg in messages]
    
    def clear_tool_messages(self) -> tuple["MessageCollection", int]:
        """
        Удалить tool-related messages из коллекции.
        
        Удаляет:
        - Assistant messages с tool_calls
        - Tool result messages
        
        Сохраняет:
        - User messages
        - System messages
        - Assistant messages без tool_calls
        
        Returns:
            Кортеж (новая коллекция, количество удаленных)
        """
        original_count = len(self.messages)
        
        filtered_messages = [
            msg for msg in self.messages
            if not (
                (msg.role == "assistant" and msg.tool_calls) or
                msg.role == "tool"
            )
        ]
        
        removed_count = original_count - len(filtered_messages)
        
        new_collection = MessageCollection(
            messages=filtered_messages,
            max_size=self.max_size
        )
        
        return new_collection, removed_count
    
    def clear(self) -> "MessageCollection":
        """
        Очистить все сообщения.
        
        Returns:
            Пустая коллекция с тем же max_size
        """
        return MessageCollection.empty(max_size=self.max_size)
    
    def replace_with(self, messages: List[Message]) -> "MessageCollection":
        """
        Заменить все сообщения новым списком.
        
        Используется при восстановлении из snapshot.
        
        Args:
            messages: Новый список сообщений
            
        Returns:
            Новая коллекция с замененными сообщениями
        """
        return MessageCollection(messages=messages.copy(), max_size=self.max_size)
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        Конвертировать в список словарей для сериализации.
        
        Returns:
            Список словарей с данными сообщений
        """
        return [msg.model_dump() for msg in self.messages]
    
    @classmethod
    def from_dict_list(
        cls,
        data: List[Dict[str, Any]],
        max_size: int = 1000
    ) -> "MessageCollection":
        """
        Создать коллекцию из списка словарей.
        
        Args:
            data: Список словарей с данными сообщений
            max_size: Максимальный размер коллекции
            
        Returns:
            Новая коллекция
        """
        messages = [Message(**msg_dict) for msg_dict in data]
        return cls(messages=messages, max_size=max_size)
    
    def __len__(self) -> int:
        """Поддержка len()"""
        return len(self.messages)
    
    def __iter__(self):
        """Поддержка итерации"""
        return iter(self.messages)
    
    def __getitem__(self, index: int) -> Message:
        """Поддержка индексации"""
        return self.messages[index]
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"<MessageCollection(count={len(self.messages)}, max_size={self.max_size})>"

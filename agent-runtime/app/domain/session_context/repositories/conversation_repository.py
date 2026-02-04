"""
Conversation Repository Interface.

Определяет контракт для персистентности Conversation entities.
"""

from abc import abstractmethod
from typing import Optional, List
from datetime import datetime

from ...shared.repository import Repository
from ..entities import Conversation
from ..value_objects import ConversationId


class ConversationRepository(Repository[Conversation]):
    """
    Repository interface для Conversation entities.
    
    Определяет операции персистентности для conversations.
    Реализация будет в infrastructure слое.
    
    Методы:
        - find_by_id: Найти conversation по ID
        - find_by_user_id: Найти все conversations пользователя
        - save: Сохранить conversation
        - delete: Удалить conversation
        - exists: Проверить существование
    
    Пример:
        >>> class ConversationRepositoryImpl(ConversationRepository):
        ...     async def find_by_id(self, conv_id: ConversationId):
        ...         # Implementation
        ...         pass
    """
    
    @abstractmethod
    async def find_by_id(
        self,
        conversation_id: ConversationId,
        load_messages: bool = True
    ) -> Optional[Conversation]:
        """
        Найти conversation по ID.
        
        Args:
            conversation_id: ID conversation
            load_messages: Загружать ли сообщения (для оптимизации списков)
            
        Returns:
            Conversation или None если не найден
            
        Пример:
            >>> conv_id = ConversationId("conv-123")
            >>> conversation = await repo.find_by_id(conv_id)
        """
        pass
    
    @abstractmethod
    async def find_by_user_id(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        load_messages: bool = False
    ) -> List[Conversation]:
        """
        Найти все conversations пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество результатов
            offset: Смещение для пагинации
            load_messages: Загружать ли сообщения
            
        Returns:
            Список conversations
            
        Пример:
            >>> conversations = await repo.find_by_user_id("user-123", limit=10)
        """
        pass
    
    @abstractmethod
    async def find_active_by_user_id(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Conversation]:
        """
        Найти активные conversations пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество результатов
            
        Returns:
            Список активных conversations
            
        Пример:
            >>> active = await repo.find_active_by_user_id("user-123")
        """
        pass
    
    @abstractmethod
    async def save(self, conversation: Conversation) -> None:
        """
        Сохранить conversation.
        
        Создает новый или обновляет существующий.
        
        Args:
            conversation: Conversation для сохранения
            
        Пример:
            >>> await repo.save(conversation)
        """
        pass
    
    @abstractmethod
    async def delete(self, conversation_id: ConversationId) -> bool:
        """
        Удалить conversation.
        
        Args:
            conversation_id: ID conversation для удаления
            
        Returns:
            True если удален, False если не найден
            
        Пример:
            >>> conv_id = ConversationId("conv-123")
            >>> deleted = await repo.delete(conv_id)
        """
        pass
    
    @abstractmethod
    async def exists(self, conversation_id: ConversationId) -> bool:
        """
        Проверить существование conversation.
        
        Args:
            conversation_id: ID для проверки
            
        Returns:
            True если существует
            
        Пример:
            >>> conv_id = ConversationId("conv-123")
            >>> exists = await repo.exists(conv_id)
        """
        pass
    
    @abstractmethod
    async def count_by_user_id(self, user_id: str) -> int:
        """
        Подсчитать количество conversations пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество conversations
            
        Пример:
            >>> count = await repo.count_by_user_id("user-123")
        """
        pass
    
    @abstractmethod
    async def find_inactive_since(
        self,
        since: datetime,
        limit: int = 100
    ) -> List[Conversation]:
        """
        Найти неактивные conversations с определенной даты.
        
        Используется для cleanup задач.
        
        Args:
            since: Дата для фильтрации
            limit: Максимальное количество результатов
            
        Returns:
            Список неактивных conversations
            
        Пример:
            >>> from datetime import datetime, timedelta
            >>> since = datetime.now() - timedelta(days=30)
            >>> inactive = await repo.find_inactive_since(since)
        """
        pass

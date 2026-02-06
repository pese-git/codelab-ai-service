"""
Реализация ConversationRepository с использованием SQLAlchemy.

Конкретная реализация интерфейса ConversationRepository для работы с БД.
"""

import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from ....domain.session_context.repositories import ConversationRepository
from ....domain.session_context.entities import Conversation
from ....domain.session_context.value_objects import ConversationId
from ..models import SessionModel
from ..mappers import ConversationMapper

logger = logging.getLogger("agent-runtime.infrastructure.conversation_repository")


class ConversationRepositoryImpl(ConversationRepository):
    """
    Реализация репозитория conversations для SQLAlchemy.
    
    Использует ConversationMapper для преобразования между
    доменными сущностями и моделями БД.
    
    Атрибуты:
        _db: Сессия БД SQLAlchemy
        _mapper: Mapper для преобразования данных
    
    Пример:
        >>> repo = ConversationRepositoryImpl(db_session)
        >>> conv_id = ConversationId("conv-123")
        >>> conversation = await repo.find_by_id(conv_id)
    """
    
    def __init__(self, db: AsyncSession):
        """
        Инициализировать репозиторий.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
        self._mapper = ConversationMapper()
    
    async def find_by_id(
        self,
        conversation_id: ConversationId,
        load_messages: bool = True
    ) -> Optional[Conversation]:
        """
        Найти conversation по ID.
        
        Args:
            conversation_id: ID conversation
            load_messages: Загружать ли сообщения
            
        Returns:
            Conversation или None если не найден
        """
        result = await self._db.execute(
            select(SessionModel).where(
                SessionModel.id == conversation_id.value,
                SessionModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        
        if not model:
            logger.debug(f"Conversation {conversation_id.value} not found")
            return None
        
        conversation = await self._mapper.to_entity(model, self._db, load_messages)
        logger.debug(f"Found conversation {conversation_id.value}")
        return conversation
    
    async def find_by_user_id(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        load_messages: bool = False
    ) -> List[Conversation]:
        """
        Найти все conversations пользователя.
        
        Note: В текущей реализации user_id хранится в metadata.
        Если нужна оптимизация, добавьте отдельное поле user_id в SessionModel.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество результатов
            offset: Смещение для пагинации
            load_messages: Загружать ли сообщения
            
        Returns:
            Список conversations
        """
        # TODO: Добавить поле user_id в SessionModel для оптимизации
        # Пока возвращаем все активные сессии
        result = await self._db.execute(
            select(SessionModel)
            .where(SessionModel.deleted_at.is_(None))
            .order_by(SessionModel.last_activity.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        
        conversations = []
        for model in models:
            conversation = await self._mapper.to_entity(model, self._db, load_messages)
            conversations.append(conversation)
        
        logger.debug(f"Found {len(conversations)} conversations for user {user_id}")
        return conversations
    
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
        """
        result = await self._db.execute(
            select(SessionModel)
            .where(
                SessionModel.is_active == True,
                SessionModel.deleted_at.is_(None)
            )
            .order_by(SessionModel.last_activity.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        
        conversations = []
        for model in models:
            conversation = await self._mapper.to_entity(model, self._db, load_messages=False)
            conversations.append(conversation)
        
        logger.debug(f"Found {len(conversations)} active conversations for user {user_id}")
        return conversations
    
    async def save(self, conversation: Conversation) -> None:
        """
        Сохранить conversation.
        
        Создает новый или обновляет существующий.
        
        Args:
            conversation: Conversation для сохранения
        """
        await self._mapper.to_model(conversation, self._db)
        await self._db.flush()
        logger.debug(f"Saved conversation {conversation.conversation_id.value}")
    
    async def delete(self, conversation_id: ConversationId) -> bool:
        """
        Удалить conversation (soft delete).
        
        Args:
            conversation_id: ID conversation для удаления
            
        Returns:
            True если удален, False если не найден
        """
        result = await self._db.execute(
            select(SessionModel).where(
                SessionModel.id == conversation_id.value,
                SessionModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        
        if not model:
            logger.debug(f"Conversation {conversation_id.value} not found for deletion")
            return False
        
        # Soft delete
        model.deleted_at = datetime.utcnow()
        model.is_active = False
        await self._db.flush()
        
        logger.info(f"Deleted conversation {conversation_id.value}")
        return True
    
    async def exists(self, conversation_id: ConversationId) -> bool:
        """
        Проверить существование conversation.
        
        Args:
            conversation_id: ID для проверки
            
        Returns:
            True если существует
        """
        result = await self._db.execute(
            select(func.count(SessionModel.id)).where(
                SessionModel.id == conversation_id.value,
                SessionModel.deleted_at.is_(None)
            )
        )
        count = result.scalar()
        return count > 0
    
    async def count_by_user_id(self, user_id: str) -> int:
        """
        Подсчитать количество conversations пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество conversations
        """
        # TODO: Добавить поле user_id в SessionModel для оптимизации
        result = await self._db.execute(
            select(func.count(SessionModel.id)).where(
                SessionModel.deleted_at.is_(None)
            )
        )
        count = result.scalar()
        logger.debug(f"User {user_id} has {count} conversations")
        return count
    
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
        """
        result = await self._db.execute(
            select(SessionModel)
            .where(
                SessionModel.is_active == False,
                SessionModel.last_activity < since,
                SessionModel.deleted_at.is_(None)
            )
            .order_by(SessionModel.last_activity.asc())
            .limit(limit)
        )
        models = result.scalars().all()
        
        conversations = []
        for model in models:
            conversation = await self._mapper.to_entity(model, self._db, load_messages=False)
            conversations.append(conversation)
        
        logger.debug(f"Found {len(conversations)} inactive conversations since {since}")
        return conversations
    
    # Базовые методы Repository
    
    async def get(self, id: ConversationId) -> Optional[Conversation]:
        """Alias для find_by_id (базовый метод Repository)."""
        return await self.find_by_id(id)
    
    async def add(self, entity: Conversation) -> None:
        """Alias для save (базовый метод Repository)."""
        await self.save(entity)
    
    async def update(self, entity: Conversation) -> None:
        """Alias для save (базовый метод Repository)."""
        await self.save(entity)
    
    async def remove(self, id: ConversationId) -> None:
        """Alias для delete (базовый метод Repository)."""
        await self.delete(id)
    
    async def list_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Conversation]:
        """Получить все conversations с пагинацией."""
        result = await self._db.execute(
            select(SessionModel)
            .where(SessionModel.deleted_at.is_(None))
            .order_by(SessionModel.last_activity.desc())
            .limit(limit if limit else 1000)
            .offset(offset if offset else 0)
        )
        models = result.scalars().all()
        
        conversations = []
        for model in models:
            conversation = await self._mapper.to_entity(model, self._db, load_messages=False)
            conversations.append(conversation)
        
        return conversations
    
    async def count(self) -> int:
        """Подсчитать общее количество conversations."""
        result = await self._db.execute(
            select(func.count(SessionModel.id)).where(
                SessionModel.deleted_at.is_(None)
            )
        )
        return result.scalar()

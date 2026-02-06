"""
Mapper для преобразования между Conversation Entity и SessionModel.

Изолирует доменный слой от деталей персистентности.
Использует новую Conversation entity вместо старой Session.
"""

import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....domain.session_context.entities import Conversation
from ....domain.session_context.value_objects import ConversationId, MessageCollection
from ....domain.entities.message import Message
from ..models import SessionModel, MessageModel

logger = logging.getLogger("agent-runtime.infrastructure.conversation_mapper")


class ConversationMapper:
    """
    Mapper между доменной сущностью Conversation и моделью БД SessionModel.
    
    Отвечает за преобразование данных между доменным слоем
    и слоем персистентности.
    
    Пример:
        >>> mapper = ConversationMapper()
        >>> # Entity -> Model
        >>> model = await mapper.to_model(conversation, db)
        >>> # Model -> Entity
        >>> entity = await mapper.to_entity(model, db)
    """
    
    async def to_entity(
        self,
        model: SessionModel,
        db: AsyncSession,
        load_messages: bool = True
    ) -> Conversation:
        """
        Преобразовать модель БД в доменную сущность Conversation.
        
        Args:
            model: Модель БД SessionModel
            db: Сессия БД для загрузки связанных данных
            load_messages: Загружать ли сообщения
            
        Returns:
            Доменная сущность Conversation
            
        Пример:
            >>> conversation = await mapper.to_entity(session_model, db)
        """
        # Загрузить сообщения если требуется
        messages: List[Message] = []
        if load_messages:
            result = await db.execute(
                select(MessageModel)
                .where(MessageModel.session_db_id == model.id)
                .order_by(MessageModel.timestamp.asc())
            )
            message_models = result.scalars().all()
            
            # Преобразовать модели сообщений в сущности
            for msg_model in message_models:
                # Парсинг tool_calls из JSON
                tool_calls = None
                if msg_model.tool_calls:
                    try:
                        tool_calls = json.loads(msg_model.tool_calls)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse tool_calls for message {msg_model.id}"
                        )
                
                # Парсинг metadata из JSON
                metadata = {}
                if msg_model.metadata_json:
                    try:
                        metadata = json.loads(msg_model.metadata_json)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse metadata for message {msg_model.id}"
                        )
                
                message = Message(
                    id=msg_model.id,
                    role=msg_model.role,
                    content=msg_model.content or "",
                    name=msg_model.name,
                    tool_call_id=msg_model.tool_call_id,
                    tool_calls=tool_calls,
                    metadata=metadata,
                    created_at=msg_model.timestamp
                )
                messages.append(message)
        
        # Создать ConversationId
        conversation_id = ConversationId(model.id)
        
        # Создать MessageCollection
        message_collection = MessageCollection(messages=messages)
        
        # Создать доменную сущность
        conversation = Conversation(
            id=model.id,
            conversation_id=conversation_id,
            messages=message_collection,
            title=model.title,
            description=model.description,
            last_activity=model.last_activity,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.last_activity,  # Используем last_activity как updated_at
            metadata={}
        )
        
        return conversation
    
    async def to_model(
        self,
        entity: Conversation,
        db: AsyncSession
    ) -> SessionModel:
        """
        Преобразовать доменную сущность Conversation в модель БД.
        
        Также сохраняет связанные сообщения.
        
        Args:
            entity: Доменная сущность Conversation
            db: Сессия БД
            
        Returns:
            Модель БД SessionModel
            
        Пример:
            >>> session_model = await mapper.to_model(conversation, db)
        """
        # Получить существующую модель или создать новую
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == entity.conversation_id.value,
                SessionModel.deleted_at.is_(None)
            )
        )
        model = result.scalar_one_or_none()
        
        if not model:
            # Создать новую модель
            model = SessionModel(
                id=entity.conversation_id.value,
                title=entity.title,
                description=entity.description,
                created_at=entity.created_at,
                last_activity=entity.last_activity,
                is_active=entity.is_active
            )
            db.add(model)
            await db.flush()  # Получить ID
            logger.debug(f"Created new SessionModel for {entity.conversation_id.value}")
        else:
            # Обновить существующую модель
            model.title = entity.title
            model.description = entity.description
            model.last_activity = entity.last_activity
            model.is_active = entity.is_active
            logger.debug(f"Updated SessionModel for {entity.conversation_id.value}")
        
        # Сохранить сообщения (атомарная замена)
        from sqlalchemy import delete
        await db.execute(
            delete(MessageModel).where(MessageModel.session_db_id == model.id)
        )
        
        # Добавить новые сообщения
        for message in entity.messages.messages:
            msg_model = MessageModel(
                id=message.id,
                session_db_id=model.id,
                role=message.role,
                content=message.content if message.content else None,
                timestamp=message.created_at,
                name=message.name,
                tool_call_id=message.tool_call_id,
                tool_calls=json.dumps(message.tool_calls) if message.tool_calls else None,
                metadata_json=json.dumps(message.metadata) if message.metadata else None
            )
            db.add(msg_model)
        
        return model

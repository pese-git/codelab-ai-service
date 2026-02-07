"""
Session Adapter - адаптер обратной совместимости.

Преобразует между старой моделью Session и новой моделью Conversation.
Обеспечивает плавную миграцию без breaking changes.
"""

from typing import Optional, List
from datetime import datetime

from ..session_context.entities.conversation import Conversation as Session
from ..entities.message import Message
from ..session_context.entities.conversation import Conversation
from ..session_context.value_objects import ConversationId, MessageCollection


class SessionAdapter:
    """
    Адаптер для преобразования Session ↔ Conversation.
    
    Обеспечивает обратную совместимость при миграции на новую архитектуру.
    Позволяет использовать новые repositories с существующим кодом.
    
    Методы:
        to_conversation: Session → Conversation
        from_conversation: Conversation → Session
        
    Пример:
        >>> session = Session(id="session-1")
        >>> conversation = SessionAdapter.to_conversation(session)
        >>> restored_session = SessionAdapter.from_conversation(conversation)
    """
    
    @staticmethod
    def to_conversation(session: Session) -> Conversation:
        """
        Преобразовать Session в Conversation.
        
        Args:
            session: Старая модель Session
            
        Returns:
            Новая модель Conversation
            
        Пример:
            >>> session = Session(id="session-1", title="Test")
            >>> conversation = SessionAdapter.to_conversation(session)
            >>> conversation.title
            'Test'
        """
        # Создать ConversationId из session.id
        conversation_id = ConversationId(value=session.id)
        
        # Создать MessageCollection из session.messages
        message_collection = MessageCollection(
            messages=session.messages.copy(),
            max_size=session.max_messages
        )
        
        # Создать Conversation с данными из Session
        conversation = Conversation(
            id=session.id,
            conversation_id=conversation_id,
            messages=message_collection,
            title=session.title,
            description=session.description,
            last_activity=session.last_activity,
            is_active=session.is_active,
            metadata=session.metadata.copy(),
            created_at=session.created_at,
            updated_at=session.updated_at
        )
        
        return conversation
    
    @staticmethod
    def from_conversation(conversation: Conversation) -> Session:
        """
        Преобразовать Conversation в Session.
        
        Args:
            conversation: Новая модель Conversation
            
        Returns:
            Старая модель Session
            
        Пример:
            >>> conv_id = ConversationId.generate()
            >>> conversation = Conversation.create(conv_id)
            >>> session = SessionAdapter.from_conversation(conversation)
            >>> session.id == conv_id.value
            True
        """
        # Извлечь messages из MessageCollection (используем прямой доступ к атрибуту)
        messages = conversation.messages.messages.copy()
        
        # Создать Session с данными из Conversation
        session = Session(
            id=conversation.conversation_id.value,
            messages=messages,
            title=conversation.title,
            description=conversation.description,
            last_activity=conversation.last_activity,
            is_active=conversation.is_active,
            max_messages=conversation.messages.max_size,
            metadata=conversation.metadata.copy(),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
        return session
    
    @staticmethod
    def to_conversation_list(sessions: List[Session]) -> List[Conversation]:
        """
        Преобразовать список Session в список Conversation.
        
        Args:
            sessions: Список старых моделей Session
            
        Returns:
            Список новых моделей Conversation
            
        Пример:
            >>> sessions = [Session(id="s1"), Session(id="s2")]
            >>> conversations = SessionAdapter.to_conversation_list(sessions)
            >>> len(conversations)
            2
        """
        return [SessionAdapter.to_conversation(session) for session in sessions]
    
    @staticmethod
    def from_conversation_list(conversations: List[Conversation]) -> List[Session]:
        """
        Преобразовать список Conversation в список Session.
        
        Args:
            conversations: Список новых моделей Conversation
            
        Returns:
            Список старых моделей Session
            
        Пример:
            >>> conv1 = Conversation.create(ConversationId.generate())
            >>> conv2 = Conversation.create(ConversationId.generate())
            >>> sessions = SessionAdapter.from_conversation_list([conv1, conv2])
            >>> len(sessions)
            2
        """
        return [SessionAdapter.from_conversation(conv) for conv in conversations]
    
    @staticmethod
    def sync_messages(session: Session, conversation: Conversation) -> None:
        """
        Синхронизировать сообщения между Session и Conversation.
        
        Полезно для обновления существующего объекта без создания нового.
        
        Args:
            session: Session для обновления
            conversation: Conversation с актуальными данными
            
        Пример:
            >>> session = Session(id="s1")
            >>> conversation = Conversation.create(ConversationId("s1"))
            >>> conversation.add_message(Message(id="m1", role="user", content="Hi"))
            >>> SessionAdapter.sync_messages(session, conversation)
            >>> len(session.messages)
            1
        """
        session.messages = conversation.messages.messages.copy()
        session.title = conversation.title
        session.description = conversation.description
        session.last_activity = conversation.last_activity
        session.is_active = conversation.is_active
        session.metadata = conversation.metadata.copy()
        session.updated_at = conversation.updated_at

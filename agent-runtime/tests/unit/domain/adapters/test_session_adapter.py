"""
Unit тесты для SessionAdapter.

Проверяет корректность преобразования между Session и Conversation.
"""

import pytest
from datetime import datetime, timezone

from app.domain.entities.session import Session
from app.domain.entities.message import Message
from app.domain.session_context.entities.conversation import Conversation
from app.domain.session_context.value_objects import ConversationId, MessageCollection
from app.domain.adapters import SessionAdapter


class TestSessionAdapter:
    """Тесты для SessionAdapter."""
    
    def test_to_conversation_basic(self):
        """Тест базового преобразования Session → Conversation."""
        # Arrange
        session = Session(
            id="session-123",
            title="Test Session",
            description="Test Description",
            is_active=True
        )
        
        # Act
        conversation = SessionAdapter.to_conversation(session)
        
        # Assert
        assert conversation.conversation_id.value == "session-123"
        assert conversation.title == "Test Session"
        assert conversation.description == "Test Description"
        assert conversation.is_active is True
        assert isinstance(conversation.messages, MessageCollection)
    
    def test_to_conversation_with_messages(self):
        """Тест преобразования Session с сообщениями."""
        # Arrange
        session = Session(id="session-123")
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi there")
        session.add_message(msg1)
        session.add_message(msg2)
        
        # Act
        conversation = SessionAdapter.to_conversation(session)
        
        # Assert
        assert conversation.messages.count() == 2
        # Используем прямой доступ к messages атрибуту
        messages = conversation.messages.messages
        assert messages[0].id == "msg-1"
        assert messages[1].id == "msg-2"
    
    def test_from_conversation_basic(self):
        """Тест базового преобразования Conversation → Session."""
        # Arrange
        conv_id = ConversationId(value="conv-456")
        conversation = Conversation.create(
            conversation_id=conv_id,
            title="Test Conversation",
            description="Test Description"
        )
        
        # Act
        session = SessionAdapter.from_conversation(conversation)
        
        # Assert
        assert session.id == "conv-456"
        assert session.title == "Test Conversation"
        assert session.description == "Test Description"
        assert session.is_active is True
        assert isinstance(session.messages, list)
    
    def test_from_conversation_with_messages(self):
        """Тест преобразования Conversation с сообщениями."""
        # Arrange
        conv_id = ConversationId(value="conv-456")
        conversation = Conversation.create(conv_id)
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi")
        conversation.add_message(msg1)
        conversation.add_message(msg2)
        
        # Act
        session = SessionAdapter.from_conversation(conversation)
        
        # Assert
        assert len(session.messages) == 2
        assert session.messages[0].id == "msg-1"
        assert session.messages[1].id == "msg-2"
    
    def test_round_trip_conversion(self):
        """Тест двустороннего преобразования Session → Conversation → Session."""
        # Arrange
        original_session = Session(
            id="session-789",
            title="Round Trip Test",
            description="Testing round trip",
            is_active=True
        )
        msg = Message(id="msg-1", role="user", content="Test message")
        original_session.add_message(msg)
        
        # Act
        conversation = SessionAdapter.to_conversation(original_session)
        restored_session = SessionAdapter.from_conversation(conversation)
        
        # Assert
        assert restored_session.id == original_session.id
        assert restored_session.title == original_session.title
        assert restored_session.description == original_session.description
        assert restored_session.is_active == original_session.is_active
        assert len(restored_session.messages) == len(original_session.messages)
        assert restored_session.messages[0].id == original_session.messages[0].id
    
    def test_to_conversation_list(self):
        """Тест преобразования списка Session."""
        # Arrange
        sessions = [
            Session(id="s1", title="Session 1"),
            Session(id="s2", title="Session 2"),
            Session(id="s3", title="Session 3")
        ]
        
        # Act
        conversations = SessionAdapter.to_conversation_list(sessions)
        
        # Assert
        assert len(conversations) == 3
        assert conversations[0].conversation_id.value == "s1"
        assert conversations[1].conversation_id.value == "s2"
        assert conversations[2].conversation_id.value == "s3"
    
    def test_from_conversation_list(self):
        """Тест преобразования списка Conversation."""
        # Arrange
        conversations = [
            Conversation.create(ConversationId("c1"), title="Conv 1"),
            Conversation.create(ConversationId("c2"), title="Conv 2"),
            Conversation.create(ConversationId("c3"), title="Conv 3")
        ]
        
        # Act
        sessions = SessionAdapter.from_conversation_list(conversations)
        
        # Assert
        assert len(sessions) == 3
        assert sessions[0].id == "c1"
        assert sessions[1].id == "c2"
        assert sessions[2].id == "c3"
    
    def test_sync_messages(self):
        """Тест синхронизации сообщений между Session и Conversation."""
        # Arrange
        session = Session(id="s1", title="Old Title")
        conversation = Conversation.create(
            ConversationId("s1"),
            title="New Title"
        )
        msg = Message(id="msg-1", role="user", content="New message")
        conversation.add_message(msg)
        
        # Act
        SessionAdapter.sync_messages(session, conversation)
        
        # Assert
        assert session.title == "New Title"
        assert len(session.messages) == 1
        assert session.messages[0].id == "msg-1"
        # Проверяем, что сообщения синхронизированы из MessageCollection
        assert session.messages[0].content == "New message"
    
    def test_preserves_metadata(self):
        """Тест сохранения метаданных при преобразовании."""
        # Arrange
        session = Session(
            id="s1",
            metadata={"key1": "value1", "key2": 123}
        )
        
        # Act
        conversation = SessionAdapter.to_conversation(session)
        restored_session = SessionAdapter.from_conversation(conversation)
        
        # Assert
        assert conversation.metadata == session.metadata
        assert restored_session.metadata == session.metadata
    
    def test_preserves_timestamps(self):
        """Тест сохранения временных меток."""
        # Arrange
        now = datetime.now(timezone.utc)
        session = Session(
            id="s1",
            created_at=now,
            updated_at=now,
            last_activity=now
        )
        
        # Act
        conversation = SessionAdapter.to_conversation(session)
        
        # Assert
        assert conversation.created_at == session.created_at
        assert conversation.updated_at == session.updated_at
        assert conversation.last_activity == session.last_activity
    
    def test_handles_inactive_session(self):
        """Тест обработки неактивной сессии."""
        # Arrange
        session = Session(id="s1", is_active=False)
        
        # Act
        conversation = SessionAdapter.to_conversation(session)
        restored_session = SessionAdapter.from_conversation(conversation)
        
        # Assert
        assert conversation.is_active is False
        assert restored_session.is_active is False
    
    def test_handles_max_messages_limit(self):
        """Тест сохранения лимита сообщений."""
        # Arrange
        session = Session(id="s1", max_messages=500)
        
        # Act
        conversation = SessionAdapter.to_conversation(session)
        restored_session = SessionAdapter.from_conversation(conversation)
        
        # Assert
        assert conversation.messages.max_size == 500
        assert restored_session.max_messages == 500

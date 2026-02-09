"""
Unit tests для Conversation Entity.
"""

import pytest
from app.domain.session_context import (
    Conversation,
    ConversationId,
    ConversationStarted,
    MessageAdded,
    ConversationDeactivated,
    MessagesCleared,
)
from app.domain.entities.message import Message


class TestConversation:
    """Тесты для Conversation entity"""
    
    def test_create_conversation(self):
        """Создание conversation"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id, title="Test")
        
        assert conversation.conversation_id == conv_id
        assert conversation.title == "Test"
        assert conversation.is_active
        assert conversation.is_empty()
    
    def test_create_generates_event(self):
        """Создание генерирует ConversationStarted event"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        
        events = conversation.get_domain_events()
        
        assert len(events) == 1
        assert isinstance(events[0], ConversationStarted)
        assert events[0].conversation_id == conv_id.value
    
    def test_add_message(self):
        """Добавление сообщения"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        
        msg = Message(id="msg-1", role="user", content="Hello")
        conversation.add_message(msg)
        
        assert conversation.get_message_count() == 1
        assert not conversation.is_empty()
    
    def test_add_message_generates_event(self):
        """Добавление сообщения генерирует MessageAdded event"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        conversation.clear_domain_events()  # Очистить ConversationStarted
        
        msg = Message(id="msg-1", role="user", content="Hello")
        conversation.add_message(msg)
        
        events = conversation.get_domain_events()
        
        assert len(events) == 1
        assert isinstance(events[0], MessageAdded)
        assert events[0].message_id == "msg-1"
        assert events[0].role == "user"
    
    def test_add_message_sets_title_from_first_user_message(self):
        """Первое user сообщение устанавливает title"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        
        msg = Message(id="msg-1", role="user", content="Hello World")
        conversation.add_message(msg)
        
        assert conversation.title == "Hello World"
    
    def test_add_message_to_inactive_raises_error(self):
        """Добавление в неактивный conversation вызывает ошибку"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        conversation.deactivate()
        
        msg = Message(id="msg-1", role="user", content="Hello")
        
        with pytest.raises(ValueError, match="неактивный conversation"):
            conversation.add_message(msg)
    
    def test_deactivate(self):
        """Деактивация conversation"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        
        conversation.deactivate(reason="Test reason")
        
        assert not conversation.is_active
        assert conversation.metadata["deactivation_reason"] == "Test reason"
    
    def test_deactivate_generates_event(self):
        """Деактивация генерирует ConversationDeactivated event"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        conversation.clear_domain_events()
        
        conversation.deactivate(reason="Test")
        
        events = conversation.get_domain_events()
        
        assert len(events) == 1
        assert isinstance(events[0], ConversationDeactivated)
        assert events[0].reason == "Test"
    
    def test_activate(self):
        """Активация conversation"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        conversation.deactivate()
        
        conversation.activate()
        
        assert conversation.is_active
    
    def test_clear_messages(self):
        """Очистка сообщений"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        
        msg = Message(id="msg-1", role="user", content="Hello")
        conversation.add_message(msg)
        
        removed = conversation.clear_messages()
        
        assert removed == 1
        assert conversation.is_empty()
    
    def test_clear_messages_generates_event(self):
        """Очистка генерирует MessagesCleared event"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        
        msg = Message(id="msg-1", role="user", content="Hello")
        conversation.add_message(msg)
        conversation.clear_domain_events()
        
        conversation.clear_messages()
        
        events = conversation.get_domain_events()
        
        assert len(events) == 1
        assert isinstance(events[0], MessagesCleared)
        assert events[0].cleared_count == 1
    
    def test_get_duration_seconds(self):
        """Получение длительности"""
        conv_id = ConversationId.generate()
        conversation = Conversation.create(conv_id)
        
        duration = conversation.get_duration_seconds()
        
        assert duration >= 0
    
    def test_repr(self):
        """Строковое представление"""
        conv_id = ConversationId(value="conv-123")
        conversation = Conversation.create(conv_id, title="Test Conversation")
        
        repr_str = repr(conversation)
        
        assert "conv-123" in repr_str
        assert "Test Conversation" in repr_str

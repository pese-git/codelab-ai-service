"""
Unit tests для MessageCollection Value Object.
"""

import pytest
from app.domain.session_context.value_objects import MessageCollection
from app.domain.entities.message import Message


class TestMessageCollection:
    """Тесты для MessageCollection"""
    
    def test_create_empty_collection(self):
        """Создание пустой коллекции"""
        collection = MessageCollection.empty()
        assert collection.count() == 0
        assert collection.is_empty()
    
    def test_add_message(self):
        """Добавление сообщения"""
        collection = MessageCollection.empty()
        msg = Message(id="msg-1", role="user", content="Hello")
        
        new_collection = collection.add(msg)
        
        assert new_collection.count() == 1
        assert not new_collection.is_empty()
        assert collection.count() == 0  # Оригинал не изменился (immutable)
    
    def test_add_multiple_messages(self):
        """Добавление нескольких сообщений"""
        collection = MessageCollection.empty()
        
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi")
        
        collection = collection.add(msg1).add(msg2)
        
        assert collection.count() == 2
    
    def test_add_exceeds_limit_raises_error(self):
        """Превышение лимита вызывает ошибку"""
        collection = MessageCollection.empty(max_size=2)
        
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi")
        msg3 = Message(id="msg-3", role="user", content="Test")
        
        collection = collection.add(msg1).add(msg2)
        
        with pytest.raises(ValueError, match="достигнут лимит"):
            collection.add(msg3)
    
    def test_is_full(self):
        """Проверка заполненности"""
        collection = MessageCollection.empty(max_size=1)
        assert not collection.is_full()
        
        msg = Message(id="msg-1", role="user", content="Hello")
        collection = collection.add(msg)
        
        assert collection.is_full()
    
    def test_get_recent_messages(self):
        """Получение последних сообщений"""
        collection = MessageCollection.empty()
        
        for i in range(5):
            msg = Message(id=f"msg-{i}", role="user", content=f"Message {i}")
            collection = collection.add(msg)
        
        recent = collection.get_recent(3)
        
        assert len(recent) == 3
        assert recent[0].id == "msg-2"
        assert recent[2].id == "msg-4"
    
    def test_filter_by_role(self):
        """Фильтрация по роли"""
        collection = MessageCollection.empty()
        
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi")
        msg3 = Message(id="msg-3", role="user", content="Test")
        
        collection = collection.add(msg1).add(msg2).add(msg3)
        
        user_messages = collection.filter_by_role("user")
        
        assert len(user_messages) == 2
        assert all(msg.role == "user" for msg in user_messages)
    
    def test_clear_tool_messages(self):
        """Очистка tool messages"""
        collection = MessageCollection.empty()
        
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="", tool_calls=[{"id": "call-1"}])
        msg3 = Message(id="msg-3", role="tool", content="Result", tool_call_id="call-1")
        msg4 = Message(id="msg-4", role="assistant", content="Done")
        
        for msg in [msg1, msg2, msg3, msg4]:
            collection = collection.add(msg)
        
        new_collection, removed = collection.clear_tool_messages()
        
        assert removed == 2  # msg2 и msg3
        assert new_collection.count() == 2  # msg1 и msg4
    
    def test_get_last_assistant_message(self):
        """Получение последнего assistant message"""
        collection = MessageCollection.empty()
        
        msg1 = Message(id="msg-1", role="assistant", content="First")
        msg2 = Message(id="msg-2", role="assistant", content="", tool_calls=[{"id": "call-1"}])
        msg3 = Message(id="msg-3", role="assistant", content="Last")
        
        for msg in [msg1, msg2, msg3]:
            collection = collection.add(msg)
        
        last = collection.get_last_assistant_message()
        
        assert last is not None
        assert last.id == "msg-3"
        assert last.content == "Last"
    
    def test_to_llm_format(self):
        """Конвертация в LLM формат"""
        collection = MessageCollection.empty()
        
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi")
        
        collection = collection.add(msg1).add(msg2)
        
        llm_format = collection.to_llm_format()
        
        assert len(llm_format) == 2
        assert llm_format[0]["role"] == "user"
        assert llm_format[0]["content"] == "Hello"
    
    def test_to_llm_format_with_limit(self):
        """Конвертация в LLM формат с лимитом"""
        collection = MessageCollection.empty()
        
        for i in range(5):
            msg = Message(id=f"msg-{i}", role="user", content=f"Message {i}")
            collection = collection.add(msg)
        
        llm_format = collection.to_llm_format(max_messages=3)
        
        assert len(llm_format) == 3
    
    def test_clear(self):
        """Очистка коллекции"""
        collection = MessageCollection.empty()
        
        msg = Message(id="msg-1", role="user", content="Hello")
        collection = collection.add(msg)
        
        cleared = collection.clear()
        
        assert cleared.count() == 0
        assert cleared.is_empty()
        assert collection.count() == 1  # Оригинал не изменился
    
    def test_iteration(self):
        """Итерация по коллекции"""
        collection = MessageCollection.empty()
        
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi")
        
        collection = collection.add(msg1).add(msg2)
        
        messages = list(collection)
        
        assert len(messages) == 2
        assert messages[0].id == "msg-1"
    
    def test_indexing(self):
        """Индексация коллекции"""
        collection = MessageCollection.empty()
        
        msg1 = Message(id="msg-1", role="user", content="Hello")
        msg2 = Message(id="msg-2", role="assistant", content="Hi")
        
        collection = collection.add(msg1).add(msg2)
        
        assert collection[0].id == "msg-1"
        assert collection[1].id == "msg-2"
    
    def test_len(self):
        """Поддержка len()"""
        collection = MessageCollection.empty()
        
        msg = Message(id="msg-1", role="user", content="Hello")
        collection = collection.add(msg)
        
        assert len(collection) == 1

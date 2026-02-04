"""
Unit tests для ConversationId Value Object.
"""

import pytest
from app.domain.session_context.value_objects import ConversationId


class TestConversationId:
    """Тесты для ConversationId"""
    
    def test_create_valid_id(self):
        """Создание валидного ID"""
        conv_id = ConversationId("conv-123")
        assert conv_id.value == "conv-123"
    
    def test_create_with_alphanumeric(self):
        """ID с alphanumeric символами"""
        conv_id = ConversationId("conv_123-abc")
        assert conv_id.value == "conv_123-abc"
    
    def test_generate_creates_valid_id(self):
        """Генерация создает валидный ID"""
        conv_id = ConversationId.generate()
        assert len(conv_id.value) > 0
        assert len(conv_id.value) <= 255
    
    def test_generate_creates_unique_ids(self):
        """Генерация создает уникальные ID"""
        id1 = ConversationId.generate()
        id2 = ConversationId.generate()
        assert id1.value != id2.value
    
    def test_empty_id_raises_error(self):
        """Пустой ID вызывает ошибку"""
        with pytest.raises(ValueError, match="не может быть пустым"):
            ConversationId("")
    
    def test_too_long_id_raises_error(self):
        """Слишком длинный ID вызывает ошибку"""
        long_id = "a" * 256
        with pytest.raises(ValueError, match="не может превышать 255 символов"):
            ConversationId(long_id)
    
    def test_invalid_characters_raise_error(self):
        """Недопустимые символы вызывают ошибку"""
        with pytest.raises(ValueError, match="может содержать только"):
            ConversationId("conv@123")
    
    def test_equality(self):
        """Проверка равенства"""
        id1 = ConversationId("conv-123")
        id2 = ConversationId("conv-123")
        assert id1 == id2
    
    def test_inequality(self):
        """Проверка неравенства"""
        id1 = ConversationId("conv-123")
        id2 = ConversationId("conv-456")
        assert id1 != id2
    
    def test_hash_consistency(self):
        """Hash консистентен для одинаковых ID"""
        id1 = ConversationId("conv-123")
        id2 = ConversationId("conv-123")
        assert hash(id1) == hash(id2)
    
    def test_can_use_in_set(self):
        """Можно использовать в set"""
        id1 = ConversationId("conv-123")
        id2 = ConversationId("conv-123")
        id3 = ConversationId("conv-456")
        
        id_set = {id1, id2, id3}
        assert len(id_set) == 2  # id1 и id2 одинаковые
    
    def test_repr(self):
        """Строковое представление"""
        conv_id = ConversationId("conv-123")
        assert "conv-123" in repr(conv_id)

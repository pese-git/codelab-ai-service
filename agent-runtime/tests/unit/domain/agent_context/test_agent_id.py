"""
Unit тесты для AgentId Value Object.
"""

import pytest
from app.domain.agent_context.value_objects.agent_id import AgentId


class TestAgentIdCreation:
    """Тесты создания AgentId."""
    
    def test_create_with_valid_id(self):
        """Тест создания AgentId с валидным ID."""
        agent_id = AgentId(value="agent-123")
        assert agent_id.value == "agent-123"
    
    def test_create_with_empty_string_raises_error(self):
        """Тест что пустая строка вызывает ошибку."""
        with pytest.raises(ValueError, match="Agent ID не может быть пустым"):
            AgentId(value="")
    
    def test_create_with_none_raises_error(self):
        """Тест что None вызывает ошибку."""
        with pytest.raises(ValueError, match="Agent ID не может быть пустым"):
            AgentId(None)
    
    def test_create_with_non_string_raises_error(self):
        """Тест что не-строка вызывает ошибку."""
        with pytest.raises(ValueError, match="Agent ID должен быть строкой"):
            AgentId(123)
    
    def test_create_with_too_long_id_raises_error(self):
        """Тест что слишком длинный ID вызывает ошибку."""
        long_id = "a" * 256
        with pytest.raises(ValueError, match="Agent ID слишком длинный"):
            AgentId(long_id)
    
    def test_create_with_whitespace_only_raises_error(self):
        """Тест что ID из пробелов вызывает ошибку."""
        with pytest.raises(ValueError, match="Agent ID не может состоять только из пробелов"):
            AgentId(value="   ")
    
    def test_create_with_invalid_characters_raises_error(self):
        """Тест что недопустимые символы вызывают ошибку."""
        with pytest.raises(ValueError, match="Agent ID содержит недопустимые символы"):
            AgentId(value="agent\n123")
    
    def test_create_strips_whitespace(self):
        """Тест что пробелы обрезаются."""
        agent_id = AgentId(value="  agent-123  ")
        assert agent_id.value == "agent-123"


class TestAgentIdGeneration:
    """Тесты генерации AgentId."""
    
    def test_generate_creates_valid_id(self):
        """Тест что generate создает валидный ID."""
        agent_id = AgentId.generate()
        assert agent_id.value.startswith("agent-")
        assert len(agent_id.value) > 10
    
    def test_generate_with_custom_prefix(self):
        """Тест генерации с кастомным префиксом."""
        agent_id = AgentId.generate(prefix="ctx")
        assert agent_id.value.startswith("ctx-")
    
    def test_generate_creates_unique_ids(self):
        """Тест что generate создает уникальные ID."""
        id1 = AgentId.generate()
        id2 = AgentId.generate()
        assert id1.value != id2.value
    
    def test_from_session_id_creates_valid_id(self):
        """Тест создания AgentId из session ID."""
        agent_id = AgentId.from_session_id("session-123")
        assert agent_id.value == "agent-123"
    
    def test_from_session_id_removes_session_prefix(self):
        """Тест что префикс session- удаляется."""
        agent_id = AgentId.from_session_id("session-abc-def")
        assert agent_id.value == "agent-abc-def"
    
    def test_from_session_id_with_empty_raises_error(self):
        """Тест что пустой session ID вызывает ошибку."""
        with pytest.raises(ValueError, match="Session ID не может быть пустым"):
            AgentId.from_session_id("")


class TestAgentIdEquality:
    """Тесты сравнения AgentId."""
    
    def test_equal_ids_are_equal(self):
        """Тест что одинаковые ID равны."""
        id1 = AgentId(value="agent-123")
        id2 = AgentId(value="agent-123")
        assert id1 == id2
    
    def test_different_ids_are_not_equal(self):
        """Тест что разные ID не равны."""
        id1 = AgentId(value="agent-123")
        id2 = AgentId(value="agent-456")
        assert id1 != id2
    
    def test_not_equal_to_non_agent_id(self):
        """Тест что AgentId не равен не-AgentId."""
        agent_id = AgentId(value="agent-123")
        assert agent_id != "agent-123"
        assert agent_id != 123
        assert agent_id != None


class TestAgentIdHashing:
    """Тесты хеширования AgentId."""
    
    def test_can_be_used_in_set(self):
        """Тест что AgentId можно использовать в множестве."""
        id1 = AgentId(value="agent-123")
        id2 = AgentId(value="agent-456")
        id3 = AgentId(value="agent-123")
        
        id_set = {id1, id2, id3}
        assert len(id_set) == 2
    
    def test_can_be_used_as_dict_key(self):
        """Тест что AgentId можно использовать как ключ словаря."""
        id1 = AgentId(value="agent-123")
        id2 = AgentId(value="agent-456")
        
        id_dict = {id1: "value1", id2: "value2"}
        assert id_dict[id1] == "value1"
        assert id_dict[id2] == "value2"
    
    def test_equal_ids_have_same_hash(self):
        """Тест что равные ID имеют одинаковый хеш."""
        id1 = AgentId(value="agent-123")
        id2 = AgentId(value="agent-123")
        assert hash(id1) == hash(id2)


class TestAgentIdComparison:
    """Тесты сравнения AgentId."""
    
    def test_less_than_comparison(self):
        """Тест сравнения меньше."""
        id1 = AgentId(value="agent-aaa")
        id2 = AgentId(value="agent-bbb")
        assert id1 < id2
    
    def test_sorting(self):
        """Тест сортировки AgentId."""
        id1 = AgentId(value="agent-ccc")
        id2 = AgentId(value="agent-aaa")
        id3 = AgentId(value="agent-bbb")
        
        sorted_ids = sorted([id1, id2, id3])
        assert sorted_ids[0].value == "agent-aaa"
        assert sorted_ids[1].value == "agent-bbb"
        assert sorted_ids[2].value == "agent-ccc"


class TestAgentIdStringRepresentation:
    """Тесты строкового представления AgentId."""
    
    def test_str_returns_value(self):
        """Тест что str() возвращает значение."""
        agent_id = AgentId(value="agent-123")
        assert str(agent_id) == "agent-123"
    
    def test_repr_shows_class_and_value(self):
        """Тест что repr() показывает класс и значение."""
        agent_id = AgentId(value="agent-123")
        assert repr(agent_id) == "AgentId(value='agent-123')"

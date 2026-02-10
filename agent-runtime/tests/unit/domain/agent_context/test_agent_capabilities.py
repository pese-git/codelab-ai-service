"""
Unit тесты для AgentCapabilities Value Object.
"""

import pytest
from app.domain.agent_context.value_objects.agent_capabilities import (
    AgentCapabilities,
    AgentType
)


class TestAgentCapabilitiesCreation:
    """Тесты создания AgentCapabilities."""
    
    def test_create_with_valid_parameters(self):
        """Тест создания с валидными параметрами."""
        caps = AgentCapabilities(
            agent_type=AgentType.CODER,
            supported_tools={"write_file", "read_file"},
            max_switches=50
        )
        assert caps.agent_type == AgentType.CODER
        assert "write_file" in caps.supported_tools
        assert caps.max_switches == 50
    
    def test_create_with_invalid_agent_type_raises_error(self):
        """Тест что невалидный тип агента вызывает ошибку."""
        with pytest.raises(ValueError, match="Невалидный тип агента"):
            AgentCapabilities(
                agent_type="invalid",
                supported_tools=set()
            )
    
    def test_create_with_negative_max_switches_raises_error(self):
        """Тест что отрицательный max_switches вызывает ошибку."""
        with pytest.raises(ValueError, match="max_switches должен быть >= 1"):
            AgentCapabilities(
                agent_type=AgentType.CODER,
                max_switches=0
            )
    
    def test_create_with_too_large_max_switches_raises_error(self):
        """Тест что слишком большой max_switches вызывает ошибку."""
        with pytest.raises(ValueError, match="max_switches слишком большой"):
            AgentCapabilities(
                agent_type=AgentType.CODER,
                max_switches=1001
            )
    
    def test_create_with_default_values(self):
        """Тест создания с значениями по умолчанию."""
        caps = AgentCapabilities(agent_type=AgentType.CODER)
        assert caps.max_switches == 50
        assert caps.can_delegate == False
        assert caps.requires_approval == False


class TestAgentCapabilitiesFactoryMethods:
    """Тесты фабричных методов AgentCapabilities."""
    
    def test_for_orchestrator(self):
        """Тест создания capabilities для Orchestrator."""
        caps = AgentCapabilities.for_orchestrator()
        assert caps.agent_type == AgentType.ORCHESTRATOR
        assert caps.can_delegate == True
        assert "create_plan" in caps.supported_tools
    
    def test_for_coder(self):
        """Тест создания capabilities для Coder."""
        caps = AgentCapabilities.for_coder()
        assert caps.agent_type == AgentType.CODER
        assert caps.requires_approval == True
        assert "write_file" in caps.supported_tools
        assert "read_file" in caps.supported_tools
    
    def test_for_architect(self):
        """Тест создания capabilities для Architect."""
        caps = AgentCapabilities.for_architect()
        assert caps.agent_type == AgentType.ARCHITECT
        assert "create_diagram" in caps.supported_tools
    
    def test_for_debug(self):
        """Тест создания capabilities для Debug."""
        caps = AgentCapabilities.for_debug()
        assert caps.agent_type == AgentType.DEBUG
        assert "analyze_logs" in caps.supported_tools
    
    def test_for_ask(self):
        """Тест создания capabilities для Ask."""
        caps = AgentCapabilities.for_ask()
        assert caps.agent_type == AgentType.ASK
        assert caps.requires_approval == False
    
    def test_for_universal(self):
        """Тест создания capabilities для Universal."""
        caps = AgentCapabilities.for_universal()
        assert caps.agent_type == AgentType.UNIVERSAL
        assert caps.can_delegate == True
        assert caps.max_switches == 100
    
    def test_for_agent_type_orchestrator(self):
        """Тест for_agent_type для Orchestrator."""
        caps = AgentCapabilities.for_agent_type(AgentType.ORCHESTRATOR)
        assert caps.agent_type == AgentType.ORCHESTRATOR
    
    def test_for_agent_type_coder(self):
        """Тест for_agent_type для Coder."""
        caps = AgentCapabilities.for_agent_type(AgentType.CODER)
        assert caps.agent_type == AgentType.CODER


class TestAgentCapabilitiesToolSupport:
    """Тесты поддержки инструментов."""
    
    def test_supports_tool_returns_true_for_supported(self):
        """Тест что supports_tool возвращает True для поддерживаемого инструмента."""
        caps = AgentCapabilities.for_coder()
        assert caps.supports_tool("write_file") == True
    
    def test_supports_tool_returns_false_for_unsupported(self):
        """Тест что supports_tool возвращает False для неподдерживаемого инструмента."""
        caps = AgentCapabilities.for_coder()
        assert caps.supports_tool("unknown_tool") == False
    
    def test_get_tool_list_returns_sorted_list(self):
        """Тест что get_tool_list возвращает отсортированный список."""
        caps = AgentCapabilities(
            agent_type=AgentType.CODER,
            supported_tools={"write_file", "read_file", "apply_diff"}
        )
        tools = caps.get_tool_list()
        assert tools == sorted(tools)
        assert "write_file" in tools
    
    def test_supported_tools_is_immutable(self):
        """Тест что supported_tools неизменяем."""
        caps = AgentCapabilities.for_coder()
        tools = caps.supported_tools
        assert isinstance(tools, frozenset)


class TestAgentCapabilitiesEquality:
    """Тесты сравнения AgentCapabilities."""
    
    def test_equal_capabilities_are_equal(self):
        """Тест что одинаковые capabilities равны."""
        caps1 = AgentCapabilities.for_coder()
        caps2 = AgentCapabilities.for_coder()
        assert caps1 == caps2
    
    def test_different_capabilities_are_not_equal(self):
        """Тест что разные capabilities не равны."""
        caps1 = AgentCapabilities.for_coder()
        caps2 = AgentCapabilities.for_architect()
        assert caps1 != caps2
    
    def test_not_equal_to_non_capabilities(self):
        """Тест что AgentCapabilities не равен не-AgentCapabilities."""
        caps = AgentCapabilities.for_coder()
        assert caps != "coder"
        assert caps != 123
        assert caps != None


class TestAgentCapabilitiesHashing:
    """Тесты хеширования AgentCapabilities."""
    
    def test_can_be_used_in_set(self):
        """Тест что AgentCapabilities можно использовать в множестве."""
        caps1 = AgentCapabilities.for_coder()
        caps2 = AgentCapabilities.for_architect()
        caps3 = AgentCapabilities.for_coder()
        
        caps_set = {caps1, caps2, caps3}
        assert len(caps_set) == 2
    
    def test_can_be_used_as_dict_key(self):
        """Тест что AgentCapabilities можно использовать как ключ словаря."""
        caps1 = AgentCapabilities.for_coder()
        caps2 = AgentCapabilities.for_architect()
        
        caps_dict = {caps1: "value1", caps2: "value2"}
        assert caps_dict[caps1] == "value1"
        assert caps_dict[caps2] == "value2"
    
    def test_equal_capabilities_have_same_hash(self):
        """Тест что равные capabilities имеют одинаковый хеш."""
        caps1 = AgentCapabilities.for_coder()
        caps2 = AgentCapabilities.for_coder()
        assert hash(caps1) == hash(caps2)


class TestAgentCapabilitiesStringRepresentation:
    """Тесты строкового представления AgentCapabilities."""
    
    def test_str_shows_type_and_tool_count(self):
        """Тест что str() показывает тип и количество инструментов."""
        caps = AgentCapabilities.for_coder()
        str_repr = str(caps)
        assert "coder" in str_repr
        assert "tools" in str_repr
    
    def test_repr_shows_details(self):
        """Тест что repr() показывает детали."""
        caps = AgentCapabilities.for_coder()
        repr_str = repr(caps)
        assert "AgentCapabilities" in repr_str
        assert "coder" in repr_str
        assert "max_switches" in repr_str


class TestAgentType:
    """Тесты AgentType enum."""
    
    def test_all_agent_types_exist(self):
        """Тест что все типы агентов существуют."""
        assert AgentType.ORCHESTRATOR.value == "orchestrator"
        assert AgentType.CODER.value == "coder"
        assert AgentType.ARCHITECT.value == "architect"
        assert AgentType.DEBUG.value == "debug"
        assert AgentType.ASK.value == "ask"
        assert AgentType.UNIVERSAL.value == "universal"
    
    def test_agent_type_is_string_enum(self):
        """Тест что AgentType является строковым enum."""
        assert isinstance(AgentType.CODER.value, str)
    
    def test_can_compare_agent_types(self):
        """Тест что можно сравнивать типы агентов."""
        assert AgentType.CODER == AgentType.CODER
        assert AgentType.CODER != AgentType.ARCHITECT

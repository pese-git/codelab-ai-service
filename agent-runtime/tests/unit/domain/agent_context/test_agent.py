"""
Unit тесты для Agent Entity.
"""

import pytest
from datetime import datetime, timezone
from app.domain.agent_context.entities.agent import Agent, AgentSwitchRecord
from app.domain.agent_context.value_objects.agent_id import AgentId
from app.domain.agent_context.value_objects.agent_capabilities import (
    AgentCapabilities,
    AgentType
)


class TestAgentCreation:
    """Тесты создания Agent."""
    
    def test_create_agent_with_factory_method(self):
        """Тест создания агента через фабричный метод."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        assert agent.session_id == "session-123"
        assert agent.current_type == AgentType.ORCHESTRATOR
        assert agent.switch_count == 0
    
    def test_create_agent_with_custom_id(self):
        """Тест создания агента с кастомным ID."""
        agent_id = AgentId("agent-custom")
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder(),
            agent_id=agent_id
        )
        assert agent.id == "agent-custom"
    
    def test_create_agent_generates_id_from_session(self):
        """Тест что ID генерируется из session ID."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        assert "agent-" in agent.id
    
    def test_create_with_empty_session_id_raises_error(self):
        """Тест что пустой session_id вызывает ошибку."""
        with pytest.raises(ValueError, match="session_id не может быть пустым"):
            Agent(
                id="agent-123",
                session_id="",
                capabilities=AgentCapabilities.for_coder()
            )
    
    def test_create_with_invalid_capabilities_raises_error(self):
        """Тест что невалидные capabilities вызывают ошибку."""
        with pytest.raises(ValueError, match="capabilities должен быть AgentCapabilities"):
            Agent(
                id="agent-123",
                session_id="session-123",
                capabilities="invalid"
            )


class TestAgentSwitching:
    """Тесты переключения агента."""
    
    def test_can_switch_to_different_type(self):
        """Тест что можно переключиться на другой тип."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        assert agent.can_switch_to(AgentType.CODER) == True
    
    def test_cannot_switch_to_same_type(self):
        """Тест что нельзя переключиться на тот же тип."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        assert agent.can_switch_to(AgentType.CODER) == False
    
    def test_switch_to_updates_type(self):
        """Тест что switch_to обновляет тип агента."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent.switch_to(AgentType.CODER, "Need to write code")
        assert agent.current_type == AgentType.CODER
    
    def test_switch_to_increments_count(self):
        """Тест что switch_to увеличивает счетчик."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        initial_count = agent.switch_count
        agent.switch_to(AgentType.CODER, "Need to write code")
        assert agent.switch_count == initial_count + 1
    
    def test_switch_to_creates_record(self):
        """Тест что switch_to создает запись о переключении."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        record = agent.switch_to(AgentType.CODER, "Need to write code")
        assert isinstance(record, AgentSwitchRecord)
        assert record.from_agent == AgentType.ORCHESTRATOR
        assert record.to_agent == AgentType.CODER
    
    def test_switch_to_adds_to_history(self):
        """Тест что switch_to добавляет в историю."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent.switch_to(AgentType.CODER, "Need to write code")
        history = agent.switch_history
        assert len(history) == 1
    
    def test_switch_to_same_type_raises_error(self):
        """Тест что переключение на тот же тип вызывает ошибку."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        with pytest.raises(ValueError, match="Агент уже имеет тип"):
            agent.switch_to(AgentType.CODER, "Try to switch")
    
    def test_switch_updates_last_switch_at(self):
        """Тест что переключение обновляет last_switch_at."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        assert agent.last_switch_at is None
        agent.switch_to(AgentType.CODER, "Need to write code")
        assert agent.last_switch_at is not None
        assert isinstance(agent.last_switch_at, datetime)


class TestAgentSwitchHistory:
    """Тесты истории переключений."""
    
    def test_get_last_switch_returns_none_initially(self):
        """Тест что get_last_switch возвращает None изначально."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        assert agent.get_last_switch() is None
    
    def test_get_last_switch_returns_last_record(self):
        """Тест что get_last_switch возвращает последнюю запись."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent.switch_to(AgentType.CODER, "First switch")
        agent.switch_to(AgentType.ARCHITECT, "Second switch")
        
        last = agent.get_last_switch()
        assert last.to_agent == AgentType.ARCHITECT
    
    def test_get_switch_history_dict_returns_list(self):
        """Тест что get_switch_history_dict возвращает список словарей."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent.switch_to(AgentType.CODER, "Switch to coder")
        
        history = agent.get_switch_history_dict()
        assert isinstance(history, list)
        assert len(history) == 1
        assert history[0]["to"] == "coder"
    
    def test_switch_history_is_immutable(self):
        """Тест что switch_history возвращает копию."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        agent.switch_to(AgentType.CODER, "Switch")
        
        history1 = agent.switch_history
        history2 = agent.switch_history
        assert history1 is not history2


class TestAgentReset:
    """Тесты сброса агента."""
    
    def test_reset_to_orchestrator_switches_type(self):
        """Тест что reset_to_orchestrator переключает тип."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        agent.reset_to_orchestrator("Reset for new task")
        assert agent.current_type == AgentType.ORCHESTRATOR
    
    def test_reset_to_orchestrator_when_already_orchestrator(self):
        """Тест что reset не делает ничего если уже Orchestrator."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        initial_count = agent.switch_count
        agent.reset_to_orchestrator()
        assert agent.switch_count == initial_count


class TestAgentMetadata:
    """Тесты метаданных агента."""
    
    def test_add_metadata_stores_value(self):
        """Тест что add_metadata сохраняет значение."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        agent.add_metadata("key", "value")
        assert agent.get_metadata("key") == "value"
    
    def test_get_metadata_returns_default_if_not_found(self):
        """Тест что get_metadata возвращает default если не найдено."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        assert agent.get_metadata("nonexistent", "default") == "default"
    
    def test_metadata_property_returns_copy(self):
        """Тест что metadata возвращает копию."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        agent.add_metadata("key", "value")
        
        metadata1 = agent.metadata
        metadata2 = agent.metadata
        assert metadata1 is not metadata2


class TestAgentToolSupport:
    """Тесты поддержки инструментов."""
    
    def test_supports_tool_returns_true_for_supported(self):
        """Тест что supports_tool возвращает True для поддерживаемого инструмента."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        assert agent.supports_tool("write_file") == True
    
    def test_supports_tool_returns_false_for_unsupported(self):
        """Тест что supports_tool возвращает False для неподдерживаемого."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        assert agent.supports_tool("unknown_tool") == False


class TestAgentProperties:
    """Тесты свойств агента."""
    
    def test_session_id_property(self):
        """Тест свойства session_id."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        assert agent.session_id == "session-123"
    
    def test_capabilities_property(self):
        """Тест свойства capabilities."""
        caps = AgentCapabilities.for_coder()
        agent = Agent.create(
            session_id="session-123",
            capabilities=caps
        )
        assert agent.capabilities == caps
    
    def test_current_type_property(self):
        """Тест свойства current_type."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        assert agent.current_type == AgentType.CODER


class TestAgentStringRepresentation:
    """Тесты строкового представления агента."""
    
    def test_repr_shows_details(self):
        """Тест что repr() показывает детали."""
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        repr_str = repr(agent)
        assert "Agent" in repr_str
        assert "session-123" in repr_str
        assert "coder" in repr_str


class TestAgentSwitchRecord:
    """Тесты AgentSwitchRecord."""
    
    def test_create_switch_record(self):
        """Тест создания записи о переключении."""
        record = AgentSwitchRecord(
            id="record-123",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.CODER,
            reason="Need to code"
        )
        assert record.from_agent == AgentType.ORCHESTRATOR
        assert record.to_agent == AgentType.CODER
        assert record.reason == "Need to code"
    
    def test_to_dict_returns_dict(self):
        """Тест что to_dict возвращает словарь."""
        record = AgentSwitchRecord(
            id="record-123",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.CODER,
            reason="Need to code"
        )
        data = record.to_dict()
        assert isinstance(data, dict)
        assert data["from"] == "orchestrator"
        assert data["to"] == "coder"

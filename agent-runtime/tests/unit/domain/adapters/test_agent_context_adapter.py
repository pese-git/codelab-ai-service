"""
Unit тесты для AgentContextAdapter.

Проверяет корректность преобразования между AgentContext и Agent.
"""

import pytest
from datetime import datetime, timezone

from app.domain.entities.agent_context import AgentContext, AgentSwitch, AgentType
from app.domain.agent_context.entities.agent import Agent, AgentSwitchRecord
from app.domain.agent_context.value_objects import AgentId, AgentCapabilities
from app.domain.adapters import AgentContextAdapter


class TestAgentContextAdapter:
    """Тесты для AgentContextAdapter."""
    
    def test_to_agent_basic(self):
        """Тест базового преобразования AgentContext → Agent."""
        # Arrange
        context = AgentContext(
            id="ctx-123",
            session_id="session-456",
            current_agent=AgentType.ORCHESTRATOR
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        
        # Assert
        assert agent.id == "ctx-123"
        assert agent.session_id == "session-456"
        assert agent.current_type == AgentType.ORCHESTRATOR
        assert isinstance(agent.capabilities, AgentCapabilities)
    
    def test_to_agent_with_switch_history(self):
        """Тест преобразования AgentContext с историей переключений."""
        # Arrange
        context = AgentContext(
            id="ctx-123",
            session_id="session-456",
            current_agent=AgentType.ORCHESTRATOR
        )
        
        # Добавить переключение (ORCHESTRATOR → CODER)
        context.switch_to(
            target_agent=AgentType.CODER,
            reason="Coding task detected"
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        
        # Assert
        assert len(agent.switch_history) == 1
        assert isinstance(agent.switch_history[0], AgentSwitchRecord)
        assert agent.switch_history[0].to_agent == AgentType.CODER
        assert agent.switch_history[0].reason == "Coding task detected"
    
    def test_from_agent_basic(self):
        """Тест базового преобразования Agent → AgentContext."""
        # Arrange
        capabilities = AgentCapabilities.for_orchestrator()
        agent = Agent.create(
            session_id="session-789",
            capabilities=capabilities
        )
        
        # Act
        context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert context.id == agent.id
        assert context.session_id == "session-789"
        assert context.current_agent == AgentType.ORCHESTRATOR
        assert isinstance(context.switch_history, list)
    
    def test_from_agent_with_switch_history(self):
        """Тест преобразования Agent с историей переключений."""
        # Arrange
        capabilities = AgentCapabilities.for_orchestrator()
        agent = Agent.create("session-789", capabilities)
        agent.switch_to(AgentType.CODER, "Coding task")
        
        # Act
        context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert len(context.switch_history) == 1
        assert isinstance(context.switch_history[0], AgentSwitch)
        assert context.switch_history[0].to_agent == AgentType.CODER
        assert context.switch_history[0].reason == "Coding task"
    
    def test_round_trip_conversion(self):
        """Тест двустороннего преобразования AgentContext → Agent → AgentContext."""
        # Arrange
        original_context = AgentContext(
            id="ctx-999",
            session_id="session-111",
            current_agent=AgentType.ORCHESTRATOR
        )
        original_context.switch_to(
            target_agent=AgentType.ARCHITECT,
            reason="Architecture design"
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(original_context)
        restored_context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert restored_context.id == original_context.id
        assert restored_context.session_id == original_context.session_id
        assert restored_context.current_agent == original_context.current_agent
        assert len(restored_context.switch_history) == len(original_context.switch_history)
    
    def test_to_agent_list(self):
        """Тест преобразования списка AgentContext."""
        # Arrange
        contexts = [
            AgentContext(id="c1", session_id="s1", current_agent=AgentType.ORCHESTRATOR),
            AgentContext(id="c2", session_id="s2", current_agent=AgentType.CODER),
            AgentContext(id="c3", session_id="s3", current_agent=AgentType.ARCHITECT)
        ]
        
        # Act
        agents = AgentContextAdapter.to_agent_list(contexts)
        
        # Assert
        assert len(agents) == 3
        assert agents[0].id == "c1"
        assert agents[1].id == "c2"
        assert agents[2].id == "c3"
        assert agents[0].current_type == AgentType.ORCHESTRATOR
        assert agents[1].current_type == AgentType.CODER
        assert agents[2].current_type == AgentType.ARCHITECT
    
    def test_from_agent_list(self):
        """Тест преобразования списка Agent."""
        # Arrange
        agents = [
            Agent.create("s1", AgentCapabilities.for_orchestrator()),
            Agent.create("s2", AgentCapabilities.for_coder()),
            Agent.create("s3", AgentCapabilities.for_architect())
        ]
        
        # Act
        contexts = AgentContextAdapter.from_agent_list(agents)
        
        # Assert
        assert len(contexts) == 3
        assert contexts[0].session_id == "s1"
        assert contexts[1].session_id == "s2"
        assert contexts[2].session_id == "s3"
    
    def test_sync_state(self):
        """Тест синхронизации состояния между AgentContext и Agent."""
        # Arrange
        context = AgentContext(
            id="c1",
            session_id="s1",
            current_agent=AgentType.ORCHESTRATOR
        )
        agent = Agent.create("s1", AgentCapabilities.for_orchestrator())
        agent.switch_to(AgentType.CODER, "Coding task")
        
        # Act
        AgentContextAdapter.sync_state(context, agent)
        
        # Assert
        assert context.current_agent == AgentType.CODER
        assert len(context.switch_history) == 1
        assert context.switch_history[0].to_agent == AgentType.CODER
    
    def test_preserves_metadata(self):
        """Тест сохранения метаданных при преобразовании."""
        # Arrange
        context = AgentContext(
            id="c1",
            session_id="s1",
            current_agent=AgentType.ORCHESTRATOR,
            metadata={"key1": "value1", "key2": 123}
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        restored_context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert agent.metadata == context.metadata
        assert restored_context.metadata == context.metadata
    
    def test_preserves_timestamps(self):
        """Тест сохранения временных меток."""
        # Arrange
        now = datetime.now(timezone.utc)
        context = AgentContext(
            id="c1",
            session_id="s1",
            current_agent=AgentType.ORCHESTRATOR,
            created_at=now,
            updated_at=now,
            last_switch_at=now
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        
        # Assert
        assert agent.created_at == context.created_at
        assert agent.updated_at == context.updated_at
        assert agent.last_switch_at == context.last_switch_at
    
    def test_preserves_switch_count(self):
        """Тест сохранения счетчика переключений."""
        # Arrange
        context = AgentContext(
            id="c1",
            session_id="s1",
            current_agent=AgentType.ORCHESTRATOR,
            switch_count=5
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        restored_context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert agent.switch_count == 5
        assert restored_context.switch_count == 5
    
    def test_preserves_max_switches(self):
        """Тест сохранения лимита переключений."""
        # Arrange
        context = AgentContext(
            id="c1",
            session_id="s1",
            current_agent=AgentType.ORCHESTRATOR,
            max_switches=100
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        restored_context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert agent.capabilities.max_switches == 100
        assert restored_context.max_switches == 100
    
    def test_handles_different_agent_types(self):
        """Тест обработки различных типов агентов."""
        agent_types = [
            AgentType.ORCHESTRATOR,
            AgentType.CODER,
            AgentType.ARCHITECT,
            AgentType.DEBUG,
            AgentType.ASK,
            AgentType.UNIVERSAL
        ]
        
        for agent_type in agent_types:
            # Arrange
            context = AgentContext(
                id=f"c-{agent_type.value}",
                session_id="s1",
                current_agent=agent_type
            )
            
            # Act
            agent = AgentContextAdapter.to_agent(context)
            restored_context = AgentContextAdapter.from_agent(agent)
            
            # Assert
            assert agent.current_type == agent_type
            assert restored_context.current_agent == agent_type
    
    def test_handles_switch_with_confidence(self):
        """Тест обработки переключений с уверенностью."""
        # Arrange
        context = AgentContext(
            id="c1",
            session_id="s1",
            current_agent=AgentType.ORCHESTRATOR
        )
        context.switch_to(
            target_agent=AgentType.CODER,
            reason="Coding task",
            confidence="high"
        )
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        restored_context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert agent.switch_history[0].confidence == "high"
        assert restored_context.switch_history[0].confidence == "high"
    
    def test_handles_multiple_switches(self):
        """Тест обработки множественных переключений."""
        # Arrange
        context = AgentContext(
            id="c1",
            session_id="s1",
            current_agent=AgentType.ORCHESTRATOR
        )
        context.switch_to(AgentType.CODER, "Coding task")
        context.switch_to(AgentType.ARCHITECT, "Design needed")
        context.switch_to(AgentType.DEBUG, "Bug found")
        
        # Act
        agent = AgentContextAdapter.to_agent(context)
        restored_context = AgentContextAdapter.from_agent(agent)
        
        # Assert
        assert len(agent.switch_history) == 3
        assert len(restored_context.switch_history) == 3
        assert agent.switch_history[0].to_agent == AgentType.CODER
        assert agent.switch_history[1].to_agent == AgentType.ARCHITECT
        assert agent.switch_history[2].to_agent == AgentType.DEBUG

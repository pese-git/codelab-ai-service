"""
Тесты для AgentCoordinationService.

Проверяет функциональность нового сервиса координации агентов.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from app.domain.agent_context.services import AgentCoordinationService
from app.domain.agent_context.entities.agent import Agent
from app.domain.agent_context.value_objects.agent_id import AgentId
from app.domain.agent_context.value_objects.agent_capabilities import (
    AgentCapabilities,
    AgentType
)
from app.core.errors import AgentSwitchError


@pytest.fixture
def mock_repository():
    """Mock repository для тестов."""
    repo = AsyncMock()
    repo.find_by_session_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    repo.find_by_agent_type = AsyncMock(return_value=[])
    repo.find_with_many_switches = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def service(mock_repository):
    """Сервис для тестов."""
    return AgentCoordinationService(repository=mock_repository)


@pytest.mark.asyncio
class TestAgentCoordinationService:
    """Тесты для AgentCoordinationService."""
    
    async def test_get_or_create_agent_creates_new(
        self,
        service,
        mock_repository
    ):
        """Тест: создание нового агента."""
        # Arrange
        session_id = "session-123"
        mock_repository.find_by_session_id.return_value = None
        
        # Act
        agent = await service.get_or_create_agent(session_id)
        
        # Assert
        assert agent is not None
        assert agent.session_id == session_id
        assert agent.current_type == AgentType.ORCHESTRATOR
        mock_repository.save.assert_called_once()
    
    async def test_get_or_create_agent_returns_existing(
        self,
        service,
        mock_repository
    ):
        """Тест: возврат существующего агента."""
        # Arrange
        session_id = "session-123"
        existing = Agent.create(
            session_id=session_id,
            capabilities=AgentCapabilities.for_orchestrator()
        )
        mock_repository.find_by_session_id.return_value = existing
        
        # Act
        agent = await service.get_or_create_agent(session_id)
        
        # Assert
        assert agent == existing
        mock_repository.save.assert_not_called()
    
    async def test_assign_agent_creates_new_with_type(
        self,
        service,
        mock_repository
    ):
        """Тест: назначение агента создает нового с указанным типом."""
        # Arrange
        session_id = "session-123"
        mock_repository.find_by_session_id.return_value = None
        
        # Act
        agent = await service.assign_agent(
            session_id=session_id,
            agent_type=AgentType.CODER,
            reason="User requested"
        )
        
        # Assert
        assert agent.current_type == AgentType.CODER
        mock_repository.save.assert_called_once()
    
    async def test_assign_agent_returns_if_already_correct_type(
        self,
        service,
        mock_repository
    ):
        """Тест: назначение агента возвращает существующего если тип совпадает."""
        # Arrange
        session_id = "session-123"
        existing = Agent.create(
            session_id=session_id,
            capabilities=AgentCapabilities.for_coder()
        )
        mock_repository.find_by_session_id.return_value = existing
        
        # Act
        agent = await service.assign_agent(
            session_id=session_id,
            agent_type=AgentType.CODER,
            reason="Already coder"
        )
        
        # Assert
        assert agent == existing
        # save не должен вызываться, т.к. агент уже нужного типа
        assert mock_repository.save.call_count == 0
    
    async def test_switch_agent_creates_if_not_exists(
        self,
        service,
        mock_repository
    ):
        """Тест: переключение создает агента если его нет."""
        # Arrange
        session_id = "session-123"
        mock_repository.find_by_session_id.return_value = None
        
        # Act
        agent = await service.switch_agent(
            session_id=session_id,
            target_type=AgentType.CODER,
            reason="Need to code"
        )
        
        # Assert
        assert agent.current_type == AgentType.CODER
        mock_repository.save.assert_called()
    
    async def test_switch_agent_switches_existing(
        self,
        service,
        mock_repository
    ):
        """Тест: переключение существующего агента."""
        # Arrange
        session_id = "session-123"
        agent = Agent.create(
            session_id=session_id,
            capabilities=AgentCapabilities.for_orchestrator()
        )
        mock_repository.find_by_session_id.return_value = agent
        
        # Act
        result = await service.switch_agent(
            session_id=session_id,
            target_type=AgentType.CODER,
            reason="Coding task detected"
        )
        
        # Assert
        assert result.current_type == AgentType.CODER
        assert result.switch_count == 1
        assert len(result.switch_history) == 1
        mock_repository.save.assert_called_once()
    
    async def test_switch_agent_raises_on_same_type(
        self,
        service,
        mock_repository
    ):
        """Тест: ошибка при переключении на тот же тип."""
        # Arrange
        session_id = "session-123"
        agent = Agent.create(
            session_id=session_id,
            capabilities=AgentCapabilities.for_coder()
        )
        mock_repository.find_by_session_id.return_value = agent
        
        # Act & Assert
        with pytest.raises(AgentSwitchError):
            await service.switch_agent(
                session_id=session_id,
                target_type=AgentType.CODER,
                reason="Already coder"
            )
    
    async def test_get_current_agent_type_returns_type(
        self,
        service,
        mock_repository
    ):
        """Тест: получение текущего типа агента."""
        # Arrange
        session_id = "session-123"
        agent = Agent.create(
            session_id=session_id,
            capabilities=AgentCapabilities.for_coder()
        )
        mock_repository.find_by_session_id.return_value = agent
        
        # Act
        agent_type = await service.get_current_agent_type(session_id)
        
        # Assert
        assert agent_type == AgentType.CODER
    
    async def test_get_current_agent_type_returns_none_if_not_found(
        self,
        service,
        mock_repository
    ):
        """Тест: None если агент не найден."""
        # Arrange
        mock_repository.find_by_session_id.return_value = None
        
        # Act
        agent_type = await service.get_current_agent_type("non-existent")
        
        # Assert
        assert agent_type is None
    
    async def test_get_agent_returns_agent(
        self,
        service,
        mock_repository
    ):
        """Тест: получение агента."""
        # Arrange
        session_id = "session-123"
        agent = Agent.create(
            session_id=session_id,
            capabilities=AgentCapabilities.for_coder()
        )
        mock_repository.find_by_session_id.return_value = agent
        
        # Act
        result = await service.get_agent(session_id)
        
        # Assert
        assert result == agent
    
    async def test_get_switch_history_returns_history(
        self,
        service,
        mock_repository
    ):
        """Тест: получение истории переключений."""
        # Arrange
        session_id = "session-123"
        agent = Agent.create(
            session_id=session_id,
            capabilities=AgentCapabilities.for_orchestrator()
        )
        # Выполнить переключение
        agent.switch_to(AgentType.CODER, "Need to code")
        mock_repository.find_by_session_id.return_value = agent
        
        # Act
        history = await service.get_switch_history(session_id)
        
        # Assert
        assert len(history) == 1
        assert history[0].to_agent == AgentType.CODER
    
    async def test_get_switch_history_returns_empty_if_not_found(
        self,
        service,
        mock_repository
    ):
        """Тест: пустая история если агент не найден."""
        # Arrange
        mock_repository.find_by_session_id.return_value = None
        
        # Act
        history = await service.get_switch_history("non-existent")
        
        # Assert
        assert history == []
    
    async def test_get_agent_usage_stats(
        self,
        service,
        mock_repository
    ):
        """Тест: получение статистики использования агентов."""
        # Arrange
        coder_agents = [
            Agent.create("s1", AgentCapabilities.for_coder()),
            Agent.create("s2", AgentCapabilities.for_coder())
        ]
        
        async def mock_find_by_type(agent_type, limit):
            if agent_type == AgentType.CODER:
                return coder_agents
            return []
        
        mock_repository.find_by_agent_type.side_effect = mock_find_by_type
        
        # Act
        stats = await service.get_agent_usage_stats()
        
        # Assert
        assert stats[AgentType.CODER.value] == 2
        assert stats[AgentType.ORCHESTRATOR.value] == 0
    
    async def test_get_problematic_sessions(
        self,
        service,
        mock_repository
    ):
        """Тест: получение проблемных сессий."""
        # Arrange
        problematic = [
            Agent.create("s1", AgentCapabilities.for_orchestrator()),
            Agent.create("s2", AgentCapabilities.for_orchestrator())
        ]
        mock_repository.find_with_many_switches.return_value = problematic
        
        # Act
        result = await service.get_problematic_sessions(min_switches=5)
        
        # Assert
        assert len(result) == 2
        mock_repository.find_with_many_switches.assert_called_once_with(
            min_switches=5,
            limit=100
        )
    
    async def test_can_switch_to_returns_true_if_no_agent(
        self,
        service,
        mock_repository
    ):
        """Тест: можно переключиться если агента нет."""
        # Arrange
        mock_repository.find_by_session_id.return_value = None
        
        # Act
        can_switch = await service.can_switch_to("session-123", AgentType.CODER)
        
        # Assert
        assert can_switch is True
    
    async def test_can_switch_to_checks_agent_capability(
        self,
        service,
        mock_repository
    ):
        """Тест: проверка возможности переключения через агента."""
        # Arrange
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_orchestrator()
        )
        mock_repository.find_by_session_id.return_value = agent
        
        # Act
        can_switch = await service.can_switch_to("session-123", AgentType.CODER)
        
        # Assert
        assert can_switch is True
    
    async def test_get_capabilities_returns_capabilities(
        self,
        service,
        mock_repository
    ):
        """Тест: получение возможностей агента."""
        # Arrange
        agent = Agent.create(
            session_id="session-123",
            capabilities=AgentCapabilities.for_coder()
        )
        mock_repository.find_by_session_id.return_value = agent
        
        # Act
        capabilities = await service.get_capabilities("session-123")
        
        # Assert
        assert capabilities is not None
        assert capabilities.agent_type == AgentType.CODER
    
    async def test_get_capabilities_returns_none_if_not_found(
        self,
        service,
        mock_repository
    ):
        """Тест: None если агент не найден."""
        # Arrange
        mock_repository.find_by_session_id.return_value = None
        
        # Act
        capabilities = await service.get_capabilities("non-existent")
        
        # Assert
        assert capabilities is None

"""
Тесты для MessageOrchestrationService.

Проверяет корректность работы оркестрации сообщений,
переключения агентов и streaming ответов.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.domain.services.message_orchestration import MessageOrchestrationService
from app.domain.services.session_management import SessionManagementService
from app.domain.services.agent_orchestration import AgentOrchestrationService
from app.domain.entities import Session, AgentContext, AgentType
from app.models.schemas import StreamChunk


@pytest.fixture
def mock_session_service():
    """Мок сервиса управления сессиями"""
    service = AsyncMock(spec=SessionManagementService)
    
    # Настроить поведение по умолчанию
    async def get_or_create_session(session_id):
        return Session(id=session_id)
    
    service.get_or_create_session = AsyncMock(side_effect=get_or_create_session)
    
    return service


@pytest.fixture
def mock_agent_service():
    """Мок сервиса оркестрации агентов"""
    service = AsyncMock(spec=AgentOrchestrationService)
    
    # Настроить поведение по умолчанию
    async def get_or_create_context(session_id, initial_agent=AgentType.ORCHESTRATOR):
        return AgentContext(
            id=f"ctx-{session_id}",
            session_id=session_id,
            current_agent=AgentType.ORCHESTRATOR
        )
    
    async def switch_agent(session_id, target_agent, reason, confidence=None):
        context = AgentContext(
            id=f"ctx-{session_id}",
            session_id=session_id,
            current_agent=target_agent
        )
        return context
    
    service.get_or_create_context = AsyncMock(side_effect=get_or_create_context)
    service.switch_agent = AsyncMock(side_effect=switch_agent)
    service.get_current_agent = AsyncMock(return_value=AgentType.ORCHESTRATOR)
    
    return service


@pytest.fixture
def mock_agent_router():
    """Мок роутера агентов"""
    router = MagicMock()
    
    # Создать мок агента
    mock_agent = MagicMock()
    
    async def mock_process(*args, **kwargs):
        """Мок процесса обработки агента"""
        yield StreamChunk(
            type="assistant_message",
            token="Hello",
            is_final=False
        )
        yield StreamChunk(
            type="assistant_message",
            token=" World",
            is_final=False
        )
        yield StreamChunk(
            type="done",
            is_final=True
        )
    
    mock_agent.process = mock_process
    router.get_agent = MagicMock(return_value=mock_agent)
    
    return router


@pytest.fixture
def mock_lock_manager():
    """Мок менеджера блокировок"""
    lock_manager = MagicMock()
    
    # Создать контекстный менеджер для блокировки
    class MockLock:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    lock_manager.lock = MagicMock(return_value=MockLock())
    
    return lock_manager


@pytest.fixture
def orchestration_service(
    mock_session_service,
    mock_agent_service,
    mock_agent_router,
    mock_lock_manager
):
    """Фикстура для MessageOrchestrationService"""
    return MessageOrchestrationService(
        session_service=mock_session_service,
        agent_service=mock_agent_service,
        agent_router=mock_agent_router,
        lock_manager=mock_lock_manager
    )


# ==================== Тесты базовой функциональности ====================

class TestMessageOrchestrationBasics:
    """Тесты базовой функциональности"""
    
    @pytest.mark.asyncio
    async def test_process_message_basic(self, orchestration_service):
        """Тест базовой обработки сообщения"""
        chunks = []
        
        async for chunk in orchestration_service.process_message(
            session_id="session-1",
            message="Hello"
        ):
            chunks.append(chunk)
        
        # Проверить что получены чанки
        assert len(chunks) > 0
        
        # Проверить что есть чанки с сообщениями
        message_chunks = [c for c in chunks if c.type == "assistant_message"]
        assert len(message_chunks) > 0
    
    @pytest.mark.asyncio
    async def test_process_message_uses_lock(
        self,
        orchestration_service,
        mock_lock_manager
    ):
        """Тест что используется блокировка сессии"""
        chunks = []
        
        async for chunk in orchestration_service.process_message(
            session_id="session-1",
            message="Hello"
        ):
            chunks.append(chunk)
        
        # Проверить что блокировка была вызвана
        mock_lock_manager.lock.assert_called_once_with("session-1")
    
    @pytest.mark.asyncio
    async def test_process_message_creates_session(
        self,
        orchestration_service,
        mock_session_service
    ):
        """Тест что создается или получается сессия"""
        chunks = []
        
        async for chunk in orchestration_service.process_message(
            session_id="session-1",
            message="Hello"
        ):
            chunks.append(chunk)
        
        # Проверить что сервис сессий был вызван
        mock_session_service.get_or_create_session.assert_called_once_with("session-1")
    
    @pytest.mark.asyncio
    async def test_process_message_creates_context(
        self,
        orchestration_service,
        mock_agent_service
    ):
        """Тест что создается или получается контекст агента"""
        chunks = []
        
        async for chunk in orchestration_service.process_message(
            session_id="session-1",
            message="Hello"
        ):
            chunks.append(chunk)
        
        # Проверить что сервис агентов был вызван
        mock_agent_service.get_or_create_context.assert_called()


# ==================== Тесты переключения агентов ====================

class TestAgentSwitching:
    """Тесты переключения агентов"""
    
    @pytest.mark.asyncio
    async def test_explicit_agent_switch(
        self,
        orchestration_service,
        mock_agent_service
    ):
        """Тест явного переключения агента"""
        chunks = []
        
        async for chunk in orchestration_service.process_message(
            session_id="session-1",
            message="Hello",
            agent_type=AgentType.CODER
        ):
            chunks.append(chunk)
        
        # Проверить что был вызван switch_agent
        mock_agent_service.switch_agent.assert_called()
        
        # Проверить что есть чанк agent_switched
        switched_chunks = [c for c in chunks if c.type == "agent_switched"]
        assert len(switched_chunks) > 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_routing(self, mock_agent_service, mock_lock_manager):
        """Тест маршрутизации через Orchestrator"""
        # Создать мок роутера с Orchestrator, который возвращает switch_agent
        mock_router = MagicMock()
        mock_orchestrator = MagicMock()
        
        async def orchestrator_process(*args, **kwargs):
            yield StreamChunk(
                type="switch_agent",
                metadata={
                    "target_agent": "coder",
                    "reason": "Coding task detected",
                    "confidence": "high"
                },
                is_final=True
            )
        
        mock_orchestrator.process = orchestrator_process
        
        mock_coder = MagicMock()
        
        async def coder_process(*args, **kwargs):
            yield StreamChunk(
                type="assistant_message",
                token="I'll help with coding",
                is_final=False
            )
        
        mock_coder.process = coder_process
        
        def get_agent(agent_type):
            if agent_type == AgentType.ORCHESTRATOR:
                return mock_orchestrator
            elif agent_type == AgentType.CODER:
                return mock_coder
            return mock_orchestrator
        
        mock_router.get_agent = get_agent
        
        # Создать сервис с этим роутером
        mock_session_service = AsyncMock(spec=SessionManagementService)
        mock_session_service.get_or_create_session = AsyncMock(
            return_value=Session(id="session-1")
        )
        
        service = MessageOrchestrationService(
            session_service=mock_session_service,
            agent_service=mock_agent_service,
            agent_router=mock_router,
            lock_manager=mock_lock_manager
        )
        
        chunks = []
        async for chunk in service.process_message(
            session_id="session-1",
            message="Write a function"
        ):
            chunks.append(chunk)
        
        # Проверить что был вызван switch_agent
        mock_agent_service.switch_agent.assert_called()
        
        # Проверить что есть чанк agent_switched
        switched_chunks = [c for c in chunks if c.type == "agent_switched"]
        assert len(switched_chunks) > 0
        assert switched_chunks[0].metadata["to_agent"] == "coder"


# ==================== Тесты вспомогательных методов ====================

class TestHelperMethods:
    """Тесты вспомогательных методов"""
    
    @pytest.mark.asyncio
    async def test_get_current_agent(
        self,
        orchestration_service,
        mock_agent_service
    ):
        """Тест получения текущего агента"""
        agent = await orchestration_service.get_current_agent("session-1")
        
        # Проверить что был вызван метод сервиса
        mock_agent_service.get_current_agent.assert_called_once_with("session-1")
        
        assert agent == AgentType.ORCHESTRATOR
    
    @pytest.mark.asyncio
    async def test_reset_session(
        self,
        orchestration_service,
        mock_agent_service
    ):
        """Тест сброса сессии"""
        await orchestration_service.reset_session("session-1")
        
        # Проверить что был вызван switch_agent с ORCHESTRATOR
        mock_agent_service.switch_agent.assert_called_once()
        call_args = mock_agent_service.switch_agent.call_args
        
        assert call_args[1]["session_id"] == "session-1"
        assert call_args[1]["target_agent"] == AgentType.ORCHESTRATOR
        assert call_args[1]["reason"] == "Session reset"
    
    def test_context_to_dict(self, orchestration_service):
        """Тест преобразования контекста в словарь"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            current_agent=AgentType.CODER
        )
        context.switch_to(AgentType.DEBUG, "Debugging needed", confidence="high")
        
        result = orchestration_service._context_to_dict(context)
        
        assert result["session_id"] == "session-1"
        assert result["current_agent"] == "debug"
        assert result["switch_count"] == 1
        assert len(result["agent_history"]) == 1
        assert result["agent_history"][0]["to_agent"] == "debug"
        assert result["agent_history"][0]["reason"] == "Debugging needed"
        assert result["agent_history"][0]["confidence"] == "high"


# ==================== Тесты обработки ошибок ====================

class TestErrorHandling:
    """Тесты обработки ошибок"""
    
    @pytest.mark.asyncio
    async def test_process_message_handles_agent_error(
        self,
        mock_session_service,
        mock_agent_service,
        mock_lock_manager
    ):
        """Тест обработки ошибки от агента"""
        # Создать роутер с агентом, который выбрасывает ошибку
        mock_router = MagicMock()
        mock_agent = MagicMock()
        
        async def failing_process(*args, **kwargs):
            raise ValueError("Agent processing failed")
            yield  # Unreachable, но нужно для async generator
        
        mock_agent.process = failing_process
        mock_router.get_agent = MagicMock(return_value=mock_agent)
        
        service = MessageOrchestrationService(
            session_service=mock_session_service,
            agent_service=mock_agent_service,
            agent_router=mock_router,
            lock_manager=mock_lock_manager
        )
        
        # Проверить что ошибка пробрасывается
        with pytest.raises(ValueError, match="Agent processing failed"):
            async for chunk in service.process_message(
                session_id="session-1",
                message="Hello"
            ):
                pass
    
    @pytest.mark.asyncio
    async def test_process_message_publishes_error_event(
        self,
        mock_session_service,
        mock_agent_service,
        mock_lock_manager
    ):
        """Тест публикации события ошибки"""
        # Создать event publisher
        event_publisher = AsyncMock()
        
        # Создать роутер с агентом, который выбрасывает ошибку
        mock_router = MagicMock()
        mock_agent = MagicMock()
        
        async def failing_process(*args, **kwargs):
            raise ValueError("Agent processing failed")
            yield
        
        mock_agent.process = failing_process
        mock_router.get_agent = MagicMock(return_value=mock_agent)
        
        service = MessageOrchestrationService(
            session_service=mock_session_service,
            agent_service=mock_agent_service,
            agent_router=mock_router,
            lock_manager=mock_lock_manager,
            event_publisher=event_publisher
        )
        
        # Попытаться обработать сообщение
        with pytest.raises(ValueError):
            async for chunk in service.process_message(
                session_id="session-1",
                message="Hello"
            ):
                pass
        
        # Проверить что event publisher был вызван дважды:
        # 1. AgentErrorOccurredEvent
        # 2. AgentProcessingCompletedEvent (в finally)
        assert event_publisher.call_count == 2


# ==================== Интеграционные тесты ====================

class TestIntegration:
    """Интеграционные тесты"""
    
    @pytest.mark.asyncio
    async def test_full_message_flow(
        self,
        mock_session_service,
        mock_agent_service,
        mock_lock_manager
    ):
        """Тест полного потока обработки сообщения"""
        # Создать роутер с реалистичным поведением
        mock_router = MagicMock()
        mock_agent = MagicMock()
        
        async def realistic_process(*args, **kwargs):
            # Симулировать streaming ответ
            yield StreamChunk(
                type="assistant_message",
                token="I",
                is_final=False
            )
            yield StreamChunk(
                type="assistant_message",
                token=" understand",
                is_final=False
            )
            yield StreamChunk(
                type="assistant_message",
                token=" your",
                is_final=False
            )
            yield StreamChunk(
                type="assistant_message",
                token=" request",
                is_final=False
            )
            yield StreamChunk(
                type="done",
                is_final=True
            )
        
        mock_agent.process = realistic_process
        mock_router.get_agent = MagicMock(return_value=mock_agent)
        
        service = MessageOrchestrationService(
            session_service=mock_session_service,
            agent_service=mock_agent_service,
            agent_router=mock_router,
            lock_manager=mock_lock_manager
        )
        
        chunks = []
        async for chunk in service.process_message(
            session_id="session-1",
            message="Hello, can you help me?"
        ):
            chunks.append(chunk)
        
        # Проверить что получены все чанки
        # Orchestrator не переключает, поэтому агент вызывается дважды
        # (один раз для Orchestrator проверки, второй раз для обработки)
        assert len(chunks) >= 5
        
        # Проверить типы чанков
        message_chunks = [c for c in chunks if c.type == "assistant_message"]
        assert len(message_chunks) >= 4
        
        done_chunks = [c for c in chunks if c.type == "done"]
        assert len(done_chunks) >= 1
        
        # Проверить что последний чанк - done
        assert chunks[-1].type == "done"
        assert chunks[-1].is_final is True

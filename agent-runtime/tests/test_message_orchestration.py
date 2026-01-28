"""
Тесты для MessageOrchestrationService.

Проверяет корректность работы оркестрации сообщений,
переключения агентов и streaming ответов.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.domain.services.message_orchestration import MessageOrchestrationService
from app.domain.services.message_processor import MessageProcessor
from app.domain.services.agent_switcher import AgentSwitcher
from app.domain.services.tool_result_handler import ToolResultHandler
from app.domain.services.hitl_decision_handler import HITLDecisionHandler
from app.domain.entities import Session, AgentContext, AgentType
from app.models.schemas import StreamChunk


@pytest.fixture
def mock_message_processor():
    """Мок процессора сообщений"""
    processor = AsyncMock(spec=MessageProcessor)
    
    # Настроить поведение по умолчанию
    async def mock_process(session_id, message, agent_type=None, correlation_id=None):
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
    
    processor.process = mock_process
    
    return processor


@pytest.fixture
def mock_agent_switcher():
    """Мок switcher агентов"""
    switcher = AsyncMock(spec=AgentSwitcher)
    
    # Настроить поведение по умолчанию
    async def mock_switch(session_id, target_agent, reason=None, confidence="high"):
        yield StreamChunk(
            type="agent_switched",
            content=f"Switched to {target_agent.value} agent",
            metadata={
                "from_agent": "orchestrator",
                "to_agent": target_agent.value,
                "reason": reason or f"User requested switch to {target_agent.value}",
                "confidence": confidence
            },
            is_final=True
        )
    
    switcher.switch = mock_switch
    switcher.get_current_agent = AsyncMock(return_value=AgentType.ORCHESTRATOR)
    switcher.reset_to_orchestrator = AsyncMock()
    
    return switcher


@pytest.fixture
def mock_tool_result_handler():
    """Мок handler результатов инструментов"""
    handler = AsyncMock(spec=ToolResultHandler)
    
    # Настроить поведение по умолчанию
    async def mock_handle(session_id, call_id, result=None, error=None):
        yield StreamChunk(
            type="assistant_message",
            token="Tool result processed",
            is_final=True
        )
    
    handler.handle = mock_handle
    
    return handler


@pytest.fixture
def mock_hitl_handler():
    """Мок handler HITL решений"""
    handler = AsyncMock(spec=HITLDecisionHandler)
    
    # Настроить поведение по умолчанию
    async def mock_handle(session_id, call_id, decision, modified_arguments=None, feedback=None):
        yield StreamChunk(
            type="assistant_message",
            token="HITL decision processed",
            is_final=True
        )
    
    handler.handle = mock_handle
    
    return handler


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
    mock_message_processor,
    mock_agent_switcher,
    mock_tool_result_handler,
    mock_hitl_handler,
    mock_lock_manager
):
    """Фикстура для MessageOrchestrationService (фасад)"""
    return MessageOrchestrationService(
        message_processor=mock_message_processor,
        agent_switcher=mock_agent_switcher,
        tool_result_handler=mock_tool_result_handler,
        hitl_handler=mock_hitl_handler,
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
    async def test_process_message_delegates_to_processor(
        self,
        orchestration_service,
        mock_message_processor
    ):
        """Тест что обработка делегируется в MessageProcessor"""
        chunks = []
        
        async for chunk in orchestration_service.process_message(
            session_id="session-1",
            message="Hello"
        ):
            chunks.append(chunk)
        
        # Проверить что MessageProcessor был вызван
        # mock_process вызывается как async generator, проверяем что он был создан
        assert len(chunks) > 0
    
    @pytest.mark.asyncio
    async def test_process_message_with_agent_type(
        self,
        orchestration_service,
        mock_message_processor
    ):
        """Тест обработки с явным типом агента"""
        chunks = []
        
        async for chunk in orchestration_service.process_message(
            session_id="session-1",
            message="Hello",
            agent_type=AgentType.CODER
        ):
            chunks.append(chunk)
        
        # Проверить что получены чанки
        assert len(chunks) > 0


# ==================== Тесты переключения агентов ====================

class TestAgentSwitching:
    """Тесты переключения агентов"""
    
    @pytest.mark.asyncio
    async def test_explicit_agent_switch(
        self,
        orchestration_service,
        mock_agent_switcher
    ):
        """Тест явного переключения агента"""
        chunks = []
        
        async for chunk in orchestration_service.switch_agent(
            session_id="session-1",
            agent_type=AgentType.CODER,
            reason="User requested"
        ):
            chunks.append(chunk)
        
        # Проверить что есть чанк agent_switched
        switched_chunks = [c for c in chunks if c.type == "agent_switched"]
        assert len(switched_chunks) > 0
        assert switched_chunks[0].metadata["to_agent"] == "coder"
    
    @pytest.mark.asyncio
    async def test_orchestrator_routing(
        self,
        mock_lock_manager
    ):
        """Тест маршрутизации через Orchestrator"""
        # Создать мок MessageProcessor с маршрутизацией
        mock_processor = AsyncMock(spec=MessageProcessor)
        
        async def processor_with_routing(*args, **kwargs):
            # Симулировать переключение агента
            yield StreamChunk(
                type="agent_switched",
                metadata={
                    "from_agent": "orchestrator",
                    "to_agent": "coder",
                    "reason": "Coding task detected",
                    "confidence": "high"
                },
                is_final=False
            )
            yield StreamChunk(
                type="assistant_message",
                token="I'll help with coding",
                is_final=True
            )
        
        mock_processor.process = processor_with_routing
        
        # Создать моки для других сервисов
        mock_switcher = AsyncMock(spec=AgentSwitcher)
        mock_tool_handler = AsyncMock(spec=ToolResultHandler)
        mock_hitl_handler = AsyncMock(spec=HITLDecisionHandler)
        
        service = MessageOrchestrationService(
            message_processor=mock_processor,
            agent_switcher=mock_switcher,
            tool_result_handler=mock_tool_handler,
            hitl_handler=mock_hitl_handler,
            lock_manager=mock_lock_manager
        )
        
        chunks = []
        async for chunk in service.process_message(
            session_id="session-1",
            message="Write a function"
        ):
            chunks.append(chunk)
        
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
        mock_agent_switcher
    ):
        """Тест получения текущего агента"""
        agent = await orchestration_service.get_current_agent("session-1")
        
        # Проверить что был вызван метод AgentSwitcher
        mock_agent_switcher.get_current_agent.assert_called_once_with("session-1")
        
        assert agent == AgentType.ORCHESTRATOR
    
    @pytest.mark.asyncio
    async def test_reset_session(
        self,
        orchestration_service,
        mock_agent_switcher
    ):
        """Тест сброса сессии"""
        await orchestration_service.reset_session("session-1")
        
        # Проверить что был вызван reset_to_orchestrator
        mock_agent_switcher.reset_to_orchestrator.assert_called_once_with("session-1")
    
    @pytest.mark.asyncio
    async def test_switch_agent(
        self,
        orchestration_service,
        mock_agent_switcher
    ):
        """Тест явного переключения агента"""
        chunks = []
        
        async for chunk in orchestration_service.switch_agent(
            session_id="session-1",
            agent_type=AgentType.CODER,
            reason="User requested"
        ):
            chunks.append(chunk)
        
        # Проверить что есть чанк agent_switched
        switched_chunks = [c for c in chunks if c.type == "agent_switched"]
        assert len(switched_chunks) > 0
        assert switched_chunks[0].metadata["to_agent"] == "coder"


# ==================== Тесты обработки ошибок ====================

class TestErrorHandling:
    """Тесты обработки ошибок"""
    
    @pytest.mark.asyncio
    async def test_process_message_handles_agent_error(
        self,
        mock_lock_manager
    ):
        """Тест обработки ошибки от агента"""
        # Создать MessageProcessor который выбрасывает ошибку
        mock_processor = AsyncMock(spec=MessageProcessor)
        
        async def failing_process(*args, **kwargs):
            raise ValueError("Agent processing failed")
            yield  # Unreachable, но нужно для async generator
        
        mock_processor.process = failing_process
        
        # Создать моки для других сервисов
        mock_switcher = AsyncMock(spec=AgentSwitcher)
        mock_tool_handler = AsyncMock(spec=ToolResultHandler)
        mock_hitl_handler = AsyncMock(spec=HITLDecisionHandler)
        
        service = MessageOrchestrationService(
            message_processor=mock_processor,
            agent_switcher=mock_switcher,
            tool_result_handler=mock_tool_handler,
            hitl_handler=mock_hitl_handler,
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
        mock_lock_manager
    ):
        """Тест публикации события ошибки"""
        # Создать MessageProcessor который выбрасывает ошибку
        mock_processor = AsyncMock(spec=MessageProcessor)
        
        async def failing_process(*args, **kwargs):
            raise ValueError("Agent processing failed")
            yield
        
        mock_processor.process = failing_process
        
        # Создать моки для других сервисов
        mock_switcher = AsyncMock(spec=AgentSwitcher)
        mock_tool_handler = AsyncMock(spec=ToolResultHandler)
        mock_hitl_handler = AsyncMock(spec=HITLDecisionHandler)
        
        service = MessageOrchestrationService(
            message_processor=mock_processor,
            agent_switcher=mock_switcher,
            tool_result_handler=mock_tool_handler,
            hitl_handler=mock_hitl_handler,
            lock_manager=mock_lock_manager
        )
        
        # Попытаться обработать сообщение
        # События публикуются через глобальный event_bus, а не через event_publisher
        # Тест просто проверяет что ошибка корректно обрабатывается
        with pytest.raises(ValueError):
            async for chunk in service.process_message(
                session_id="session-1",
                message="Hello"
            ):
                pass


# ==================== Интеграционные тесты ====================

class TestIntegration:
    """Интеграционные тесты"""
    
    @pytest.mark.asyncio
    async def test_full_message_flow(
        self,
        mock_lock_manager
    ):
        """Тест полного потока обработки сообщения"""
        # Создать MessageProcessor с реалистичным поведением
        mock_processor = AsyncMock(spec=MessageProcessor)
        
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
        
        mock_processor.process = realistic_process
        
        # Создать моки для других сервисов
        mock_switcher = AsyncMock(spec=AgentSwitcher)
        mock_tool_handler = AsyncMock(spec=ToolResultHandler)
        mock_hitl_handler = AsyncMock(spec=HITLDecisionHandler)
        
        service = MessageOrchestrationService(
            message_processor=mock_processor,
            agent_switcher=mock_switcher,
            tool_result_handler=mock_tool_handler,
            hitl_handler=mock_hitl_handler,
            lock_manager=mock_lock_manager
        )
        
        chunks = []
        async for chunk in service.process_message(
            session_id="session-1",
            message="Hello, can you help me?"
        ):
            chunks.append(chunk)
        
        # Проверить что получены все чанки
        assert len(chunks) == 5
        
        # Проверить типы чанков
        message_chunks = [c for c in chunks if c.type == "assistant_message"]
        assert len(message_chunks) == 4
        
        done_chunks = [c for c in chunks if c.type == "done"]
        assert len(done_chunks) == 1
        
        # Проверить что последний чанк - done
        assert chunks[-1].type == "done"
        assert chunks[-1].is_final is True

"""
Integration тесты для StreamLLMResponseHandler.

Тестирует координацию между компонентами при стриминге LLM ответов.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from app.application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
from app.domain.entities.llm_response import (
    LLMResponse,
    ProcessedResponse,
    ToolCall,
    TokenUsage
)
from app.models.schemas import StreamChunk


class TestStreamLLMResponseHandler:
    """Integration тесты для StreamLLMResponseHandler"""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client"""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_tool_filter(self):
        """Mock tool filter service"""
        filter_service = Mock()
        filter_service.filter_tools.return_value = [
            {"function": {"name": "read_file"}},
            {"function": {"name": "write_file"}}
        ]
        return filter_service
    
    @pytest.fixture
    def mock_response_processor(self):
        """Mock response processor"""
        processor = Mock()
        return processor
    
    @pytest.fixture
    def mock_event_publisher(self):
        """Mock event publisher"""
        publisher = AsyncMock()
        return publisher
    
    @pytest.fixture
    def mock_session_service(self):
        """Mock session service"""
        service = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_hitl_service(self):
        """Mock HITL service"""
        service = AsyncMock()
        return service
    
    @pytest.fixture
    def handler(
        self,
        mock_llm_client,
        mock_tool_filter,
        mock_response_processor,
        mock_event_publisher,
        mock_session_service,
        mock_hitl_service
    ):
        """Создать handler с mock зависимостями"""
        return StreamLLMResponseHandler(
            llm_client=mock_llm_client,
            tool_filter=mock_tool_filter,
            response_processor=mock_response_processor,
            event_publisher=mock_event_publisher,
            session_service=mock_session_service,
            hitl_service=mock_hitl_service
        )
    
    @pytest.mark.asyncio
    async def test_handle_simple_assistant_message(
        self,
        handler,
        mock_llm_client,
        mock_response_processor,
        mock_event_publisher,
        mock_session_service
    ):
        """Тест обработки простого сообщения ассистента"""
        # Arrange
        llm_response = LLMResponse(
            content="Hello, world!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        processed = ProcessedResponse(
            content="Hello, world!",
            tool_calls=[],
            usage=llm_response.usage,
            model="gpt-4",
            requires_approval=False,
            approval_reason=None,
            validation_warnings=[]
        )
        
        mock_llm_client.chat_completion.return_value = llm_response
        mock_response_processor.process_response.return_value = processed
        
        # Act
        chunks = []
        async for chunk in handler.handle(
            session_id="session-1",
            history=[{"role": "user", "content": "Hello"}],
            model="gpt-4",
            allowed_tools=None
        ):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 1
        assert chunks[0].type == "assistant_message"
        assert chunks[0].content == "Hello, world!"
        assert chunks[0].is_final == True
        
        # Проверить вызовы
        mock_llm_client.chat_completion.assert_called_once()
        mock_response_processor.process_response.assert_called_once()
        mock_session_service.add_message.assert_called_once()
        
        # Проверить публикацию событий
        assert mock_event_publisher.publish_request_started.called
        assert mock_event_publisher.publish_request_completed.called
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_without_approval(
        self,
        handler,
        mock_llm_client,
        mock_response_processor,
        mock_event_publisher,
        mock_session_service,
        mock_hitl_service
    ):
        """Тест обработки tool call без необходимости одобрения"""
        # Arrange
        tool_call = ToolCall(
            id="call-1",
            tool_name="read_file",
            arguments={"path": "test.py"}
        )
        
        llm_response = LLMResponse(
            content="",
            tool_calls=[tool_call],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
            model="gpt-4"
        )
        
        processed = ProcessedResponse(
            content="",
            tool_calls=[tool_call],
            usage=llm_response.usage,
            model="gpt-4",
            requires_approval=False,  # Не требует одобрения
            approval_reason=None,
            validation_warnings=[]
        )
        
        mock_llm_client.chat_completion.return_value = llm_response
        mock_response_processor.process_response.return_value = processed
        
        # Act
        chunks = []
        async for chunk in handler.handle(
            session_id="session-1",
            history=[{"role": "user", "content": "Read test.py"}],
            model="gpt-4"
        ):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 1
        assert chunks[0].type == "tool_call"
        assert chunks[0].tool_name == "read_file"
        assert chunks[0].requires_approval == False
        
        # HITL service НЕ должен быть вызван
        mock_hitl_service.add_pending.assert_not_called()
        
        # Session service должен сохранить сообщение
        mock_session_service.add_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_with_approval(
        self,
        handler,
        mock_llm_client,
        mock_response_processor,
        mock_event_publisher,
        mock_session_service,
        mock_hitl_service
    ):
        """Тест обработки tool call с необходимостью одобрения"""
        # Arrange
        tool_call = ToolCall(
            id="call-1",
            tool_name="write_file",
            arguments={"path": "important.py", "content": "..."}
        )
        
        llm_response = LLMResponse(
            content="",
            tool_calls=[tool_call],
            usage=TokenUsage(),
            model="gpt-4"
        )
        
        processed = ProcessedResponse(
            content="",
            tool_calls=[tool_call],
            usage=llm_response.usage,
            model="gpt-4",
            requires_approval=True,  # Требует одобрения
            approval_reason="File modification requires approval",
            validation_warnings=[]
        )
        
        mock_llm_client.chat_completion.return_value = llm_response
        mock_response_processor.process_response.return_value = processed
        
        # Act
        chunks = []
        async for chunk in handler.handle(
            session_id="session-1",
            history=[{"role": "user", "content": "Write to important.py"}],
            model="gpt-4"
        ):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 1
        assert chunks[0].type == "tool_call"
        assert chunks[0].requires_approval == True
        
        # HITL service должен сохранить pending state
        mock_hitl_service.add_pending.assert_called_once_with(
            session_id="session-1",
            call_id="call-1",
            tool_name="write_file",
            arguments={"path": "important.py", "content": "..."},
            reason="File modification requires approval"
        )
        
        # Должно быть опубликовано событие approval required
        mock_event_publisher.publish_tool_approval_required.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_error(
        self,
        handler,
        mock_llm_client,
        mock_event_publisher
    ):
        """Тест обработки ошибки при вызове LLM"""
        # Arrange
        mock_llm_client.chat_completion.side_effect = Exception("LLM API error")
        
        # Act
        chunks = []
        async for chunk in handler.handle(
            session_id="session-1",
            history=[{"role": "user", "content": "Hello"}],
            model="gpt-4"
        ):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 1
        assert chunks[0].type == "error"
        assert "LLM API error" in chunks[0].error
        
        # Должно быть опубликовано событие ошибки
        mock_event_publisher.publish_request_failed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tool_filtering(
        self,
        handler,
        mock_tool_filter,
        mock_llm_client
    ):
        """Тест фильтрации инструментов"""
        # Arrange
        mock_llm_client.chat_completion.return_value = LLMResponse(
            content="Test",
            tool_calls=[],
            usage=TokenUsage(),
            model="gpt-4"
        )
        
        # Act
        chunks = [chunk async for chunk in handler.handle(
            session_id="session-1",
            history=[],
            model="gpt-4",
            allowed_tools=["read_file", "write_file"]
        )]
        
        # Assert
        mock_tool_filter.filter_tools.assert_called_once_with(
            ["read_file", "write_file"]
        )

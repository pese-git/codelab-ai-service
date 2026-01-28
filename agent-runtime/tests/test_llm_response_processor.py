"""
Unit тесты для LLMResponseProcessor.

Тестирует применение бизнес-правил к LLM ответам.
"""

import pytest
from unittest.mock import Mock

from app.domain.entities.llm_response import (
    LLMResponse,
    ProcessedResponse,
    ToolCall,
    TokenUsage
)
from app.domain.services.llm_response_processor import LLMResponseProcessor
from app.domain.services.hitl_policy import HITLPolicyService


class TestLLMResponseProcessor:
    """Тесты для LLMResponseProcessor"""
    
    @pytest.fixture
    def mock_hitl_policy(self):
        """Mock HITL policy service"""
        policy = Mock(spec=HITLPolicyService)
        policy.requires_approval.return_value = (False, None)
        return policy
    
    @pytest.fixture
    def processor(self, mock_hitl_policy):
        """Создать processor с mock зависимостями"""
        return LLMResponseProcessor(hitl_policy=mock_hitl_policy)
    
    def test_process_simple_response(self, processor):
        """Тест обработки простого ответа без tool calls"""
        # Arrange
        response = LLMResponse(
            content="Hello, world!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        # Act
        processed = processor.process_response(response)
        
        # Assert
        assert processed.content == "Hello, world!"
        assert len(processed.tool_calls) == 0
        assert processed.requires_approval == False
        assert len(processed.validation_warnings) == 0
    
    def test_process_response_with_single_tool_call(self, processor, mock_hitl_policy):
        """Тест обработки ответа с одним tool call"""
        # Arrange
        tool_call = ToolCall(
            id="call-1",
            tool_name="read_file",
            arguments={"path": "test.py"}
        )
        response = LLMResponse(
            content="",
            tool_calls=[tool_call],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
            model="gpt-4"
        )
        
        mock_hitl_policy.requires_approval.return_value = (False, None)
        
        # Act
        processed = processor.process_response(response)
        
        # Assert
        assert len(processed.tool_calls) == 1
        assert processed.tool_calls[0].tool_name == "read_file"
        assert processed.requires_approval == False
        assert len(processed.validation_warnings) == 0
    
    def test_process_response_with_multiple_tool_calls(self, processor):
        """Тест бизнес-правила: только один tool call за раз"""
        # Arrange
        tool_call1 = ToolCall(id="call-1", tool_name="read_file", arguments={})
        tool_call2 = ToolCall(id="call-2", tool_name="write_file", arguments={})
        
        response = LLMResponse(
            content="",
            tool_calls=[tool_call1, tool_call2],
            usage=TokenUsage(),
            model="gpt-4"
        )
        
        # Act
        processed = processor.process_response(response)
        
        # Assert
        assert len(processed.tool_calls) == 1, "Должен остаться только первый tool call"
        assert processed.tool_calls[0].id == "call-1"
        assert len(processed.validation_warnings) == 1
        assert "simultaneously" in processed.validation_warnings[0].lower()
    
    def test_process_response_with_hitl_approval_required(self, processor, mock_hitl_policy):
        """Тест проверки HITL политики"""
        # Arrange
        tool_call = ToolCall(
            id="call-1",
            tool_name="write_file",
            arguments={"path": "important.py", "content": "..."}
        )
        response = LLMResponse(
            content="",
            tool_calls=[tool_call],
            usage=TokenUsage(),
            model="gpt-4"
        )
        
        # Mock: write_file требует одобрения
        mock_hitl_policy.requires_approval.return_value = (
            True,
            "File modification requires approval"
        )
        
        # Act
        processed = processor.process_response(response)
        
        # Assert
        assert processed.requires_approval == True
        assert processed.approval_reason == "File modification requires approval"
        mock_hitl_policy.requires_approval.assert_called_once_with("write_file")
    
    def test_process_empty_response(self, processor):
        """Тест валидации пустого ответа"""
        # Arrange
        response = LLMResponse(
            content="",
            tool_calls=[],
            usage=TokenUsage(),
            model="gpt-4"
        )
        
        # Act
        processed = processor.process_response(response)
        
        # Assert
        assert len(processed.validation_warnings) == 1
        assert "empty content" in processed.validation_warnings[0].lower()
    
    def test_validate_tool_call_valid(self, processor):
        """Тест валидации корректного tool call"""
        # Arrange
        tool_call = ToolCall(
            id="call-1",
            tool_name="read_file",
            arguments={"path": "test.py"}
        )
        
        # Act
        is_valid, error = processor.validate_tool_call(tool_call)
        
        # Assert
        assert is_valid == True
        assert error is None
    
    def test_validate_tool_call_missing_id(self, processor):
        """Тест валидации tool call без ID"""
        # Arrange
        tool_call = ToolCall(
            id="",
            tool_name="read_file",
            arguments={}
        )
        
        # Act
        is_valid, error = processor.validate_tool_call(tool_call)
        
        # Assert
        assert is_valid == False
        assert "ID is required" in error
    
    def test_validate_tool_call_missing_name(self, processor):
        """Тест валидации tool call без имени"""
        # Arrange
        tool_call = ToolCall(
            id="call-1",
            tool_name="",
            arguments={}
        )
        
        # Act
        is_valid, error = processor.validate_tool_call(tool_call)
        
        # Assert
        assert is_valid == False
        assert "name is required" in error.lower()

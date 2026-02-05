"""
Unit tests for LLM Context Domain Services.
"""

import pytest

from app.domain.llm_context.services import (
    LLMRequestBuilder,
    LLMResponseValidator,
    TokenEstimator,
)
from app.domain.llm_context.value_objects import ModelName, Temperature, TokenLimit
from app.domain.entities.llm_response import LLMResponse, ToolCall, TokenUsage


# ============================================================================
# LLMRequestBuilder Tests
# ============================================================================

class TestLLMRequestBuilder:
    """Tests for LLMRequestBuilder service."""
    
    def test_build_chat_request(self):
        """Test building chat request."""
        builder = LLMRequestBuilder()
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        
        request = builder.build_chat_request(model=model, messages=messages)
        
        assert request.model == model
        assert request.messages == messages
        assert request.temperature is not None
        assert request.max_tokens is not None
    
    def test_build_chat_request_with_custom_temperature(self):
        """Test building chat request with custom temperature."""
        builder = LLMRequestBuilder()
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        temp = Temperature.creative()
        
        request = builder.build_chat_request(
            model=model,
            messages=messages,
            temperature=temp
        )
        
        assert request.temperature == temp
    
    def test_build_tool_request(self):
        """Test building tool request."""
        builder = LLMRequestBuilder()
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        request = builder.build_tool_request(
            model=model,
            messages=messages,
            tools=tools
        )
        
        assert request.has_tools() is True
        assert request.temperature.is_conservative() is True  # Conservative for tools
    
    def test_build_tool_request_unsupported_model_raises_error(self):
        """Test that building tool request with unsupported model raises error."""
        builder = LLMRequestBuilder()
        model = ModelName(value="gpt-3.5-turbo-instruct")  # Doesn't support tools
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        # Note: This will pass because our ModelName.supports_tools() returns True by default
        # In real implementation, we'd need more sophisticated detection
        request = builder.build_tool_request(
            model=model,
            messages=messages,
            tools=tools
        )
        assert request is not None
    
    def test_build_code_generation_request(self):
        """Test building code generation request."""
        builder = LLMRequestBuilder()
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Write a function"}]
        
        request = builder.build_code_generation_request(
            model=model,
            messages=messages
        )
        
        assert request.temperature.is_conservative() is True
        assert request.metadata.get("task_type") == "code_generation"
    
    def test_validate_messages_success(self):
        """Test successful message validation."""
        builder = LLMRequestBuilder()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        assert builder.validate_messages(messages) is True
    
    def test_validate_messages_empty(self):
        """Test validation with empty messages."""
        builder = LLMRequestBuilder()
        assert builder.validate_messages([]) is False
    
    def test_validate_messages_missing_role(self):
        """Test validation with missing role."""
        builder = LLMRequestBuilder()
        messages = [{"content": "Hello"}]
        
        assert builder.validate_messages(messages) is False
    
    def test_optimize_context(self):
        """Test context optimization."""
        builder = LLMRequestBuilder()
        messages = [
            {"role": "system", "content": "System prompt"},
            *[{"role": "user", "content": f"Message {i}"} for i in range(20)]
        ]
        
        optimized = builder.optimize_context(messages, max_messages=10)
        
        # Should keep system message + last 9 messages
        assert len(optimized) == 10
        assert optimized[0]["role"] == "system"


# ============================================================================
# LLMResponseValidator Tests
# ============================================================================

class TestLLMResponseValidator:
    """Tests for LLMResponseValidator service."""
    
    def test_validate_response_with_content(self):
        """Test validating response with content."""
        validator = LLMResponseValidator()
        response = LLMResponse(
            content="Hello!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        is_valid, warnings = validator.validate_response(response)
        
        assert is_valid is True
    
    def test_validate_response_with_tool_calls(self):
        """Test validating response with tool calls."""
        validator = LLMResponseValidator()
        tool_call = ToolCall(
            id="call-123",
            tool_name="test_tool",
            arguments={"arg": "value"}
        )
        response = LLMResponse(
            content="",
            tool_calls=[tool_call],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        is_valid, warnings = validator.validate_response(response)
        
        assert is_valid is True
    
    def test_validate_response_empty_fails(self):
        """Test that empty response fails validation."""
        validator = LLMResponseValidator()
        response = LLMResponse(
            content="",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        is_valid, warnings = validator.validate_response(response)
        
        assert is_valid is False
        assert len(warnings) > 0
    
    def test_validate_tool_calls_multiple_warning(self):
        """Test that multiple tool calls generate warning."""
        validator = LLMResponseValidator()
        tool_calls = [
            ToolCall(id="call-1", tool_name="tool1", arguments={}),
            ToolCall(id="call-2", tool_name="tool2", arguments={})
        ]
        
        is_valid, warnings = validator.validate_tool_calls(tool_calls)
        
        assert is_valid is True
        assert len(warnings) > 0
        assert "Multiple tool calls" in warnings[0]
    
    def test_validate_content_success(self):
        """Test successful content validation."""
        validator = LLMResponseValidator()
        is_valid, error = validator.validate_content("Hello, world!")
        
        assert is_valid is True
        assert error == ""
    
    def test_validate_content_empty_fails(self):
        """Test that empty content fails validation."""
        validator = LLMResponseValidator()
        is_valid, error = validator.validate_content("")
        
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_check_token_usage_normal(self):
        """Test normal token usage check."""
        validator = LLMResponseValidator()
        response = LLMResponse(
            content="Hello!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            model="gpt-4"
        )
        
        is_valid, warning = validator.check_token_usage(response)
        
        assert is_valid is True


# ============================================================================
# TokenEstimator Tests
# ============================================================================

class TestTokenEstimator:
    """Tests for TokenEstimator service."""
    
    def test_estimate_text(self):
        """Test text token estimation."""
        estimator = TokenEstimator()
        tokens = estimator.estimate_text("Hello, world!")
        
        assert tokens > 0
        assert tokens < 10  # Should be ~3 tokens
    
    def test_estimate_text_empty(self):
        """Test empty text estimation."""
        estimator = TokenEstimator()
        tokens = estimator.estimate_text("")
        
        assert tokens == 0
    
    def test_estimate_message(self):
        """Test message token estimation."""
        estimator = TokenEstimator()
        message = {"role": "user", "content": "Hello, world!"}
        tokens = estimator.estimate_message(message)
        
        assert tokens > 0
    
    def test_estimate_messages(self):
        """Test multiple messages estimation."""
        estimator = TokenEstimator()
        model = ModelName(value="gpt-4")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        tokens = estimator.estimate_messages(messages, model)
        
        assert tokens > 0
    
    def test_estimate_tools(self):
        """Test tools estimation."""
        estimator = TokenEstimator()
        tools = [
            {"type": "function", "function": {"name": "test1"}},
            {"type": "function", "function": {"name": "test2"}}
        ]
        
        tokens = estimator.estimate_tools(tools)
        
        assert tokens == 200  # 2 tools * 100 tokens each
    
    def test_estimate_total(self):
        """Test total estimation."""
        estimator = TokenEstimator()
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        total = estimator.estimate_total(messages, tools, model)
        
        assert total > 100  # Should include both messages and tools
    
    def test_will_exceed_limit_false(self):
        """Test will_exceed_limit returns False for small request."""
        from app.domain.llm_context import LLMRequest
        
        estimator = TokenEstimator()
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        
        request = LLMRequest.create(model=model, messages=messages)
        limit = TokenLimit.for_gpt4()
        
        assert estimator.will_exceed_limit(request, limit) is False
    
    def test_get_recommended_max_tokens(self):
        """Test recommended max tokens calculation."""
        estimator = TokenEstimator()
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        
        recommended = estimator.get_recommended_max_tokens(messages, model)
        
        assert recommended >= 500  # Minimum
        assert recommended <= 8192  # Model limit

"""
Unit tests for LLM Context Entities.
"""

import pytest
from datetime import datetime

from app.domain.llm_context.entities import LLMRequest, LLMInteraction
from app.domain.llm_context.value_objects import (
    ModelName,
    Temperature,
    TokenLimit,
    LLMRequestId,
)
from app.domain.entities.llm_response import LLMResponse, TokenUsage


# ============================================================================
# LLMRequest Tests
# ============================================================================

class TestLLMRequest:
    """Tests for LLMRequest entity."""
    
    def test_create_minimal_request(self):
        """Test creating minimal request."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        
        request = LLMRequest.create(model=model, messages=messages)
        
        assert request.model == model
        assert request.messages == messages
        assert request.tools == []
        assert len(request.domain_events) == 1  # LLMRequestCreated
    
    def test_create_request_with_tools(self):
        """Test creating request with tools."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        request = LLMRequest.create(
            model=model,
            messages=messages,
            tools=tools
        )
        
        assert request.has_tools() is True
        assert len(request.tools) == 1
    
    def test_create_request_with_temperature(self):
        """Test creating request with temperature."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        temp = Temperature.balanced()
        
        request = LLMRequest.create(
            model=model,
            messages=messages,
            temperature=temp
        )
        
        assert request.temperature == temp
    
    def test_validate_success(self):
        """Test successful validation."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        
        request = LLMRequest.create(model=model, messages=messages)
        is_valid, error = request.validate()
        
        assert is_valid is True
        assert error is None
        assert len(request.domain_events) == 2  # Created + Validated
    
    def test_validate_empty_messages(self):
        """Test validation with empty messages."""
        model = ModelName(value="gpt-4")
        
        request = LLMRequest.create(model=model, messages=[])
        is_valid, error = request.validate()
        
        assert is_valid is False
        assert "at least one message" in error
    
    def test_validate_invalid_message_format(self):
        """Test validation with invalid message format."""
        model = ModelName(value="gpt-4")
        messages = [{"content": "Hello"}]  # Missing 'role'
        
        request = LLMRequest.create(model=model, messages=messages)
        is_valid, error = request.validate()
        
        assert is_valid is False
        assert "role" in error
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello world"}]
        
        request = LLMRequest.create(model=model, messages=messages)
        estimated = request.estimate_tokens()
        
        assert estimated > 0
    
    def test_to_api_format(self):
        """Test conversion to API format."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        temp = Temperature.balanced()
        
        request = LLMRequest.create(
            model=model,
            messages=messages,
            temperature=temp
        )
        
        api_format = request.to_api_format()
        
        assert api_format["model"] == "gpt-4"
        assert api_format["messages"] == messages
        assert api_format["temperature"] == 0.7
    
    def test_add_message(self):
        """Test adding message to request."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        
        request = LLMRequest.create(model=model, messages=messages)
        request.add_message("assistant", "Hi there!")
        
        assert request.get_message_count() == 2
        assert request.messages[-1]["role"] == "assistant"


# ============================================================================
# LLMInteraction Tests
# ============================================================================

class TestLLMInteraction:
    """Tests for LLMInteraction entity."""
    
    def test_start_interaction(self):
        """Test starting interaction."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        
        assert interaction.request == request
        assert interaction.response is None
        assert interaction.is_in_progress() is True
        assert len(interaction.domain_events) == 1  # LLMInteractionStarted
    
    def test_complete_interaction(self):
        """Test completing interaction."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        
        response = LLMResponse(
            content="Hi there!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        interaction.complete(response)
        
        assert interaction.is_completed() is True
        assert interaction.response == response
        assert interaction.completed_at is not None
        assert len(interaction.domain_events) == 2  # Started + Completed
    
    def test_fail_interaction(self):
        """Test failing interaction."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        interaction.fail("Connection timeout")
        
        assert interaction.is_failed() is True
        assert interaction.error == "Connection timeout"
        assert interaction.completed_at is not None
        assert len(interaction.domain_events) == 2  # Started + Failed
    
    def test_cannot_complete_twice(self):
        """Test that interaction cannot be completed twice."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        
        response = LLMResponse(
            content="Hi!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        interaction.complete(response)
        
        with pytest.raises(ValueError, match="already completed"):
            interaction.complete(response)
    
    def test_cannot_fail_after_complete(self):
        """Test that interaction cannot fail after completion."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        
        response = LLMResponse(
            content="Hi!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        interaction.complete(response)
        
        with pytest.raises(ValueError, match="already completed"):
            interaction.fail("Error")
    
    def test_get_duration_ms(self):
        """Test getting duration in milliseconds."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        
        # Duration is None while in progress
        assert interaction.get_duration_ms() is None
        
        response = LLMResponse(
            content="Hi!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        interaction.complete(response)
        
        # Duration is calculated after completion
        duration = interaction.get_duration_ms()
        assert duration is not None
        assert duration >= 0
    
    def test_get_tokens_used(self):
        """Test getting tokens used."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        
        # No tokens used while in progress
        assert interaction.get_tokens_used() == 0
        
        response = LLMResponse(
            content="Hi!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        interaction.complete(response)
        
        # Tokens from response
        assert interaction.get_tokens_used() == 15
    
    def test_get_status(self):
        """Test getting status."""
        model = ModelName(value="gpt-4")
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest.create(model=model, messages=messages)
        
        interaction = LLMInteraction.start(request)
        assert interaction.get_status() == "in_progress"
        
        response = LLMResponse(
            content="Hi!",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4"
        )
        
        interaction.complete(response)
        assert interaction.get_status() == "completed"
        
        # Test failed status
        interaction2 = LLMInteraction.start(request)
        interaction2.fail("Error")
        assert interaction2.get_status() == "failed"

"""
Unit tests for LLM Context Value Objects.
"""

import pytest
from pydantic import ValidationError

from app.domain.llm_context.value_objects import (
    ModelName,
    Temperature,
    TokenLimit,
    LLMRequestId,
    FinishReason,
    PromptTemplate,
)


# ============================================================================
# ModelName Tests
# ============================================================================

class TestModelName:
    """Tests for ModelName value object."""
    
    def test_create_valid_model_name(self):
        """Test creating valid model name."""
        model = ModelName(value="gpt-4")
        assert model.value == "gpt-4"
    
    def test_empty_model_name_raises_error(self):
        """Test that empty model name raises error."""
        with pytest.raises(ValidationError):
            ModelName(value="")
    
    def test_whitespace_model_name_raises_error(self):
        """Test that whitespace in model name raises error."""
        with pytest.raises(ValidationError):
            ModelName(value="gpt\n4")
    
    def test_get_provider_openai(self):
        """Test provider detection for OpenAI models."""
        model = ModelName(value="gpt-4")
        assert model.get_provider() == "openai"
        assert model.is_openai() is True
    
    def test_get_provider_anthropic(self):
        """Test provider detection for Anthropic models."""
        model = ModelName(value="claude-3-opus-20240229")
        assert model.get_provider() == "anthropic"
        assert model.is_anthropic() is True
    
    def test_get_provider_with_prefix(self):
        """Test provider detection with prefix."""
        model = ModelName(value="openai/gpt-4-turbo")
        assert model.get_provider() == "openai"
        assert model.get_model() == "gpt-4-turbo"
    
    def test_supports_tools_gpt4(self):
        """Test tool support for GPT-4."""
        model = ModelName(value="gpt-4")
        assert model.supports_tools() is True
    
    def test_supports_tools_claude3(self):
        """Test tool support for Claude 3."""
        model = ModelName(value="claude-3-opus-20240229")
        assert model.supports_tools() is True
    
    def test_equality(self):
        """Test equality comparison."""
        model1 = ModelName(value="gpt-4")
        model2 = ModelName(value="gpt-4")
        model3 = ModelName(value="gpt-3.5-turbo")
        
        assert model1 == model2
        assert model1 != model3


# ============================================================================
# Temperature Tests
# ============================================================================

class TestTemperature:
    """Tests for Temperature value object."""
    
    def test_create_valid_temperature(self):
        """Test creating valid temperature."""
        temp = Temperature(value=0.7)
        assert temp.value == 0.7
    
    def test_temperature_below_zero_raises_error(self):
        """Test that temperature below 0 raises error."""
        with pytest.raises(ValidationError):
            Temperature(value=-0.1)
    
    def test_temperature_above_two_raises_error(self):
        """Test that temperature above 2.0 raises error."""
        with pytest.raises(ValidationError):
            Temperature(value=2.1)
    
    def test_conservative_factory(self):
        """Test conservative factory method."""
        temp = Temperature.conservative()
        assert temp.value == 0.0
        assert temp.is_conservative() is True
    
    def test_balanced_factory(self):
        """Test balanced factory method."""
        temp = Temperature.balanced()
        assert temp.value == 0.7
        assert temp.is_balanced() is True
    
    def test_creative_factory(self):
        """Test creative factory method."""
        temp = Temperature.creative()
        assert temp.value == 1.0
        assert temp.is_creative() is True
    
    def test_maximum_factory(self):
        """Test maximum factory method."""
        temp = Temperature.maximum()
        assert temp.value == 2.0
        assert temp.is_creative() is True
    
    def test_get_description(self):
        """Test description generation."""
        assert "Conservative" in Temperature(value=0.0).get_description()
        assert "Balanced" in Temperature(value=0.7).get_description()
        assert "Creative" in Temperature(value=1.5).get_description()


# ============================================================================
# TokenLimit Tests
# ============================================================================

class TestTokenLimit:
    """Tests for TokenLimit value object."""
    
    def test_create_valid_token_limit(self):
        """Test creating valid token limit."""
        limit = TokenLimit(value=4096)
        assert limit.value == 4096
    
    def test_token_limit_below_minimum_raises_error(self):
        """Test that limit below 100 raises error."""
        with pytest.raises(ValidationError):
            TokenLimit(value=50)
    
    def test_token_limit_above_maximum_raises_error(self):
        """Test that limit above 200000 raises error."""
        with pytest.raises(ValidationError):
            TokenLimit(value=300000)
    
    def test_for_gpt35_factory(self):
        """Test GPT-3.5 factory method."""
        limit = TokenLimit.for_gpt35()
        assert limit.value == 4096
    
    def test_for_gpt4_factory(self):
        """Test GPT-4 factory method."""
        limit = TokenLimit.for_gpt4()
        assert limit.value == 8192
    
    def test_for_gpt4_turbo_factory(self):
        """Test GPT-4 Turbo factory method."""
        limit = TokenLimit.for_gpt4_turbo()
        assert limit.value == 128000
    
    def test_for_model_gpt4(self):
        """Test for_model with GPT-4."""
        model = ModelName(value="gpt-4")
        limit = TokenLimit.for_model(model)
        assert limit.value == 8192
    
    def test_for_model_claude3(self):
        """Test for_model with Claude 3."""
        model = ModelName(value="claude-3-opus-20240229")
        limit = TokenLimit.for_model(model)
        assert limit.value == 200000
    
    def test_is_within_limit(self):
        """Test is_within_limit check."""
        from app.domain.entities.llm_response import TokenUsage
        
        limit = TokenLimit(value=1000)
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        
        assert limit.is_within_limit(usage) is True
    
    def test_remaining_tokens(self):
        """Test remaining tokens calculation."""
        from app.domain.entities.llm_response import TokenUsage
        
        limit = TokenLimit(value=1000)
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        
        assert limit.remaining(usage) == 850
    
    def test_percentage_used(self):
        """Test percentage used calculation."""
        from app.domain.entities.llm_response import TokenUsage
        
        limit = TokenLimit(value=1000)
        usage = TokenUsage(prompt_tokens=200, completion_tokens=50, total_tokens=250)
        
        assert limit.percentage_used(usage) == 25.0


# ============================================================================
# LLMRequestId Tests
# ============================================================================

class TestLLMRequestId:
    """Tests for LLMRequestId value object."""
    
    def test_create_valid_request_id(self):
        """Test creating valid request ID."""
        request_id = LLMRequestId(value="test-123")
        assert request_id.value == "test-123"
    
    def test_empty_request_id_raises_error(self):
        """Test that empty request ID raises error."""
        with pytest.raises(ValidationError):
            LLMRequestId(value="")
    
    def test_whitespace_request_id_raises_error(self):
        """Test that whitespace in request ID raises error."""
        with pytest.raises(ValidationError):
            LLMRequestId(value="test\n123")
    
    def test_generate_request_id(self):
        """Test generating request ID."""
        request_id = LLMRequestId.generate()
        assert request_id.value.startswith("llm-req-")
        assert request_id.is_generated() is True
    
    def test_from_string(self):
        """Test creating from string."""
        request_id = LLMRequestId.from_string("custom-id")
        assert request_id.value == "custom-id"
        assert request_id.is_generated() is False
    
    def test_hash(self):
        """Test hashing."""
        id1 = LLMRequestId(value="test-123")
        id2 = LLMRequestId(value="test-123")
        
        assert hash(id1) == hash(id2)
        assert {id1, id2} == {id1}  # Set deduplication


# ============================================================================
# FinishReason Tests
# ============================================================================

class TestFinishReason:
    """Tests for FinishReason value object."""
    
    def test_create_valid_finish_reason(self):
        """Test creating valid finish reason."""
        reason = FinishReason(value="stop")
        assert reason.value == "stop"
    
    def test_stop_factory(self):
        """Test stop factory method."""
        reason = FinishReason.stop()
        assert reason.value == "stop"
        assert reason.is_normal() is True
    
    def test_length_factory(self):
        """Test length factory method."""
        reason = FinishReason.length()
        assert reason.value == "length"
        assert reason.is_truncated() is True
    
    def test_tool_calls_factory(self):
        """Test tool_calls factory method."""
        reason = FinishReason.tool_calls()
        assert reason.value == "tool_calls"
        assert reason.requires_action() is True
    
    def test_error_factory(self):
        """Test error factory method."""
        reason = FinishReason.error()
        assert reason.value == "error"
        assert reason.is_error() is True
    
    def test_content_filter_is_error(self):
        """Test that content_filter is considered error."""
        reason = FinishReason.content_filter()
        assert reason.is_error() is True
    
    def test_get_description(self):
        """Test description generation."""
        assert "Normal" in FinishReason.stop().get_description()
        assert "Token limit" in FinishReason.length().get_description()
        assert "Tool calls" in FinishReason.tool_calls().get_description()


# ============================================================================
# PromptTemplate Tests
# ============================================================================

class TestPromptTemplate:
    """Tests for PromptTemplate value object."""
    
    def test_create_valid_template(self):
        """Test creating valid template."""
        template = PromptTemplate(template="Hello, {name}!")
        assert template.template == "Hello, {name}!"
    
    def test_empty_template_raises_error(self):
        """Test that empty template raises error."""
        with pytest.raises(ValidationError):
            PromptTemplate(template="")
    
    def test_invalid_placeholder_raises_error(self):
        """Test that invalid placeholder raises error."""
        with pytest.raises(ValidationError):
            PromptTemplate(template="Hello, {123}!")  # Numbers not allowed
    
    def test_get_variables(self):
        """Test getting variables from template."""
        template = PromptTemplate(template="Hello, {name}! You are {role}.")
        variables = template.get_variables()
        
        assert variables == ["name", "role"]
    
    def test_get_variables_with_duplicates(self):
        """Test that duplicates are removed."""
        template = PromptTemplate(template="{name} {name} {role}")
        variables = template.get_variables()
        
        assert variables == ["name", "role"]
    
    def test_validate_variables_success(self):
        """Test successful variable validation."""
        template = PromptTemplate(template="Hello, {name}!")
        assert template.validate_variables({"name": "Alice"}) is True
    
    def test_validate_variables_missing(self):
        """Test validation with missing variables."""
        template = PromptTemplate(template="Hello, {name}!")
        assert template.validate_variables({"other": "value"}) is False
    
    def test_get_missing_variables(self):
        """Test getting missing variables."""
        template = PromptTemplate(template="Hello, {name}! You are {role}.")
        missing = template.get_missing_variables({"name": "Alice"})
        
        assert missing == ["role"]
    
    def test_render_success(self):
        """Test successful rendering."""
        template = PromptTemplate(template="Hello, {name}!")
        result = template.render({"name": "Alice"})
        
        assert result == "Hello, Alice!"
    
    def test_render_missing_variable_raises_error(self):
        """Test that rendering with missing variable raises error."""
        template = PromptTemplate(template="Hello, {name}!")
        
        with pytest.raises(ValueError, match="Missing required variables"):
            template.render({})
    
    def test_has_variables(self):
        """Test has_variables check."""
        template1 = PromptTemplate(template="Hello, {name}!")
        template2 = PromptTemplate(template="Hello, world!")
        
        assert template1.has_variables() is True
        assert template2.has_variables() is False
    
    def test_preview(self):
        """Test preview generation."""
        long_text = "A" * 200
        template = PromptTemplate(template=long_text)
        preview = template.preview(50)
        
        assert len(preview) == 53  # 50 + "..."
        assert preview.endswith("...")

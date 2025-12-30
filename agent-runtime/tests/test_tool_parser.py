"""
Unit tests for ToolParser.
"""
import pytest
import json

from app.services.tool_parser import (
    OpenAIToolCallParser,
    parse_tool_calls
)
from app.models.schemas import ToolCall


class TestOpenAIToolCallParser:
    """Tests for OpenAI tool call parser"""
    
    def test_parse_tool_calls_from_metadata(self):
        """Test parsing tool calls from metadata (OpenAI tools API)"""
        parser = OpenAIToolCallParser()
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "list_files",
                        "arguments": '{"path": "."}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_123"
        assert tool_calls[0].tool_name == "list_files"
        assert tool_calls[0].arguments == {"path": "."}
    
    def test_parse_multiple_tool_calls(self):
        """Test parsing multiple tool calls"""
        parser = OpenAIToolCallParser()
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "tool1",
                        "arguments": '{"arg1": "value1"}'
                    }
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "tool2",
                        "arguments": '{"arg2": "value2"}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        assert len(tool_calls) == 2
        assert tool_calls[0].tool_name == "tool1"
        assert tool_calls[1].tool_name == "tool2"
    
    def test_parse_function_call_legacy(self):
        """Test parsing legacy function_call format"""
        parser = OpenAIToolCallParser()
        content = ""
        metadata = {
            "function_call": {
                "name": "get_weather",
                "arguments": '{"location": "London"}'
            }
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "get_weather"
        assert tool_calls[0].arguments == {"location": "London"}
    
    def test_parse_empty_metadata(self):
        """Test parsing with empty metadata"""
        parser = OpenAIToolCallParser()
        content = "Just text"
        metadata = {}
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        assert len(tool_calls) == 0
        assert remaining == "Just text"
    
    def test_parse_no_metadata(self):
        """Test parsing with no metadata"""
        parser = OpenAIToolCallParser()
        content = "Just text"
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 0
        assert remaining == "Just text"
    
    def test_parse_invalid_json_arguments(self):
        """Test parsing with invalid JSON in arguments"""
        parser = OpenAIToolCallParser()
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "tool",
                        "arguments": "not valid json"
                    }
                }
            ]
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        # Should still create tool call with empty arguments
        assert len(tool_calls) == 1
        assert tool_calls[0].arguments == {}
    
    def test_parse_missing_tool_call_id(self):
        """Test parsing tool call without id (should generate fallback)"""
        parser = OpenAIToolCallParser()
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "tool",
                        "arguments": '{}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        # Should create tool call with fallback id
        assert len(tool_calls) == 1
        assert tool_calls[0].id.startswith("tc_fallback_")
    
    def test_parse_empty_tool_name_skipped(self):
        """Test that tool calls with empty name are skipped"""
        parser = OpenAIToolCallParser()
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "",
                        "arguments": '{}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        # Should not create tool call with empty name
        assert len(tool_calls) == 0
    
    def test_parse_list_content_without_tool_calls(self):
        """Test parsing list content without tool calls"""
        parser = OpenAIToolCallParser()
        content = [{"content": "Response text"}]
        metadata = {}
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        assert len(tool_calls) == 0
        assert remaining == "Response text"


class TestParseToolCallsFunction:
    """Tests for the convenience parse_tool_calls function"""
    
    def test_parse_tool_calls_function(self):
        """Test the global parse_tool_calls function"""
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "tool",
                        "arguments": '{"arg": "value"}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parse_tool_calls(content, metadata)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "tool"
        assert tool_calls[0].arguments == {"arg": "value"}
    
    def test_parse_tool_calls_returns_tuple(self):
        """Test that parse_tool_calls returns tuple"""
        result = parse_tool_calls("", None)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
    
    def test_parse_tool_calls_with_openai_format(self):
        """Test parsing with OpenAI format"""
        content = "Text content"
        metadata = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "openai_tool",
                        "arguments": '{}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parse_tool_calls(content, metadata)
        
        # Should find OpenAI format tool
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "openai_tool"


class TestToolCallModel:
    """Tests for ToolCall model"""
    
    def test_tool_call_construction(self):
        """Test ToolCall model construction"""
        tool_call = ToolCall.model_construct(
            id="call_123",
            tool_name="test_tool",
            arguments={"arg": "value"}
        )
        
        assert tool_call.id == "call_123"
        assert tool_call.tool_name == "test_tool"
        assert tool_call.arguments == {"arg": "value"}
    
    def test_tool_call_with_empty_arguments(self):
        """Test ToolCall with empty arguments"""
        tool_call = ToolCall.model_construct(
            id="call_123",
            tool_name="test_tool",
            arguments={}
        )
        
        assert tool_call.arguments == {}
    
    def test_tool_call_serialization(self):
        """Test ToolCall serialization"""
        tool_call = ToolCall.model_construct(
            id="call_123",
            tool_name="test_tool",
            arguments={"arg": "value"}
        )
        
        data = tool_call.model_dump()
        
        assert data["id"] == "call_123"
        assert data["tool_name"] == "test_tool"
        assert data["arguments"] == {"arg": "value"}

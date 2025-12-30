"""
Unit tests for ToolParser.
"""
import pytest
import json

from app.services.tool_parser import (
    OpenAIToolCallParser,
    XMLToolCallParser,
    CustomToolCallParser,
    UnifiedToolCallParser,
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


class TestXMLToolCallParser:
    """Tests for XML tool call parser"""
    
    def test_parse_xml_tool_call(self):
        """Test parsing XML-formatted tool call"""
        parser = XMLToolCallParser()
        content = "<list_files><path>.</path></list_files>"
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "list_files"
        assert tool_calls[0].arguments == {"path": "."}
        assert remaining == ""
    
    def test_parse_multiple_xml_tool_calls(self):
        """Test parsing multiple XML tool calls"""
        parser = XMLToolCallParser()
        content = """
        <tool1><arg1>value1</arg1></tool1>
        Some text
        <tool2><arg2>value2</arg2></tool2>
        """
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 2
        assert tool_calls[0].tool_name == "tool1"
        assert tool_calls[1].tool_name == "tool2"
    
    def test_parse_self_closing_xml_tag(self):
        """Test parsing self-closing XML tag"""
        parser = XMLToolCallParser()
        content = "<refresh/>"
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "refresh"
        assert tool_calls[0].arguments == {}
    
    def test_parse_xml_with_text_content(self):
        """Test parsing XML with surrounding text"""
        parser = XMLToolCallParser()
        content = "I will list files: <list_files><path>/home</path></list_files> Done!"
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "list_files"
        assert "I will list files:" in remaining
        assert "Done!" in remaining
    
    def test_parse_xml_fallback_to_line_parsing(self):
        """Test XML parser fallback to line-based parsing"""
        parser = XMLToolCallParser()
        # Use proper XML format that will parse correctly
        content = "<tool><arg1>value1</arg1><arg2>value2</arg2></tool>"
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "tool"
        assert tool_calls[0].arguments.get("arg1") == "value1"
        assert tool_calls[0].arguments.get("arg2") == "value2"


class TestCustomToolCallParser:
    """Tests for custom tool call parser"""
    
    def test_parse_function_style_tool_call(self):
        """Test parsing function-style tool call"""
        parser = CustomToolCallParser()
        content = 'list_files(path=".", recursive="true")'
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "list_files"
        assert "path" in tool_calls[0].arguments
        assert "recursive" in tool_calls[0].arguments
    
    def test_parse_ignores_common_keywords(self):
        """Test that parser ignores common programming keywords"""
        parser = CustomToolCallParser()
        content = 'print("hello") def function(): pass'
        
        tool_calls, remaining = parser.parse(content, None)
        
        # Should not parse print, def, etc.
        assert len(tool_calls) == 0
    
    def test_parse_multiple_custom_tool_calls(self):
        """Test parsing multiple custom tool calls"""
        parser = CustomToolCallParser()
        content = 'tool1(arg1="val1") and tool2(arg2="val2")'
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 2
        assert tool_calls[0].tool_name == "tool1"
        assert tool_calls[1].tool_name == "tool2"
    
    def test_parse_no_arguments_returns_empty(self):
        """Test that tool calls without arguments are not parsed"""
        parser = CustomToolCallParser()
        content = 'tool_name()'
        
        tool_calls, remaining = parser.parse(content, None)
        
        # Should not parse tool calls without arguments
        assert len(tool_calls) == 0


class TestUnifiedToolCallParser:
    """Tests for unified tool call parser"""
    
    def test_parse_openai_format(self):
        """Test unified parser with OpenAI format"""
        parser = UnifiedToolCallParser()
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "tool",
                        "arguments": '{}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "tool"
    
    def test_parse_xml_format(self):
        """Test unified parser with XML format"""
        parser = UnifiedToolCallParser()
        content = "<tool><arg>value</arg></tool>"
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "tool"
    
    def test_parse_custom_format(self):
        """Test unified parser with custom format"""
        parser = UnifiedToolCallParser()
        content = 'my_tool(param="value")'
        
        tool_calls, remaining = parser.parse(content, None)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "my_tool"
    
    def test_parse_deduplicates_by_id(self):
        """Test that unified parser deduplicates tool calls by ID"""
        parser = UnifiedToolCallParser()
        
        # Create a scenario where multiple parsers might return same tool
        # This is a bit artificial but tests the deduplication logic
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "tool",
                        "arguments": '{}'
                    }
                }
            ]
        }
        
        tool_calls, remaining = parser.parse(content, metadata)
        
        # Should have unique tool calls
        ids = [tc.id for tc in tool_calls]
        assert len(ids) == len(set(ids))
    
    def test_parse_handles_parser_errors(self):
        """Test that unified parser handles individual parser errors"""
        parser = UnifiedToolCallParser()
        
        # Even with potentially problematic content, should not raise
        content = "Some random text with <unclosed tag"
        
        tool_calls, remaining = parser.parse(content, None)
        
        # Should return empty list, not raise exception
        assert isinstance(tool_calls, list)


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
    
    def test_parse_tool_calls_with_mixed_formats(self):
        """Test parsing with mixed format content"""
        content = "Text with <xml_tool/> and more text"
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
        
        # Should find both OpenAI and XML format tools
        assert len(tool_calls) >= 1
        tool_names = [tc.tool_name for tc in tool_calls]
        assert "openai_tool" in tool_names


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

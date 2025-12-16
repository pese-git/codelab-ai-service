"""
Tool call parser for extracting tool calls from LLM responses.
Supports multiple formats: OpenAI native, XML, and custom formats.
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET

from app.models.schemas import ToolCall

logger = logging.getLogger("agent-runtime")


class ToolCallParser(ABC):
    """Abstract base class for tool call parsers"""
    
    @abstractmethod
    def parse(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[List[ToolCall], str]:
        """
        Parse tool calls from content and metadata.
        
        Args:
            content: The text content from LLM
            metadata: Optional metadata from LLM response
            
        Returns:
            Tuple of (list of ToolCall objects, remaining content after extraction)
        """
        pass


class OpenAIToolCallParser(ToolCallParser):
    """Parser for OpenAI native tool call format (legacy and modern tools)"""
    def parse(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[List[ToolCall], str]:
        tool_calls = []
        # Новый OpenAI tools API — tool_calls массив
        if metadata and "tool_calls" in metadata and metadata["tool_calls"]:
            for tc in metadata["tool_calls"]:
                func = tc.get("function") if isinstance(tc, dict) else getattr(tc, "function", None)
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                tool_name = None
                arguments = {}
                if func:
                    tool_name = func.get("name") if isinstance(func, dict) else getattr(func, "name", None)
                    args_str = func.get("arguments") if isinstance(func, dict) else getattr(func, "arguments", "")
                    try:
                        arguments = json.loads(args_str) if args_str else {}
                    except Exception:
                        arguments = {}
                if not tool_name:
                    tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                logger.debug(f"Parsing tool_call: tc={tc}, func={func}, tool_name={tool_name}, args={arguments}")
                # НЕ добавлять ToolCall если tool_name пустой!
                if tool_name:
                    tool_calls.append(
                        ToolCall(
                            id=tc_id or f"tc_{len(tool_calls)}",
                            tool_name=tool_name,
                            arguments=arguments or {},
                        )
                    )
        # Старый OpenAI function_call (legacy)
        if metadata and "function_call" in metadata:
            try:
                fc = metadata["function_call"]
                id = f"call_func_{len(tool_calls)}"
                tool_name=fc.get("name", "") if isinstance(fc, dict) else getattr(fc, "name", "")
                arguments=json.loads(fc.get("arguments", "{}")) if isinstance(fc, dict) else json.loads(getattr(fc, "arguments", "{}"))
                # НЕ добавлять ToolCall если tool_name пустой
                if tool_name:
                    tool_call = ToolCall(
                        id=id,
                        tool_name=tool_name,
                        arguments=arguments
                    )
                    logger.debug(f"Parsing tool_call: tc={id}, func={fc}, tool_name={tool_name}, args={arguments}")
                    tool_calls.append(tool_call)
            except Exception as e:
                logger.warning(f"Failed to parse OpenAI function call: {e}")
        # Исправление: если content это список, но в нем нет tool_call — вернуть текст без ToolCall!
        if isinstance(content, list):
            for item in content:
                if (
                    isinstance(item, dict) and
                    (
                        ("tool_calls" in item and item["tool_calls"]) or
                        ("function_call" in item and item["function_call"])
                    )
                ):
                    pass # будем парсить как обычно
            if not tool_calls:
                first_content = content[0].get("content", "") if content and isinstance(content[0], dict) else ""
                return [], first_content
        return tool_calls, content


class XMLToolCallParser(ToolCallParser):
    """Parser for XML-formatted tool calls (Claude/Anthropic style)"""
    
    def parse(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[List[ToolCall], str]:
        tool_calls = []
        remaining_content = content
        
        # Find all XML-style tool calls
        # Pattern matches <tool_name>...</tool_name> or <tool_name/>
        pattern = r'<(\w+)>(.*?)</\1>|<(\w+)/>'
        matches = list(re.finditer(pattern, content, re.DOTALL))
        
        for match in matches:
            tool_name = match.group(1) or match.group(3)
            tool_content = match.group(2) if match.group(1) else ""
            
            # Parse arguments from tool content
            arguments = {}
            if tool_content:
                # Try to parse as XML first
                try:
                    root = ET.fromstring(f"<root>{tool_content}</root>")
                    for child in root:
                        arguments[child.tag] = child.text or ""
                except:
                    # Fallback to line-based parsing
                    for line in tool_content.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            arguments[key.strip()] = value.strip()
            
            tool_call = ToolCall(
                id=f"call_xml_{len(tool_calls)}",
                tool_name=tool_name,
                arguments=arguments
            )
            tool_calls.append(tool_call)
            
            # Remove the tool call from content
            remaining_content = remaining_content.replace(match.group(0), "", 1)
        
        return tool_calls, remaining_content.strip()


class CustomToolCallParser(ToolCallParser):
    """Parser for custom tool call formats"""
    
    def parse(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[List[ToolCall], str]:
        tool_calls = []
        remaining_content = content
        
        # Pattern for function-like syntax: tool_name(arg1="value1", arg2="value2")
        pattern = r'(\w+)\((.*?)\)'
        matches = list(re.finditer(pattern, content))
        
        for match in matches:
            tool_name = match.group(1)
            args_str = match.group(2)
            
            # Skip if this looks like regular function syntax in code
            if tool_name in ['print', 'def', 'class', 'if', 'for', 'while']:
                continue
            
            arguments = {}
            # Parse arguments
            arg_pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']|(\w+)\s*=\s*([^,\)]+)'
            for arg_match in re.finditer(arg_pattern, args_str):
                key = arg_match.group(1) or arg_match.group(3)
                value = arg_match.group(2) or arg_match.group(4)
                arguments[key] = value.strip()
            
            if arguments:  # Only add if we found valid arguments
                tool_call = ToolCall(
                    id=f"call_custom_{len(tool_calls)}",
                    tool_name=tool_name,
                    arguments=arguments
                )
                tool_calls.append(tool_call)
                remaining_content = remaining_content.replace(match.group(0), "", 1)
        
        return tool_calls, remaining_content.strip()


class UnifiedToolCallParser:
    """Unified parser that tries multiple formats"""
    
    def __init__(self):
        self.parsers = [
            OpenAIToolCallParser(),
            XMLToolCallParser(),
            CustomToolCallParser()
        ]
    
    def parse(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[List[ToolCall], str]:
        """
        Parse tool calls using all available parsers.
        
        Returns combined results from all parsers.
        """
        all_tool_calls = []
        remaining_content = content
        
        for parser in self.parsers:
            try:
                tool_calls, new_content = parser.parse(remaining_content, metadata)
                if tool_calls:
                    all_tool_calls.extend(tool_calls)
                    remaining_content = new_content
                    logger.debug(f"Parser {parser.__class__.__name__} found {len(tool_calls)} tool calls")
            except Exception as e:
                logger.error(f"Parser {parser.__class__.__name__} failed: {e}")
        
        # Deduplicate tool calls by ID
        seen_ids = set()
        unique_tool_calls = []
        for tc in all_tool_calls:
            if tc.id not in seen_ids:
                seen_ids.add(tc.id)
                unique_tool_calls.append(tc)
        
        return unique_tool_calls, remaining_content


# Global instance for easy access
_parser = UnifiedToolCallParser()


def parse_tool_calls(content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[List[ToolCall], str]:
    """
    Convenience function to parse tool calls from content.
    
    Args:
        content: Text content from LLM
        metadata: Optional metadata containing tool calls in provider format
        
    Returns:
        Tuple of (list of ToolCall objects, remaining content)
    """
    return _parser.parse(content, metadata)

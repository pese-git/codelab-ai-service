"""
Tool call parser for extracting tool calls from LLM responses.

Supports multiple formats:
- OpenAI native tool calls (modern and legacy function_call)
- XML-formatted tool calls (Claude/Anthropic style)
- Custom function-like syntax
"""
import json
import logging
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.models.schemas import ToolCall

logger = logging.getLogger("agent-runtime.tool_parser")


class ToolCallParser(ABC):
    """Abstract base class for tool call parsers"""

    @abstractmethod
    def parse(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ToolCall], str]:
        """
        Parse tool calls from content and metadata.

        Args:
            content: Text content from LLM
            metadata: Optional metadata from LLM response

        Returns:
            Tuple of (list of ToolCall objects, remaining content after extraction)
        """
        pass


class OpenAIToolCallParser(ToolCallParser):
    """Parser for OpenAI native tool call format (modern tools and legacy function_call)"""

    def parse(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ToolCall], str]:
        """Parse OpenAI-style tool calls from metadata"""
        tool_calls = []
        
        # Modern OpenAI tools API - tool_calls array
        if metadata and "tool_calls" in metadata and metadata["tool_calls"]:
            for tc in metadata["tool_calls"]:
                tool_call = self._parse_tool_call_item(tc)
                if tool_call:
                    tool_calls.append(tool_call)
        
        # Legacy OpenAI function_call
        if metadata and "function_call" in metadata:
            tool_call = self._parse_function_call(metadata["function_call"])
            if tool_call:
                tool_calls.append(tool_call)
        
        # Handle list content without tool_calls
        if isinstance(content, list) and not tool_calls:
            first_content = (
                content[0].get("content", "")
                if content and isinstance(content[0], dict)
                else ""
            )
            return [], first_content
        
        return tool_calls, content

    def _parse_tool_call_item(self, tc: Any) -> Optional[ToolCall]:
        """Parse a single tool_call item"""
        # Extract function and id
        func = tc.get("function") if isinstance(tc, dict) else getattr(tc, "function", None)
        tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
        
        logger.debug(
            f"Parsing tool_call: id={tc_id}, "
            f"type={type(tc).__name__}"
        )
        
        # Extract tool name and arguments
        tool_name = None
        arguments = {}
        
        if func:
            tool_name = (
                func.get("name") if isinstance(func, dict) 
                else getattr(func, "name", None)
            )
            args_str = (
                func.get("arguments") if isinstance(func, dict)
                else getattr(func, "arguments", "")
            )
            try:
                arguments = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool arguments: {e}")
                arguments = {}
        
        if not tool_name:
            tool_name = (
                tc.get("name") if isinstance(tc, dict) 
                else getattr(tc, "name", None)
            )
        
        # CRITICAL: Validate call_id presence
        if not tc_id:
            logger.error(
                f"CRITICAL: tool_call missing 'id' field! "
                f"This will cause call_id mismatch."
            )
            # Generate fallback ID
            tc_id = f"tc_fallback_{id(tc)}"
            logger.warning(f"Using fallback call_id: {tc_id}")
        
        # Only create ToolCall if tool_name is present
        if not tool_name:
            logger.warning("Skipping tool_call with empty tool_name")
            return None
        
        logger.info(f"Parsed tool_call: id={tc_id}, tool={tool_name}")
        
        return ToolCall.model_construct(
            id=tc_id,
            tool_name=tool_name,
            arguments=arguments or {},
        )

    def _parse_function_call(self, fc: Any) -> Optional[ToolCall]:
        """Parse legacy function_call format"""
        try:
            tool_name = fc.get("name", "") if isinstance(fc, dict) else getattr(fc, "name", "")
            arguments_str = (
                fc.get("arguments", "{}") if isinstance(fc, dict)
                else getattr(fc, "arguments", "{}")
            )
            arguments = json.loads(arguments_str)
            
            if not tool_name:
                return None
            
            call_id = f"call_func_{id(fc)}"
            
            logger.info(f"Parsed legacy function_call: {tool_name}")
            
            return ToolCall.model_construct(
                id=call_id, 
                tool_name=tool_name, 
                arguments=arguments
            )
        except Exception as e:
            logger.warning(f"Failed to parse legacy function_call: {e}")
            return None


class XMLToolCallParser(ToolCallParser):
    """Parser for XML-formatted tool calls (Claude/Anthropic style)"""

    def parse(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ToolCall], str]:
        """Parse XML-style tool calls from content"""
        tool_calls = []
        remaining_content = content

        # Pattern matches <tool_name>...</tool_name> or <tool_name/>
        pattern = r"<(\w+)>(.*?)</\1>|<(\w+)/>"
        matches = list(re.finditer(pattern, content, re.DOTALL))

        for match in matches:
            tool_name = match.group(1) or match.group(3)
            tool_content = match.group(2) if match.group(1) else ""

            # Parse arguments from tool content
            arguments = self._parse_xml_arguments(tool_content)

            tool_call = ToolCall.model_construct(
                id=f"call_xml_{len(tool_calls)}", 
                tool_name=tool_name, 
                arguments=arguments
            )
            tool_calls.append(tool_call)

            # Remove the tool call from content
            remaining_content = remaining_content.replace(match.group(0), "", 1)

        return tool_calls, remaining_content.strip()

    def _parse_xml_arguments(self, tool_content: str) -> Dict[str, Any]:
        """Parse arguments from XML tool content"""
        arguments = {}
        
        if not tool_content:
            return arguments
        
        # Try to parse as XML first
        try:
            root = ET.fromstring(f"<root>{tool_content}</root>")
            for child in root:
                arguments[child.tag] = child.text or ""
        except ET.ParseError:
            # Fallback to line-based parsing
            for line in tool_content.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    arguments[key.strip()] = value.strip()
        
        return arguments


class CustomToolCallParser(ToolCallParser):
    """Parser for custom tool call formats (function-like syntax)"""

    # Common programming keywords to skip
    SKIP_KEYWORDS = {"print", "def", "class", "if", "for", "while", "return"}

    def parse(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ToolCall], str]:
        """Parse custom function-like tool calls"""
        tool_calls = []
        remaining_content = content

        # Pattern for function-like syntax: tool_name(arg1="value1", arg2="value2")
        pattern = r"(\w+)\((.*?)\)"
        matches = list(re.finditer(pattern, content))

        for match in matches:
            tool_name = match.group(1)
            args_str = match.group(2)

            # Skip common programming keywords
            if tool_name in self.SKIP_KEYWORDS:
                continue

            # Parse arguments
            arguments = self._parse_custom_arguments(args_str)

            # Only add if we found valid arguments
            if arguments:
                tool_call = ToolCall.model_construct(
                    id=f"call_custom_{len(tool_calls)}", 
                    tool_name=tool_name, 
                    arguments=arguments
                )
                tool_calls.append(tool_call)
                remaining_content = remaining_content.replace(match.group(0), "", 1)

        return tool_calls, remaining_content.strip()

    def _parse_custom_arguments(self, args_str: str) -> Dict[str, Any]:
        """Parse arguments from custom format"""
        arguments = {}
        
        # Pattern for key=value pairs
        arg_pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']|(\w+)\s*=\s*([^,\)]+)'
        
        for arg_match in re.finditer(arg_pattern, args_str):
            key = arg_match.group(1) or arg_match.group(3)
            value = arg_match.group(2) or arg_match.group(4)
            arguments[key] = value.strip()
        
        return arguments


class UnifiedToolCallParser:
    """Unified parser that tries multiple formats"""

    def __init__(self):
        self.parsers = [
            OpenAIToolCallParser(), 
            XMLToolCallParser(), 
            CustomToolCallParser()
        ]

    def parse(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ToolCall], str]:
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
                    logger.debug(
                        f"{parser.__class__.__name__} found {len(tool_calls)} tool calls"
                    )
            except Exception as e:
                logger.error(f"{parser.__class__.__name__} failed: {e}")

        # Deduplicate tool calls by ID
        seen_ids = set()
        unique_tool_calls = []
        for tc in all_tool_calls:
            if tc.id not in seen_ids:
                seen_ids.add(tc.id)
                unique_tool_calls.append(tc)

        return unique_tool_calls, remaining_content


# Global parser instance
_parser = UnifiedToolCallParser()


def parse_tool_calls(
    content: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[List[ToolCall], str]:
    """
    Convenience function to parse tool calls from content.

    Args:
        content: Text content from LLM
        metadata: Optional metadata containing tool calls in provider format

    Returns:
        Tuple of (list of ToolCall objects, remaining content)
    """
    return _parser.parse(content, metadata)

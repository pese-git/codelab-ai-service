"""
Tool call parser for extracting tool calls from LLM responses.

Supports OpenAI native tool calls format (modern and legacy function_call).
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.models.schemas import ToolCall

logger = logging.getLogger("agent-runtime.tool_parser")


class OpenAIToolCallParser:
    """Parser for OpenAI native tool call format (modern tools and legacy function_call)"""

    def parse(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ToolCall], str]:
        """
        Parse OpenAI-style tool calls from metadata.
        
        Args:
            content: Text content from LLM
            metadata: Optional metadata from LLM response
        
        Returns:
            Tuple of (list of ToolCall objects, remaining content after extraction)
        """
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


# Global parser instance
_parser = OpenAIToolCallParser()


def parse_tool_calls(
    content: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[List[ToolCall], str]:
    """
    Convenience function to parse tool calls from content.

    Args:
        content: Text content from LLM
        metadata: Optional metadata containing tool calls in OpenAI format

    Returns:
        Tuple of (list of ToolCall objects, remaining content)
    """
    return _parser.parse(content, metadata)

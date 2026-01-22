"""
LLM infrastructure components.

Provides:
- LLM client for communication with LLM Proxy
- Streaming service for handling LLM responses
- Tool call parser for extracting tool calls from LLM responses
"""
from app.infrastructure.llm.client import LLMProxyClient, llm_proxy_client
from app.infrastructure.llm.streaming import stream_response
from app.infrastructure.llm.tool_parser import parse_tool_calls, OpenAIToolCallParser

__all__ = [
    "LLMProxyClient",
    "llm_proxy_client",
    "stream_response",
    "parse_tool_calls",
    "OpenAIToolCallParser",
]

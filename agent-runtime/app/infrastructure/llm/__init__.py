"""
LLM infrastructure components.

Provides:
- LLM client for communication with LLM Proxy
- Streaming service for handling LLM responses
- Tool call parser for extracting tool calls from LLM responses
"""
# Новый клиент, возвращающий LLMResponse объекты
from app.infrastructure.llm.llm_client import LLMClient, LLMProxyClient

from app.infrastructure.llm.tool_parser import parse_tool_calls, OpenAIToolCallParser

__all__ = [
    "LLMClient",
    "LLMProxyClient",
    "parse_tool_calls",
    "OpenAIToolCallParser",
]

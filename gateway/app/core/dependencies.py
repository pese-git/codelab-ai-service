from functools import lru_cache
from app.services.session_manager import SessionManager
from app.services.token_buffer_manager import TokenBufferManager
from app.services.agent_runtime_proxy import AgentRuntimeProxy
from app.services.websocket import (
    WebSocketHandler,
    WebSocketMessageParser,
    SSEStreamHandler
)
from app.core.config import config

# Временно Singletons через lru_cache (FastAPI DI-best practice)

@lru_cache
def get_session_manager() -> SessionManager:
    return SessionManager()

@lru_cache
def get_token_buffer_manager() -> TokenBufferManager:
    return TokenBufferManager()

@lru_cache
def get_agent_runtime_proxy() -> AgentRuntimeProxy:
    """Получить singleton instance AgentRuntimeProxy."""
    return AgentRuntimeProxy(
        base_url=config.agent_url,
        internal_api_key=config.internal_api_key,
        timeout=config.request_timeout
    )

@lru_cache
def get_websocket_handler() -> WebSocketHandler:
    """Получить singleton instance WebSocketHandler."""
    return WebSocketHandler(
        message_parser=WebSocketMessageParser(),
        sse_handler=SSEStreamHandler(),
        agent_runtime_url=config.agent_url,
        internal_api_key=config.internal_api_key,
        stream_timeout=config.agent_stream_timeout
    )

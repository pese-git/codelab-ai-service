"""
FastAPI dependency injection providers.

Provides singleton instances and factory functions for services.
"""
from fastapi import Depends

from app.core.config import AppConfig, logger
from app.services.session_manager import session_manager
from app.services.llm_proxy_client import LLMProxyClient, llm_proxy_client
from app.services.tool_registry import LOCAL_TOOLS
from app.services.chat_service import ChatService


def get_config() -> AppConfig:
    """Get application configuration"""
    return AppConfig


def get_logger():
    """Get application logger"""
    return logger


def get_session_manager():
    """Get session manager singleton"""
    return session_manager


def get_llm_proxy_client() -> LLMProxyClient:
    """Get LLM proxy client singleton"""
    return llm_proxy_client


def get_tool_registry():
    """Get local tool registry"""
    return LOCAL_TOOLS


def get_chat_service(
    llm_client: LLMProxyClient = Depends(get_llm_proxy_client),
    tools = Depends(get_tool_registry),
) -> ChatService:
    """
    Create ChatService instance with dependencies.
    
    Args:
        llm_client: LLM proxy client
        tools: Tool registry
        
    Returns:
        ChatService instance
    """
    return ChatService(llm_proxy_client=llm_client, tools=tools)

from fastapi import Depends
from app.core.config import logger, AppConfig
from app.services.session_manager import session_manager
from app.services.llm_proxy_client import LLMProxyClient, llm_proxy_client
from app.services.tool_registry import TOOLS
from app.services.chat_service import ChatService

def get_tool_registry():
    return TOOLS

def get_settings():
    return AppConfig

def get_logger():
    return logger

def get_session_manager():
    return session_manager

def get_llm_proxy_client():
    return llm_proxy_client

def get_chat_service(
    llm_proxy_client: LLMProxyClient = Depends(get_llm_proxy_client),
    tools = Depends(get_tool_registry),
) -> ChatService:
    return ChatService(llm_proxy_client=llm_proxy_client, tools=tools)
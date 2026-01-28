"""
Dependency Injection для LLM компонентов.

Предоставляет фабрики для создания LLM-related сервисов и handlers.
"""

import logging
from typing import Annotated

from fastapi import Depends

from ..infrastructure.llm.llm_client import LLMClient, LLMProxyClient
from ..infrastructure.events.llm_event_publisher import LLMEventPublisher
from ..domain.services.llm_response_processor import LLMResponseProcessor
from ..domain.services.tool_filter_service import ToolFilterService
from ..domain.services.tool_registry import ToolRegistry
from ..domain.services.hitl_policy import hitl_policy_service
from ..domain.services.session_management import SessionManagementService
from ..application.handlers.stream_llm_response_handler import StreamLLMResponseHandler
from .dependencies import get_session_management_service

logger = logging.getLogger("agent-runtime.dependencies_llm")


# ==================== Infrastructure Dependencies ====================

# Singleton instance of LLM client
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """
    Получить LLM клиент (singleton).
    
    Returns:
        LLMClient: Клиент для вызова LLM API
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMProxyClient()
        logger.info("LLM client initialized")
    return _llm_client


async def cleanup_llm_client():
    """
    Закрыть LLM клиент и освободить ресурсы.
    
    Должен вызываться при shutdown приложения.
    """
    global _llm_client
    if _llm_client is not None:
        await _llm_client.close()
        _llm_client = None
        logger.info("LLM client closed and resources released")


# Singleton instance of event publisher
_llm_event_publisher: LLMEventPublisher | None = None


def get_llm_event_publisher() -> LLMEventPublisher:
    """
    Получить LLM event publisher (singleton).
    
    Returns:
        LLMEventPublisher: Publisher для LLM событий
    """
    global _llm_event_publisher
    if _llm_event_publisher is None:
        _llm_event_publisher = LLMEventPublisher()
        logger.info("LLM event publisher initialized")
    return _llm_event_publisher


# ==================== Domain Service Dependencies ====================

def get_tool_registry() -> ToolRegistry:
    """
    Получить реестр инструментов.
    
    Returns:
        ToolRegistry: Реестр всех доступных инструментов
    """
    # Используем существующий глобальный реестр
    from ..domain.services.tool_registry import tool_registry
    return tool_registry


def get_tool_filter_service(
    tool_registry: ToolRegistry = Depends(get_tool_registry)
) -> ToolFilterService:
    """
    Получить сервис фильтрации инструментов.
    
    Args:
        tool_registry: Реестр инструментов (инжектируется)
        
    Returns:
        ToolFilterService: Сервис фильтрации
    """
    return ToolFilterService(tool_registry=tool_registry)


def get_llm_response_processor() -> LLMResponseProcessor:
    """
    Получить процессор LLM ответов.
    
    Returns:
        LLMResponseProcessor: Процессор для обработки ответов
    """
    return LLMResponseProcessor(hitl_policy=hitl_policy_service)


# ==================== Annotated Types ====================

# Удобные типы для использования в роутерах
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
LLMEventPublisherDep = Annotated[LLMEventPublisher, Depends(get_llm_event_publisher)]
ToolFilterServiceDep = Annotated[ToolFilterService, Depends(get_tool_filter_service)]
LLMResponseProcessorDep = Annotated[LLMResponseProcessor, Depends(get_llm_response_processor)]

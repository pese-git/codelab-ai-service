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
from ..domain.services.hitl_management import hitl_manager
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


def get_hitl_manager():
    """
    Получить HITL менеджер (DEPRECATED).
    
    DEPRECATED: Используйте get_hitl_service() из dependencies.py
    Оставлено для обратной совместимости.
    
    Returns:
        HITLManager: Менеджер для управления HITL состоянием
    """
    # Используем существующий глобальный менеджер (deprecated)
    return hitl_manager


# ==================== Application Handler Dependencies ====================

async def get_stream_llm_response_handler(
    llm_client: LLMClient = Depends(get_llm_client),
    tool_filter: ToolFilterService = Depends(get_tool_filter_service),
    response_processor: LLMResponseProcessor = Depends(get_llm_response_processor),
    event_publisher: LLMEventPublisher = Depends(get_llm_event_publisher),
    session_service: SessionManagementService = Depends(get_session_management_service),
    hitl_service = Depends(lambda: __import__('app.core.dependencies', fromlist=['get_hitl_service']).get_hitl_service)
) -> StreamLLMResponseHandler:
    """
    Получить handler для стриминга LLM ответов.
    
    Args:
        llm_client: LLM клиент (инжектируется)
        tool_filter: Сервис фильтрации инструментов (инжектируется)
        response_processor: Процессор ответов (инжектируется)
        event_publisher: Event publisher (инжектируется)
        session_service: Сервис управления сессиями (инжектируется)
        hitl_service: HITL сервис (инжектируется)
        
    Returns:
        StreamLLMResponseHandler: Handler для стриминга
    """
    # Получить hitl_service из dependencies.py (избегаем циклического импорта)
    from .dependencies import get_hitl_service as get_hitl_svc
    hitl_svc = await get_hitl_svc()
    
    return StreamLLMResponseHandler(
        llm_client=llm_client,
        tool_filter=tool_filter,
        response_processor=response_processor,
        event_publisher=event_publisher,
        session_service=session_service,
        hitl_service=hitl_svc
    )


# ==================== Annotated Types ====================

# Удобные типы для использования в роутерах
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
LLMEventPublisherDep = Annotated[LLMEventPublisher, Depends(get_llm_event_publisher)]
ToolFilterServiceDep = Annotated[ToolFilterService, Depends(get_tool_filter_service)]
LLMResponseProcessorDep = Annotated[LLMResponseProcessor, Depends(get_llm_response_processor)]
StreamLLMResponseHandlerDep = Annotated[StreamLLMResponseHandler, Depends(get_stream_llm_response_handler)]

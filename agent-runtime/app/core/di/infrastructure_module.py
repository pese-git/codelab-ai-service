"""
DI Module для Infrastructure Layer.

Предоставляет зависимости для инфраструктурных компонентов.
"""

import logging
from typing import Optional

from app.infrastructure.llm import LLMProxyClient
from app.infrastructure.events.llm_event_publisher import LLMEventPublisher
from app.infrastructure.adapters import EventPublisherAdapter
from app.core.config import AppConfig

logger = logging.getLogger("agent-runtime.di.infrastructure_module")


class InfrastructureModule:
    """
    DI модуль для Infrastructure Layer.
    
    Предоставляет:
    - LLMClient
    - EventPublisher
    - LLMEventPublisher
    """
    
    def __init__(self):
        """Инициализация модуля."""
        self._llm_client: Optional[LLMProxyClient] = None
        self._event_publisher: Optional[EventPublisherAdapter] = None
        self._llm_event_publisher: Optional[LLMEventPublisher] = None
        
        logger.debug("InfrastructureModule инициализирован")
    
    def provide_llm_client(self) -> LLMProxyClient:
        """
        Предоставить LLM клиент.
        
        Returns:
            LLMProxyClient: Клиент для работы с LLM
        """
        if self._llm_client is None:
            self._llm_client = LLMProxyClient(
                api_url=AppConfig.LLM_PROXY_URL
            )
            logger.info(f"LLMProxyClient создан (base_url={AppConfig.LLM_PROXY_URL})")
        
        return self._llm_client
    
    def provide_event_publisher(self) -> EventPublisherAdapter:
        """
        Предоставить publisher событий.
        
        Returns:
            EventPublisherAdapter: Publisher событий
        """
        if self._event_publisher is None:
            self._event_publisher = EventPublisherAdapter()
            logger.info("EventPublisher создан")
        
        return self._event_publisher
    
    def provide_llm_event_publisher(
        self,
        event_publisher: EventPublisherAdapter
    ) -> LLMEventPublisher:
        """
        Предоставить publisher LLM событий.
        
        Args:
            event_publisher: Базовый publisher событий
            
        Returns:
            LLMEventPublisher: Publisher LLM событий
        """
        if self._llm_event_publisher is None:
            self._llm_event_publisher = LLMEventPublisher(
                event_publisher=event_publisher
            )
            logger.info("LLMEventPublisher создан")
        
        return self._llm_event_publisher

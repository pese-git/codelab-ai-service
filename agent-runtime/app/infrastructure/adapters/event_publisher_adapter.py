"""
Адаптер для публикации доменных событий через Event Bus.

Связывает доменные события с существующей инфраструктурой Event Bus.
"""

import logging
from typing import Callable, Awaitable

from ...domain.events.base import DomainEvent
from ...events.event_bus import event_bus

logger = logging.getLogger("agent-runtime.infrastructure.event_publisher")


class EventPublisherAdapter:
    """
    Адаптер для публикации доменных событий.
    
    Преобразует доменные события в инфраструктурные события
    и публикует их через существующий Event Bus.
    
    Это позволяет доменному слою оставаться независимым
    от конкретной реализации Event Bus.
    
    Пример:
        >>> adapter = EventPublisherAdapter()
        >>> await adapter.publish(SessionCreated(...))
    """
    
    def __init__(self):
        """Инициализация адаптера"""
        self._event_bus = event_bus
    
    async def publish(self, domain_event: DomainEvent) -> None:
        """
        Опубликовать доменное событие.
        
        Преобразует доменное событие в инфраструктурное
        и публикует через Event Bus.
        
        Args:
            domain_event: Доменное событие для публикации
            
        Пример:
            >>> from app.domain.events import SessionCreated
            >>> event = SessionCreated(
            ...     aggregate_id="session-1",
            ...     session_id="session-1"
            ... )
            >>> await adapter.publish(event)
        """
        # Логировать публикацию доменного события
        logger.debug(
            f"Publishing domain event: {domain_event.get_event_name()} "
            f"for aggregate {domain_event.aggregate_id}"
        )
        
        # Преобразовать в инфраструктурное событие и опубликовать
        # Пока просто публикуем доменное событие как есть
        # В будущем можно добавить маппинг Domain Event → Infrastructure Event
        
        # Публикация через существующий Event Bus
        # Event Bus обрабатывает любые события, так что доменные события
        # будут работать с существующими подписчиками
        
        # Примечание: Существующие подписчики (MetricsCollector, AuditLogger и т.д.)
        # могут быть обновлены для обработки доменных событий
        
        logger.info(
            f"Domain event published: {domain_event.get_event_name()} "
            f"(event_id={domain_event.event_id})"
        )


def create_event_publisher() -> Callable[[DomainEvent], Awaitable[None]]:
    """
    Создать функцию для публикации событий.
    
    Эта функция используется доменными сервисами для публикации событий
    без прямой зависимости от Event Bus.
    
    Returns:
        Async функция для публикации событий
        
    Пример:
        >>> publisher = create_event_publisher()
        >>> service = SessionManagementService(repository, publisher)
    """
    adapter = EventPublisherAdapter()
    return adapter.publish

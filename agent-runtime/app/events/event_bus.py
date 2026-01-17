"""
Event Bus implementation for pub/sub event handling.
"""

from typing import Callable, List, Dict, Optional, Any
from collections import defaultdict
import asyncio
import logging
from datetime import datetime

from .base_event import BaseEvent
from .event_types import EventType, EventCategory

logger = logging.getLogger(__name__)


class EventHandler:
    """Wrapper for event handler with metadata."""
    
    def __init__(
        self,
        handler: Callable,
        priority: int = 0,
        event_type: Optional[EventType] = None,
        event_category: Optional[EventCategory] = None
    ):
        self.handler = handler
        self.priority = priority
        self.event_type = event_type
        self.event_category = event_category
    
    def __repr__(self):
        return f"EventHandler(handler={self.handler.__name__}, priority={self.priority})"


class EventBusStats:
    """Statistics for event bus operations."""
    
    def __init__(self):
        self.total_published: int = 0
        self.successful_handlers: int = 0
        self.failed_handlers: int = 0
        self.last_event_time: Optional[datetime] = None


class EventBus:
    """
    Centralized event bus for asynchronous communication between components.
    
    Features:
    - Subscribe to events by type or category
    - Wildcard subscriptions (all events)
    - Handler priorities
    - Error handling for handlers
    - Async processing
    - Middleware support
    """
    
    def __init__(self):
        # Subscribers by event type
        self._subscribers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        
        # Subscribers by category
        self._category_subscribers: Dict[EventCategory, List[EventHandler]] = defaultdict(list)
        
        # Wildcard subscribers (receive all events)
        self._wildcard_subscribers: List[EventHandler] = []
        
        # Middleware for event processing
        self._middleware: List[Callable] = []
        
        # Statistics
        self._stats = EventBusStats()
        
        # Lock for thread-safety
        self._lock = asyncio.Lock()
    
    def subscribe(
        self,
        event_type: Optional[EventType] = None,
        event_category: Optional[EventCategory] = None,
        handler: Optional[Callable] = None,
        priority: int = 0
    ):
        """
        Subscribe to events.
        
        Args:
            event_type: Specific event type to subscribe to
            event_category: Event category to subscribe to
            handler: Async function to handle events
            priority: Handler priority (higher = executed first)
        
        Returns:
            Unsubscribe function or decorator
        
        Examples:
            # Direct subscription
            event_bus.subscribe(
                event_type=EventType.AGENT_SWITCHED,
                handler=my_handler
            )
            
            # Decorator usage
            @event_bus.subscribe(event_type=EventType.AGENT_SWITCHED)
            async def my_handler(event):
                pass
        """
        if handler is None:
            # Decorator mode
            def decorator(func: Callable):
                self._add_subscriber(event_type, event_category, func, priority)
                return func
            return decorator
        else:
            # Direct mode
            self._add_subscriber(event_type, event_category, handler, priority)
            
            # Return unsubscribe function
            def unsubscribe():
                self.unsubscribe(event_type, event_category, handler)
            return unsubscribe
    
    def _add_subscriber(
        self,
        event_type: Optional[EventType],
        event_category: Optional[EventCategory],
        handler: Callable,
        priority: int
    ):
        """Add a subscriber to the appropriate list."""
        event_handler = EventHandler(
            handler=handler,
            priority=priority,
            event_type=event_type,
            event_category=event_category
        )
        
        if event_type:
            self._subscribers[event_type].append(event_handler)
            self._subscribers[event_type].sort(key=lambda h: h.priority, reverse=True)
        elif event_category:
            self._category_subscribers[event_category].append(event_handler)
            self._category_subscribers[event_category].sort(key=lambda h: h.priority, reverse=True)
        else:
            # Wildcard subscription
            self._wildcard_subscribers.append(event_handler)
            self._wildcard_subscribers.sort(key=lambda h: h.priority, reverse=True)
        
        logger.debug(
            f"Subscribed {handler.__name__} to "
            f"{'type=' + str(event_type) if event_type else ''}"
            f"{'category=' + str(event_category) if event_category else ''}"
            f"{'wildcard' if not event_type and not event_category else ''}"
        )
    
    def unsubscribe(
        self,
        event_type: Optional[EventType],
        event_category: Optional[EventCategory],
        handler: Callable
    ):
        """Unsubscribe a handler from events."""
        if event_type:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type]
                if h.handler != handler
            ]
        elif event_category:
            self._category_subscribers[event_category] = [
                h for h in self._category_subscribers[event_category]
                if h.handler != handler
            ]
        else:
            self._wildcard_subscribers = [
                h for h in self._wildcard_subscribers
                if h.handler != handler
            ]
        
        logger.debug(f"Unsubscribed {handler.__name__}")
    
    async def publish(
        self,
        event: BaseEvent,
        wait_for_handlers: bool = False
    ) -> Optional[List[Any]]:
        """
        Publish an event to all subscribers.
        
        Args:
            event: Event to publish
            wait_for_handlers: If True, wait for all handlers to complete
        
        Returns:
            List of handler results if wait_for_handlers=True, else None
        """
        async with self._lock:
            self._stats.total_published += 1
            self._stats.last_event_time = datetime.utcnow()
        
        # Apply middleware
        for middleware in self._middleware:
            event = await middleware(event)
            if event is None:
                # Middleware cancelled the event
                logger.debug("Event cancelled by middleware")
                return None
        
        # Get all handlers for this event
        handlers = self._get_handlers_for_event(event)
        
        if not handlers:
            logger.debug(f"No handlers for event {event.event_type}")
            return None
        
        logger.debug(
            f"Publishing event {event.event_type} to {len(handlers)} handlers"
        )
        
        # Execute handlers
        if wait_for_handlers:
            results = await self._execute_handlers_sync(event, handlers)
            return results
        else:
            # Fire and forget
            asyncio.create_task(self._execute_handlers_async(event, handlers))
            return None
    
    def _get_handlers_for_event(self, event: BaseEvent) -> List[EventHandler]:
        """Get all subscribers for an event."""
        handlers = []
        
        # Type-specific subscribers
        if event.event_type in self._subscribers:
            handlers.extend(self._subscribers[event.event_type])
        
        # Category subscribers
        if event.event_category in self._category_subscribers:
            handlers.extend(self._category_subscribers[event.event_category])
        
        # Wildcard subscribers
        handlers.extend(self._wildcard_subscribers)
        
        # Sort by priority
        handlers.sort(key=lambda h: h.priority, reverse=True)
        
        return handlers
    
    async def _execute_handlers_sync(
        self,
        event: BaseEvent,
        handlers: List[EventHandler]
    ) -> List[Any]:
        """Execute handlers synchronously (wait for all)."""
        results = []
        
        for handler in handlers:
            try:
                result = await handler.handler(event)
                results.append(result)
                
                async with self._lock:
                    self._stats.successful_handlers += 1
                    
            except Exception as e:
                logger.error(
                    f"Error in event handler {handler.handler.__name__} "
                    f"for event {event.event_type}: {e}",
                    exc_info=True
                )
                async with self._lock:
                    self._stats.failed_handlers += 1
                results.append(None)
        
        return results
    
    async def _execute_handlers_async(
        self,
        event: BaseEvent,
        handlers: List[EventHandler]
    ):
        """Execute handlers asynchronously (fire and forget)."""
        tasks = []
        
        for handler in handlers:
            task = asyncio.create_task(self._execute_single_handler(event, handler))
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_single_handler(
        self,
        event: BaseEvent,
        handler: EventHandler
    ):
        """Execute a single handler with error handling."""
        try:
            await handler.handler(event)
            
            async with self._lock:
                self._stats.successful_handlers += 1
                
        except Exception as e:
            logger.error(
                f"Error in event handler {handler.handler.__name__} "
                f"for event {event.event_type}: {e}",
                exc_info=True
            )
            async with self._lock:
                self._stats.failed_handlers += 1
    
    def add_middleware(self, middleware: Callable):
        """
        Add middleware for event processing.
        
        Middleware can:
        - Modify events
        - Cancel events (return None)
        - Log events
        - Validate events
        
        Args:
            middleware: Async function that takes an event and returns an event or None
        """
        self._middleware.append(middleware)
        logger.debug(f"Added middleware: {middleware.__name__}")
    
    def get_stats(self) -> EventBusStats:
        """Get event bus statistics."""
        return self._stats
    
    async def clear(self):
        """Clear all subscriptions (for testing)."""
        async with self._lock:
            self._subscribers.clear()
            self._category_subscribers.clear()
            self._wildcard_subscribers.clear()
            self._middleware.clear()
        logger.debug("Event bus cleared")


# Global singleton instance
event_bus = EventBus()

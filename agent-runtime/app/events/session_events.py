"""
Session-specific events for the Event-Driven Architecture.
"""

from typing import Optional

from .base_event import BaseEvent
from .event_types import EventType, EventCategory


class SessionCreatedEvent(BaseEvent):
    """Event published when a new session is created."""
    
    def __init__(
        self,
        session_id: str,
        system_prompt: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.SESSION_CREATED,
            event_category=EventCategory.SESSION,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "system_prompt_length": len(system_prompt)
            },
            source="session_manager"
        )


class SessionUpdatedEvent(BaseEvent):
    """Event published when a session is updated."""
    
    def __init__(
        self,
        session_id: str,
        update_type: str,  # message_added, tool_result_added, etc.
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.SESSION_UPDATED,
            event_category=EventCategory.SESSION,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "update_type": update_type
            },
            source="session_manager"
        )


class SessionDeletedEvent(BaseEvent):
    """Event published when a session is deleted."""
    
    def __init__(
        self,
        session_id: str,
        soft_delete: bool = True,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.SESSION_DELETED,
            event_category=EventCategory.SESSION,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "soft_delete": soft_delete
            },
            source="session_manager"
        )


class MessageAddedEvent(BaseEvent):
    """Event published when a message is added to a session."""
    
    def __init__(
        self,
        session_id: str,
        role: str,  # user, assistant, tool
        content_length: int,
        agent_name: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.MESSAGE_ADDED,
            event_category=EventCategory.SESSION,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "role": role,
                "content_length": content_length,
                "agent_name": agent_name
            },
            source="session_manager"
        )

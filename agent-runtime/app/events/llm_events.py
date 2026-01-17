"""
LLM-specific events for tracking LLM requests and token usage.
"""

from typing import Optional

from .base_event import BaseEvent
from .event_types import EventType, EventCategory


class LLMRequestStartedEvent(BaseEvent):
    """Event published when an LLM request starts."""
    
    def __init__(
        self,
        session_id: str,
        model: str,
        message_count: int,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.LLM_REQUEST_STARTED,
            event_category=EventCategory.METRICS,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "model": model,
                "message_count": message_count
            },
            source="llm_stream_service"
        )


class LLMRequestCompletedEvent(BaseEvent):
    """Event published when an LLM request completes successfully."""
    
    def __init__(
        self,
        session_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        duration_ms: float,
        cost: float = 0.0,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.LLM_REQUEST_COMPLETED,
            event_category=EventCategory.METRICS,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "duration_ms": duration_ms,
                "cost": cost
            },
            source="llm_stream_service"
        )


class LLMRequestFailedEvent(BaseEvent):
    """Event published when an LLM request fails."""
    
    def __init__(
        self,
        session_id: str,
        model: str,
        error_message: str,
        error_type: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.LLM_REQUEST_FAILED,
            event_category=EventCategory.METRICS,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "model": model,
                "error_message": error_message,
                "error_type": error_type
            },
            source="llm_stream_service"
        )

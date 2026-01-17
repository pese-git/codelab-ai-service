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
        messages_count: int,
        tools_count: int,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.LLM_REQUEST_STARTED,
            event_category=EventCategory.METRICS,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "model": model,
                "messages_count": messages_count,
                "tools_count": tools_count
            },
            source="llm_stream_service"
        )


class LLMRequestCompletedEvent(BaseEvent):
    """Event published when an LLM request completes successfully."""
    
    def __init__(
        self,
        session_id: str,
        model: str,
        duration_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        has_tool_calls: bool,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.LLM_REQUEST_COMPLETED,
            event_category=EventCategory.METRICS,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "model": model,
                "duration_ms": duration_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "has_tool_calls": has_tool_calls
            },
            source="llm_stream_service"
        )


class LLMRequestFailedEvent(BaseEvent):
    """Event published when an LLM request fails."""
    
    def __init__(
        self,
        session_id: str,
        model: str,
        error: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.LLM_REQUEST_FAILED,
            event_category=EventCategory.METRICS,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "model": model,
                "error": error
            },
            source="llm_stream_service"
        )

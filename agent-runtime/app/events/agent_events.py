"""
Agent-specific events for the Event-Driven Architecture.
"""

from typing import Optional
from datetime import datetime

from .base_event import BaseEvent
from .event_types import EventType, EventCategory


class AgentSwitchedEvent(BaseEvent):
    """Event published when an agent switch occurs."""
    
    def __init__(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str,
        reason: str,
        confidence: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.AGENT_SWITCHED,
            event_category=EventCategory.AGENT,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "from_agent": from_agent,
                "to_agent": to_agent,
                "reason": reason,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat()
            },
            source="multi_agent_orchestrator"
        )


class AgentProcessingStartedEvent(BaseEvent):
    """Event published when an agent starts processing a message."""
    
    def __init__(
        self,
        session_id: str,
        agent_type: str,
        message: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.AGENT_PROCESSING_STARTED,
            event_category=EventCategory.AGENT,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "agent": agent_type,
                "message_length": len(message),
                "message_preview": message[:100] if len(message) > 100 else message
            },
            source=f"{agent_type}_agent"
        )


class AgentProcessingCompletedEvent(BaseEvent):
    """Event published when an agent completes processing."""
    
    def __init__(
        self,
        session_id: str,
        agent_type: str,
        duration_ms: float,
        success: bool,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.AGENT_PROCESSING_COMPLETED,
            event_category=EventCategory.AGENT,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "agent": agent_type,
                "duration_ms": duration_ms,
                "success": success
            },
            source=f"{agent_type}_agent"
        )


class AgentErrorOccurredEvent(BaseEvent):
    """Event published when an error occurs in an agent."""
    
    def __init__(
        self,
        session_id: str,
        agent_type: str,
        error_message: str,
        error_type: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.AGENT_ERROR_OCCURRED,
            event_category=EventCategory.AGENT,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "agent": agent_type,
                "error_message": error_message,
                "error_type": error_type
            },
            source=f"{agent_type}_agent"
        )

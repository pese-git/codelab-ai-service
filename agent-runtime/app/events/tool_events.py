"""
Tool and HITL-specific events for the Event-Driven Architecture.
"""

from typing import Dict, Any, Optional

from .base_event import BaseEvent
from .event_types import EventType, EventCategory


class ToolExecutionRequestedEvent(BaseEvent):
    """Event published when a tool execution is requested."""
    
    def __init__(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: str,
        agent: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.TOOL_EXECUTION_REQUESTED,
            event_category=EventCategory.TOOL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "tool_name": tool_name,
                "arguments": arguments,
                "call_id": call_id,
                "agent": agent
            },
            source="llm_stream_service"
        )


class ToolExecutionStartedEvent(BaseEvent):
    """Event published when tool execution starts."""
    
    def __init__(
        self,
        session_id: str,
        tool_name: str,
        call_id: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.TOOL_EXECUTION_STARTED,
            event_category=EventCategory.TOOL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "tool_name": tool_name,
                "call_id": call_id
            },
            source="tool_executor"
        )


class ToolExecutionCompletedEvent(BaseEvent):
    """Event published when tool execution completes successfully."""
    
    def __init__(
        self,
        session_id: str,
        tool_name: str,
        call_id: str,
        duration_ms: float,
        result_length: int,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.TOOL_EXECUTION_COMPLETED,
            event_category=EventCategory.TOOL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "tool_name": tool_name,
                "call_id": call_id,
                "duration_ms": duration_ms,
                "result_length": result_length
            },
            source="tool_executor"
        )


class ToolExecutionFailedEvent(BaseEvent):
    """Event published when tool execution fails."""
    
    def __init__(
        self,
        session_id: str,
        tool_name: str,
        call_id: str,
        error_message: str,
        error_type: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.TOOL_EXECUTION_FAILED,
            event_category=EventCategory.TOOL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "tool_name": tool_name,
                "call_id": call_id,
                "error_message": error_message,
                "error_type": error_type
            },
            source="tool_executor"
        )


class ToolApprovalRequiredEvent(BaseEvent):
    """Event published when a tool requires HITL approval."""
    
    def __init__(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: str,
        reason: str,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.TOOL_APPROVAL_REQUIRED,
            event_category=EventCategory.HITL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "tool_name": tool_name,
                "arguments": arguments,
                "call_id": call_id,
                "reason": reason
            },
            source="hitl_policy_service"
        )


class HITLApprovalRequestedEvent(BaseEvent):
    """Event published when HITL approval is requested."""
    
    def __init__(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: str,
        timeout_seconds: int = 300,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.HITL_APPROVAL_REQUESTED,
            event_category=EventCategory.HITL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "call_id": call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "reason": reason,
                "timeout_seconds": timeout_seconds
            },
            source="hitl_manager"
        )


class HITLDecisionMadeEvent(BaseEvent):
    """Event published when a HITL decision is made."""
    
    def __init__(
        self,
        session_id: str,
        call_id: str,
        decision: str,  # APPROVE, EDIT, REJECT
        tool_name: str,
        original_args: Dict[str, Any],
        modified_args: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.HITL_DECISION_MADE,
            event_category=EventCategory.HITL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "call_id": call_id,
                "decision": decision,
                "tool_name": tool_name,
                "original_args": original_args,
                "modified_args": modified_args
            },
            source="hitl_manager"
        )


class HITLTimeoutOccurredEvent(BaseEvent):
    """Event published when a HITL approval times out."""
    
    def __init__(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        timeout_seconds: int,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.HITL_TIMEOUT_OCCURRED,
            event_category=EventCategory.HITL,
            session_id=session_id,
            correlation_id=correlation_id,
            data={
                "call_id": call_id,
                "tool_name": tool_name,
                "timeout_seconds": timeout_seconds
            },
            source="hitl_manager"
        )

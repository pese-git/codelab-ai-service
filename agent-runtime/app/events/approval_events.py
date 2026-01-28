"""
Unified Approval System - Domain Events.

Events for approval lifecycle:
- ApprovalRequestedEvent: When approval is requested
- ApprovalApprovedEvent: When approval is approved
- ApprovalRejectedEvent: When approval is rejected
"""
from typing import Optional
from app.events.base_event import BaseEvent
from app.events.event_types import EventType, EventCategory


class ApprovalRequestedEvent(BaseEvent):
    """Event when approval is requested"""
    
    def __init__(
        self,
        aggregate_id: str,
        session_id: str,
        request_id: str,
        request_type: str,
        subject: str,
        reason: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.APPROVAL_REQUESTED,
            event_category=EventCategory.APPROVAL,
            session_id=session_id,
            data={
                "request_id": request_id,
                "request_type": request_type,
                "subject": subject,
                "reason": reason
            },
            source="approval_manager"
        )


class ApprovalApprovedEvent(BaseEvent):
    """Event when approval is approved"""
    
    def __init__(
        self,
        aggregate_id: str,
        session_id: str,
        request_id: str,
        request_type: str
    ):
        super().__init__(
            event_type=EventType.APPROVAL_APPROVED,
            event_category=EventCategory.APPROVAL,
            session_id=session_id,
            data={
                "request_id": request_id,
                "request_type": request_type
            },
            source="approval_manager"
        )


class ApprovalRejectedEvent(BaseEvent):
    """Event when approval is rejected"""
    
    def __init__(
        self,
        aggregate_id: str,
        session_id: str,
        request_id: str,
        request_type: str,
        reason: Optional[str] = None
    ):
        super().__init__(
            event_type=EventType.APPROVAL_REJECTED,
            event_category=EventCategory.APPROVAL,
            session_id=session_id,
            data={
                "request_id": request_id,
                "request_type": request_type,
                "reason": reason
            },
            source="approval_manager"
        )

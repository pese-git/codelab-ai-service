"""
Base event model for the Event-Driven Architecture.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid

from .event_types import EventType, EventCategory


class BaseEvent(BaseModel):
    """
    Base class for all events in the system.
    
    Provides common metadata and structure for events.
    """
    
    # Event metadata
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    event_category: EventCategory
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Context
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None  # For tracing related events
    causation_id: Optional[str] = None    # ID of the event that caused this event
    
    # Event data
    data: Dict[str, Any]
    
    # Source metadata
    source: str  # Component that created the event
    version: str = "1.0"
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def dict(self, **kwargs):
        """Override dict to ensure datetime serialization."""
        d = super().dict(**kwargs)
        if isinstance(d.get('timestamp'), datetime):
            d['timestamp'] = d['timestamp'].isoformat()
        return d

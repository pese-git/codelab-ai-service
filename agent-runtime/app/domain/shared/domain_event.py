"""
Base Domain Event class for Domain-Driven Design.

This module provides the foundation for all domain events following DDD principles.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


class DomainEvent(BaseModel):
    """
    Base class for all domain events.
    
    A domain event represents something that happened in the domain that domain
    experts care about. Events are immutable and represent facts that occurred.
    
    Principles:
    - Immutability: Events cannot be modified after creation
    - Past tense: Event names should be in past tense (e.g., OrderPlaced, not PlaceOrder)
    - Rich information: Events should contain all relevant information
    - Timestamp: Events should record when they occurred
    
    Usage:
        from pydantic import Field
        
        class ConversationStarted(DomainEvent):
            conversation_id: str = Field(..., description="ID разговора")
            user_id: str = Field(..., description="ID пользователя")
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutability
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
    
    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Уникальный идентификатор события"
    )
    
    event_type: str = Field(
        default="",
        description="Тип события (имя класса)"
    )
    
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время возникновения события"
    )
    
    def model_post_init(self, __context: Any) -> None:
        """Post-initialization hook to set event_type."""
        # Set event_type to class name if not provided
        if not self.event_type:
            object.__setattr__(self, 'event_type', self.__class__.__name__)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event to dictionary representation.
        
        Returns:
            Dictionary with event data
        """
        return self.model_dump()

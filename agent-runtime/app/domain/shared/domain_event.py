"""
Base Domain Event class for Domain-Driven Design.

This module provides the foundation for all domain events following DDD principles.
"""

from abc import ABC
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


class DomainEvent(ABC):
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
        class ConversationStarted(DomainEvent):
            def __init__(self, conversation_id: str, user_id: str):
                super().__init__()
                self._conversation_id = conversation_id
                self._user_id = user_id
            
            @property
            def conversation_id(self) -> str:
                return self._conversation_id
            
            @property
            def user_id(self) -> str:
                return self._user_id
            
            def to_dict(self) -> Dict[str, Any]:
                data = super().to_dict()
                data.update({
                    "conversation_id": self._conversation_id,
                    "user_id": self._user_id
                })
                return data
    """
    
    def __init__(self, event_id: Optional[str] = None, occurred_at: Optional[datetime] = None):
        """
        Initialize domain event.
        
        Args:
            event_id: Optional unique event identifier. If not provided, generates UUID.
            occurred_at: Optional timestamp. If not provided, uses current UTC time.
        """
        self._event_id: str = event_id or str(uuid4())
        self._occurred_at: datetime = occurred_at or datetime.now(timezone.utc)
        self._event_type: str = self.__class__.__name__
    
    @property
    def event_id(self) -> str:
        """Get event unique identifier."""
        return self._event_id
    
    @property
    def occurred_at(self) -> datetime:
        """Get event occurrence timestamp."""
        return self._occurred_at
    
    @property
    def event_type(self) -> str:
        """Get event type (class name)."""
        return self._event_type
    
    def __eq__(self, other: Any) -> bool:
        """
        Compare events by identity.
        
        Args:
            other: Object to compare with
            
        Returns:
            True if events have the same ID and type
        """
        if not isinstance(other, DomainEvent):
            return False
        return self._event_id == other._event_id and type(self) == type(other)
    
    def __hash__(self) -> int:
        """
        Generate hash based on identity.
        
        Returns:
            Hash of event ID and type
        """
        return hash((self._event_id, type(self)))
    
    def __repr__(self) -> str:
        """
        String representation of event.
        
        Returns:
            String with event type and ID
        """
        return f"{self._event_type}(id={self._event_id}, occurred_at={self._occurred_at.isoformat()})"
    
    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevent modification after initialization.
        
        Args:
            name: Attribute name
            value: Attribute value
            
        Raises:
            AttributeError: If trying to modify after initialization
        """
        # Allow setting during __init__ (when object.__getattribute__ raises)
        try:
            object.__getattribute__(self, name)
            raise AttributeError(
                f"Cannot modify immutable domain event {self.__class__.__name__}"
            )
        except AttributeError:
            # Attribute doesn't exist yet, allow setting
            object.__setattr__(self, name, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event to dictionary representation.
        
        Subclasses should override this method to include their specific data.
        
        Returns:
            Dictionary with event data
        """
        return {
            "event_id": self._event_id,
            "event_type": self._event_type,
            "occurred_at": self._occurred_at.isoformat()
        }

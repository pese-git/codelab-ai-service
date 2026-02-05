"""
Base Entity class for Domain-Driven Design.

This module provides the foundation for all domain entities following DDD principles.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Entity(BaseModel):
    """
    Base class for all domain entities.
    
    An entity is defined by its identity, not its attributes.
    Two entities with the same ID are considered equal, even if their attributes differ.
    
    Principles:
    - Identity: Each entity has a unique identifier
    - Lifecycle: Entities have a lifecycle (created, modified, etc.)
    - Equality: Based on identity, not attributes
    
    Attributes:
        id: Unique identifier
        created_at: Creation timestamp (UTC)
        updated_at: Last update timestamp (UTC)
    """
    
    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp (UTC)"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp (UTC)"
    )
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def mark_updated(self) -> None:
        """Mark entity as updated (sets updated_at to current time)."""
        self.updated_at = datetime.now(timezone.utc)
    
    def add_domain_event(self, event: Any) -> None:
        """
        Add domain event to entity.
        
        Args:
            event: Domain event to add
        """
        if not hasattr(self, '_domain_events'):
            self._domain_events: List[Any] = []
        self._domain_events.append(event)
    
    def clear_domain_events(self) -> None:
        """Clear all domain events."""
        self._domain_events = []
    
    @property
    def domain_events(self) -> List[Any]:
        """Get list of domain events."""
        if not hasattr(self, '_domain_events'):
            self._domain_events = []
        return self._domain_events.copy()
    
    def __eq__(self, other: Any) -> bool:
        """
        Compare entities by identity.
        
        Args:
            other: Object to compare with
            
        Returns:
            True if entities have the same ID and type
        """
        if not isinstance(other, Entity):
            return False
        return self.id == other.id and type(self) == type(other)
    
    def __hash__(self) -> int:
        """
        Generate hash based on identity.
        
        Returns:
            Hash of entity ID and type
        """
        return hash((self.id, type(self)))
    
    def __repr__(self) -> str:
        """
        String representation of entity.
        
        Returns:
            String with entity type and ID
        """
        return f"{self.__class__.__name__}(id={self.id})"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert entity to dictionary representation.
        
        Returns:
            Dictionary with entity data
        """
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Alias for backward compatibility
BaseEntity = Entity

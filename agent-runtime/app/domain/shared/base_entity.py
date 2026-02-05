"""
Base Entity class for Domain-Driven Design.

This module provides the foundation for all domain entities following DDD principles.
"""

from abc import ABC
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


class Entity(ABC):
    """
    Base class for all domain entities.
    
    An entity is defined by its identity, not its attributes.
    Two entities with the same ID are considered equal, even if their attributes differ.
    
    Principles:
    - Identity: Each entity has a unique identifier
    - Lifecycle: Entities have a lifecycle (created, modified, etc.)
    - Equality: Based on identity, not attributes
    """
    
    def __init__(self, id: Optional[str] = None):
        """
        Initialize entity with unique identifier.
        
        Args:
            id: Optional unique identifier. If not provided, generates UUID.
        """
        self._id: str = id or str(uuid4())
        self._created_at: datetime = datetime.now(timezone.utc)
        self._updated_at: datetime = datetime.now(timezone.utc)
        self._version: int = 1
    
    @property
    def id(self) -> str:
        """Get entity identifier."""
        return self._id
    
    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at
    
    @property
    def version(self) -> int:
        """Get entity version for optimistic locking."""
        return self._version
    
    def _mark_updated(self) -> None:
        """Mark entity as updated (internal use)."""
        self._updated_at = datetime.now(timezone.utc)
        self._version += 1
    
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
        return self._id == other._id and type(self) == type(other)
    
    def __hash__(self) -> int:
        """
        Generate hash based on identity.
        
        Returns:
            Hash of entity ID and type
        """
        return hash((self._id, type(self)))
    
    def __repr__(self) -> str:
        """
        String representation of entity.
        
        Returns:
            String with entity type and ID
        """
        return f"{self.__class__.__name__}(id={self._id})"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert entity to dictionary representation.
        
        Returns:
            Dictionary with entity data
        """
        return {
            "id": self._id,
            "created_at": self._created_at.isoformat(),
            "updated_at": self._updated_at.isoformat(),
            "version": self._version
        }


# Alias for backward compatibility
BaseEntity = Entity

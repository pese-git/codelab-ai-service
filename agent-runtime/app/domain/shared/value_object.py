"""
Base Value Object class for Domain-Driven Design.

This module provides the foundation for all value objects following DDD principles.
"""

from pydantic import BaseModel, ConfigDict


class ValueObject(BaseModel):
    """
    Base class for all value objects.
    
    A value object is defined by its attributes, not by identity.
    Two value objects with the same attributes are considered equal.
    
    Principles:
    - Immutability: Value objects cannot be modified after creation
    - Equality: Based on attributes, not identity
    - No Identity: Value objects don't have unique identifiers
    - Self-validation: Value objects validate themselves on creation
    
    Usage:
        from pydantic import Field, field_validator
        
        class Email(ValueObject):
            value: str = Field(..., description="Email address")
            
            @field_validator("value")
            @classmethod
            def validate_email(cls, v: str) -> str:
                if "@" not in v:
                    raise ValueError("Invalid email")
                return v
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutability
        validate_assignment=True,  # Validate on assignment
        arbitrary_types_allowed=True,  # Allow custom types
    )
    
    def __hash__(self) -> int:
        """
        Generate hash based on attributes.
        
        Returns:
            Hash of all attributes
        """
        # Use Pydantic's model_dump for consistent hashing
        values = tuple(sorted(self.model_dump().items()))
        return hash(values)

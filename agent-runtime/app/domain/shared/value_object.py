"""
Base Value Object class for Domain-Driven Design.

This module provides the foundation for all value objects following DDD principles.
"""

from abc import ABC
from typing import Any


class ValueObject(ABC):
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
        class Email(ValueObject):
            def __init__(self, value: str):
                if not self._is_valid_email(value):
                    raise ValueError(f"Invalid email: {value}")
                self._value = value
            
            @property
            def value(self) -> str:
                return self._value
            
            def _is_valid_email(self, email: str) -> bool:
                return "@" in email
    """
    
    def __eq__(self, other: Any) -> bool:
        """
        Compare value objects by attributes.
        
        Args:
            other: Object to compare with
            
        Returns:
            True if all attributes are equal
        """
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self) -> int:
        """
        Generate hash based on attributes.
        
        Returns:
            Hash of all attributes
        """
        # Convert dict values to tuple for hashing
        # Filter out private attributes starting with _
        public_attrs = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return hash(tuple(sorted(public_attrs.items())))
    
    def __repr__(self) -> str:
        """
        String representation of value object.
        
        Returns:
            String with class name and attributes
        """
        attrs = ", ".join(
            f"{k}={v!r}" 
            for k, v in self.__dict__.items() 
            if not k.startswith('_')
        )
        return f"{self.__class__.__name__}({attrs})"
    
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
                f"Cannot modify immutable value object {self.__class__.__name__}"
            )
        except AttributeError:
            # Attribute doesn't exist yet, allow setting
            object.__setattr__(self, name, value)

"""
ConversationId Value Object.

Represents a unique identifier for a conversation with validation.
"""

import re
from typing import Optional

from app.domain.shared.value_object import ValueObject


class ConversationId(ValueObject):
    """
    Value object representing a conversation identifier.
    
    Encapsulates validation logic for conversation IDs to ensure they are:
    - Non-empty
    - Within length limits (1-255 characters)
    - Valid format (alphanumeric, hyphens, underscores)
    
    Principles:
    - Immutable: Cannot be changed after creation
    - Self-validating: Validates on construction
    - Type-safe: Prevents invalid IDs from being created
    
    Usage:
        >>> conv_id = ConversationId("session-123")
        >>> str(conv_id)
        'session-123'
        
        >>> invalid_id = ConversationId("")  # Raises ValueError
    """
    
    # Validation constants
    MIN_LENGTH = 1
    MAX_LENGTH = 255
    VALID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    def __init__(self, value: str):
        """
        Initialize conversation ID with validation.
        
        Args:
            value: String identifier for the conversation
            
        Raises:
            ValueError: If value is invalid (empty, too long, invalid format)
        """
        if not value:
            raise ValueError("Conversation ID cannot be empty")
        
        if len(value) < self.MIN_LENGTH:
            raise ValueError(
                f"Conversation ID must be at least {self.MIN_LENGTH} character(s)"
            )
        
        if len(value) > self.MAX_LENGTH:
            raise ValueError(
                f"Conversation ID cannot exceed {self.MAX_LENGTH} characters, got {len(value)}"
            )
        
        if not self.VALID_PATTERN.match(value):
            raise ValueError(
                f"Conversation ID must contain only alphanumeric characters, "
                f"hyphens, and underscores. Got: {value}"
            )
        
        self._value = value
    
    @property
    def value(self) -> str:
        """Get the string value of the conversation ID."""
        return self._value
    
    def __str__(self) -> str:
        """String representation returns the ID value."""
        return self._value
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"ConversationId('{self._value}')"
    
    @classmethod
    def generate(cls) -> 'ConversationId':
        """
        Generate a new unique conversation ID.
        
        Returns:
            New ConversationId with UUID-based value
            
        Usage:
            >>> conv_id = ConversationId.generate()
            >>> len(str(conv_id)) == 36  # UUID length
            True
        """
        import uuid
        return cls(str(uuid.uuid4()))

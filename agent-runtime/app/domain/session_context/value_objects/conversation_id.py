"""
ConversationId Value Object.

Represents a unique identifier for a conversation with validation.
"""

import re
from typing import Optional, ClassVar
from pydantic import field_validator

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
        >>> conv_id = ConversationId(value="session-123")
        >>> str(conv_id)
        'session-123'
        
        >>> invalid_id = ConversationId(value="")  # Raises ValueError
    """
    
    value: str
    
    # Validation constants
    MIN_LENGTH: ClassVar[int] = 1
    MAX_LENGTH: ClassVar[int] = 255
    VALID_PATTERN: ClassVar[re.Pattern] = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Validate conversation ID format and constraints."""
        if not v:
            raise ValueError("Conversation ID не может быть пустым")
        
        if len(v) < cls.MIN_LENGTH:
            raise ValueError(f"Conversation ID не может быть короче {cls.MIN_LENGTH} символов")
        
        if len(v) > cls.MAX_LENGTH:
            raise ValueError(f"Conversation ID не может превышать {cls.MAX_LENGTH} символов")
        
        if not cls.VALID_PATTERN.match(v):
            raise ValueError(
                "Conversation ID может содержать только буквы, цифры, дефисы и подчеркивания"
            )
        
        return v
    
    def __str__(self) -> str:
        """String representation returns the ID value."""
        return self.value
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"ConversationId('{self.value}')"
    
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
        return cls(value=str(uuid.uuid4()))

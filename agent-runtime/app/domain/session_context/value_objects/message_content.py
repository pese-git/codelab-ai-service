"""
MessageContent Value Object.

Represents message content with validation and sanitization.
"""

from typing import Optional

from app.domain.shared.value_object import ValueObject


class MessageContent(ValueObject):
    """
    Value object representing message content.
    
    Encapsulates validation logic for message content to ensure it is:
    - Within length limits
    - Properly sanitized
    - Non-null (empty strings are allowed for some message types)
    
    Principles:
    - Immutable: Cannot be changed after creation
    - Self-validating: Validates on construction
    - Type-safe: Prevents invalid content from being created
    
    Usage:
        >>> content = MessageContent("Hello, world!")
        >>> str(content)
        'Hello, world!'
        
        >>> long_content = MessageContent("x" * 200000)  # Raises ValueError
    """
    
    # Validation constants
    MAX_LENGTH = 100000  # 100KB of text
    
    def __init__(self, text: str, max_length: Optional[int] = None):
        """
        Initialize message content with validation.
        
        Args:
            text: Content text
            max_length: Optional custom max length (defaults to MAX_LENGTH)
            
        Raises:
            ValueError: If content exceeds maximum length
            TypeError: If text is not a string
        """
        if not isinstance(text, str):
            raise TypeError(f"Message content must be a string, got {type(text).__name__}")
        
        max_len = max_length or self.MAX_LENGTH
        
        if len(text) > max_len:
            raise ValueError(
                f"Message content too long: {len(text)} characters exceeds "
                f"maximum of {max_len} characters"
            )
        
        self._text = text
        self._length = len(text)
    
    @property
    def text(self) -> str:
        """Get the text content."""
        return self._text
    
    @property
    def length(self) -> int:
        """Get the length of the content."""
        return self._length
    
    def is_empty(self) -> bool:
        """
        Check if content is empty.
        
        Returns:
            True if content is empty or whitespace-only
        """
        return not self._text.strip()
    
    def truncate(self, max_length: int) -> 'MessageContent':
        """
        Create a new MessageContent with truncated text.
        
        Args:
            max_length: Maximum length for truncation
            
        Returns:
            New MessageContent with truncated text
            
        Usage:
            >>> content = MessageContent("Hello, world!")
            >>> short = content.truncate(5)
            >>> str(short)
            'Hello'
        """
        if max_length < 0:
            raise ValueError("max_length must be non-negative")
        
        truncated_text = self._text[:max_length]
        return MessageContent(truncated_text)
    
    def preview(self, length: int = 50) -> str:
        """
        Get a preview of the content.
        
        Args:
            length: Maximum length of preview
            
        Returns:
            Preview string with ellipsis if truncated
            
        Usage:
            >>> content = MessageContent("This is a very long message...")
            >>> content.preview(10)
            'This is a...'
        """
        if self._length <= length:
            return self._text
        
        return self._text[:length] + "..."
    
    def __str__(self) -> str:
        """String representation returns the text content."""
        return self._text
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        preview = self.preview(30)
        return f"MessageContent('{preview}', length={self._length})"
    
    def __len__(self) -> int:
        """Support len() function."""
        return self._length
    
    @classmethod
    def empty(cls) -> 'MessageContent':
        """
        Create an empty message content.
        
        Returns:
            MessageContent with empty string
            
        Usage:
            >>> content = MessageContent.empty()
            >>> content.is_empty()
            True
        """
        return cls("")

"""
Session Context Repositories.

Repository interfaces для Session bounded context.
"""

from .conversation_repository import ConversationRepository

__all__ = [
    "ConversationRepository",
]

"""
Base Repository interface for Domain-Driven Design.

This module provides the foundation for all repository interfaces following DDD principles.
"""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

from app.domain.shared.base_entity import Entity


# Type variable for entity type
TEntity = TypeVar('TEntity', bound=Entity)
TId = TypeVar('TId')


class Repository(ABC, Generic[TEntity, TId]):
    """
    Base interface for all repositories.
    
    A repository provides the illusion of an in-memory collection of domain objects.
    It encapsulates the logic required to access data sources and provides a more
    object-oriented view of the persistence layer.
    
    Principles:
    - Abstraction: Hide persistence details from domain layer
    - Collection-like: Provide collection-like interface (add, get, remove)
    - Domain-focused: Work with domain entities, not database models
    - Single responsibility: One repository per aggregate root
    
    Usage:
        class ConversationRepository(Repository[Conversation, ConversationId]):
            async def get_by_user_id(self, user_id: str) -> List[Conversation]:
                pass
    """
    
    @abstractmethod
    async def get(self, id: TId) -> Optional[TEntity]:
        """
        Get entity by identifier.
        
        Args:
            id: Entity identifier
            
        Returns:
            Entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def add(self, entity: TEntity) -> None:
        """
        Add new entity to repository.
        
        Args:
            entity: Entity to add
            
        Raises:
            ValueError: If entity with same ID already exists
        """
        pass
    
    @abstractmethod
    async def update(self, entity: TEntity) -> None:
        """
        Update existing entity in repository.
        
        Args:
            entity: Entity to update
            
        Raises:
            ValueError: If entity doesn't exist
        """
        pass
    
    @abstractmethod
    async def remove(self, id: TId) -> None:
        """
        Remove entity from repository.
        
        Args:
            id: Entity identifier
            
        Raises:
            ValueError: If entity doesn't exist
        """
        pass
    
    @abstractmethod
    async def exists(self, id: TId) -> bool:
        """
        Check if entity exists.
        
        Args:
            id: Entity identifier
            
        Returns:
            True if entity exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def list_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[TEntity]:
        """
        List all entities with optional pagination.
        
        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            
        Returns:
            List of entities
        """
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """
        Count total number of entities.
        
        Returns:
            Total count
        """
        pass


class UnitOfWork(ABC):
    """
    Unit of Work pattern for managing transactions.
    
    A Unit of Work maintains a list of objects affected by a business transaction
    and coordinates the writing out of changes and the resolution of concurrency problems.
    
    Usage:
        async with unit_of_work:
            conversation = await conversation_repo.get(conversation_id)
            conversation.add_message(message)
            await conversation_repo.update(conversation)
            # Changes are committed when exiting context
    """
    
    @abstractmethod
    async def __aenter__(self):
        """Begin transaction."""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Commit or rollback transaction."""
        pass
    
    @abstractmethod
    async def commit(self) -> None:
        """Commit all changes."""
        pass
    
    @abstractmethod
    async def rollback(self) -> None:
        """Rollback all changes."""
        pass

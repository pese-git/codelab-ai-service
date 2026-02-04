"""
Shared Kernel for Domain Layer.

This module contains base classes and interfaces shared across all bounded contexts.
Following Domain-Driven Design principles, this is the "Shared Kernel" - a subset
of the domain model that is shared between multiple bounded contexts.

Exports:
    - Entity: Base class for all domain entities
    - ValueObject: Base class for all value objects
    - DomainEvent: Base class for all domain events
    - Repository: Base interface for all repositories
    - UnitOfWork: Interface for transaction management
"""

from app.domain.shared.base_entity import Entity
from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.repository import Repository, UnitOfWork
from app.domain.shared.value_object import ValueObject

__all__ = [
    "Entity",
    "ValueObject",
    "DomainEvent",
    "Repository",
    "UnitOfWork",
]

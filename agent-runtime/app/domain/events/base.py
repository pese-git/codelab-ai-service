"""
Базовый класс для доменных событий.

Доменное событие (Domain Event) - это запись о том, что произошло
важное бизнес-событие в системе. События неизменяемы и описывают
факты из прошлого.
"""

import uuid
from abc import ABC
from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel, Field


class DomainEvent(BaseModel, ABC):
    """
    Базовое доменное событие.
    
    Доменные события описывают важные бизнес-события, которые произошли
    в системе. Они неизменяемы (immutable) и всегда описывают прошлое.
    
    Атрибуты:
        event_id: Уникальный идентификатор события
        occurred_at: Время возникновения события (UTC)
        aggregate_id: ID агрегата, с которым связано событие
        event_version: Версия события (для эволюции схемы)
    
    Пример:
        >>> class UserCreated(DomainEvent):
        ...     user_id: str
        ...     email: str
        >>> 
        >>> event = UserCreated(
        ...     aggregate_id="user-123",
        ...     user_id="user-123",
        ...     email="john@example.com"
        ... )
        >>> event.occurred_at
        datetime.datetime(2026, 1, 18, ...)
    """
    
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Уникальный идентификатор события"
    )
    
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время возникновения события (UTC)"
    )
    
    aggregate_id: str = Field(
        ...,
        description="ID агрегата (сущности), с которым связано событие"
    )
    
    event_version: int = Field(
        default=1,
        description="Версия события (для эволюции схемы)"
    )
    
    class Config:
        """Конфигурация Pydantic модели"""
        # События неизменяемы
        frozen = True
        # Кастомные JSON энкодеры
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать событие в словарь.
        
        Полезно для сериализации и логирования.
        
        Returns:
            Словарь с данными события
            
        Пример:
            >>> event = UserCreated(aggregate_id="user-123", ...)
            >>> data = event.to_dict()
            >>> data['event_id']
            'a1b2c3d4-...'
        """
        return self.dict()
    
    def get_event_name(self) -> str:
        """
        Получить имя события.
        
        Возвращает имя класса события, которое используется
        для идентификации типа события.
        
        Returns:
            Имя класса события
            
        Пример:
            >>> event = UserCreated(aggregate_id="user-123", ...)
            >>> event.get_event_name()
            'UserCreated'
        """
        return self.__class__.__name__
    
    def __repr__(self) -> str:
        """
        Строковое представление события.
        
        Returns:
            Строка с именем события и aggregate_id
        """
        return (
            f"<{self.get_event_name()}("
            f"event_id='{self.event_id}', "
            f"aggregate_id='{self.aggregate_id}', "
            f"occurred_at='{self.occurred_at.isoformat()}'"
            f")>"
        )

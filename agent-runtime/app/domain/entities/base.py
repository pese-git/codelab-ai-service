"""
Базовый класс для доменных сущностей.

Сущность (Entity) - это объект, который имеет уникальную идентичность
и жизненный цикл. Две сущности с одинаковым ID считаются одной и той же сущностью,
даже если их атрибуты различаются.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class Entity(BaseModel):
    """
    Базовая доменная сущность.
    
    Все доменные сущности должны наследоваться от этого класса.
    Предоставляет базовые поля для отслеживания жизненного цикла сущности.
    
    Атрибуты:
        id: Уникальный идентификатор сущности
        created_at: Время создания сущности (UTC)
        updated_at: Время последнего обновления сущности (UTC)
    
    Пример:
        >>> class User(Entity):
        ...     name: str
        ...     email: str
        >>> 
        >>> user = User(id="user-1", name="John", email="john@example.com")
        >>> user.id
        'user-1'
    """
    
    id: str = Field(
        ...,
        description="Уникальный идентификатор сущности"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время создания сущности (UTC)"
    )
    
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Время последнего обновления сущности (UTC)"
    )
    
    class Config:
        """Конфигурация Pydantic модели"""
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def mark_updated(self) -> None:
        """
        Отметить сущность как обновленную.
        
        Устанавливает текущее время в поле updated_at.
        Должен вызываться при любом изменении состояния сущности.
        
        Пример:
            >>> user = User(id="user-1", name="John", email="john@example.com")
            >>> user.name = "Jane"
            >>> user.mark_updated()
            >>> user.updated_at is not None
            True
        """
        self.updated_at = datetime.now(timezone.utc)
    
    def __eq__(self, other: object) -> bool:
        """
        Сравнение сущностей по ID.
        
        Две сущности считаются равными, если у них одинаковый ID,
        независимо от значений других атрибутов.
        
        Args:
            other: Другая сущность для сравнения
            
        Returns:
            True если ID совпадают, False иначе
        """
        if not isinstance(other, Entity):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """
        Хеш сущности на основе ID.
        
        Позволяет использовать сущности в множествах и словарях.
        
        Returns:
            Хеш значение на основе ID
        """
        return hash(self.id)
    
    def __repr__(self) -> str:
        """
        Строковое представление сущности.
        
        Returns:
            Строка с именем класса и ID
        """
        return f"<{self.__class__.__name__}(id='{self.id}')>"

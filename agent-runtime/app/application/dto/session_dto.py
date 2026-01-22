"""
Data Transfer Objects для сессий.

DTO изолируют внутреннюю структуру доменных сущностей
от внешнего API и других слоев.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from ...domain.entities.session import Session
from .message_dto import MessageDTO


class SessionDTO(BaseModel):
    """
    DTO для полной информации о сессии.
    
    Используется для передачи данных сессии между слоями.
    Содержит все детали включая сообщения.
    
    Атрибуты:
        id: ID сессии
        title: Заголовок сессии
        description: Описание сессии
        message_count: Количество сообщений
        messages: Список сообщений (опционально)
        last_activity: Время последней активности
        is_active: Флаг активности
        created_at: Время создания
        duration_seconds: Длительность сессии в секундах
    
    Пример:
        >>> dto = SessionDTO(
        ...     id="session-1",
        ...     title="Создание виджета",
        ...     message_count=5,
        ...     is_active=True,
        ...     last_activity=datetime.now(),
        ...     created_at=datetime.now()
        ... )
    """
    
    id: str = Field(description="ID сессии")
    title: Optional[str] = Field(default=None, description="Заголовок сессии")
    description: Optional[str] = Field(default=None, description="Описание сессии")
    message_count: int = Field(description="Количество сообщений")
    messages: Optional[List[MessageDTO]] = Field(
        default=None,
        description="Список сообщений (опционально)"
    )
    last_activity: datetime = Field(description="Время последней активности")
    is_active: bool = Field(description="Флаг активности сессии")
    created_at: datetime = Field(description="Время создания сессии")
    duration_seconds: float = Field(description="Длительность сессии в секундах")
    
    @classmethod
    def from_entity(
        cls,
        session: Session,
        include_messages: bool = False
    ) -> "SessionDTO":
        """
        Создать DTO из доменной сущности.
        
        Args:
            session: Доменная сущность сессии
            include_messages: Включить ли сообщения в DTO
            
        Returns:
            DTO сессии
            
        Пример:
            >>> session = Session(id="session-1", ...)
            >>> dto = SessionDTO.from_entity(session, include_messages=True)
        """
        messages_dto = None
        if include_messages:
            messages_dto = [
                MessageDTO.from_entity(msg)
                for msg in session.messages
            ]
        
        return cls(
            id=session.id,
            title=session.title,
            description=session.description,
            message_count=session.get_message_count(),
            messages=messages_dto,
            last_activity=session.last_activity,
            is_active=session.is_active,
            created_at=session.created_at,
            duration_seconds=session.get_duration_seconds()
        )


class SessionListItemDTO(BaseModel):
    """
    DTO для элемента списка сессий.
    
    Облегченная версия SessionDTO для списков.
    Не содержит сообщения для экономии памяти и трафика.
    
    Атрибуты:
        id: ID сессии
        title: Заголовок сессии
        message_count: Количество сообщений
        last_activity: Время последней активности
        is_active: Флаг активности
        current_agent: Текущий агент (опционально)
    
    Пример:
        >>> dto = SessionListItemDTO(
        ...     id="session-1",
        ...     title="Создание виджета",
        ...     message_count=5,
        ...     last_activity=datetime.now(),
        ...     is_active=True
        ... )
    """
    
    id: str = Field(description="ID сессии")
    title: Optional[str] = Field(default=None, description="Заголовок сессии")
    message_count: int = Field(description="Количество сообщений")
    last_activity: datetime = Field(description="Время последней активности")
    is_active: bool = Field(description="Флаг активности")
    current_agent: Optional[str] = Field(
        default=None,
        description="Текущий агент сессии"
    )
    
    @classmethod
    def from_entity(
        cls,
        session: Session,
        current_agent: Optional[str] = None
    ) -> "SessionListItemDTO":
        """
        Создать DTO из доменной сущности.
        
        Args:
            session: Доменная сущность сессии
            current_agent: Текущий агент (опционально)
            
        Returns:
            DTO элемента списка
            
        Пример:
            >>> session = Session(id="session-1", ...)
            >>> dto = SessionListItemDTO.from_entity(session, current_agent="coder")
        """
        return cls(
            id=session.id,
            title=session.title,
            message_count=session.get_message_count(),
            last_activity=session.last_activity,
            is_active=session.is_active,
            current_agent=current_agent
        )

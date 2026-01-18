"""
Запрос получения сессии.

Получает полную информацию о сессии по ID.
"""

from typing import Optional
from pydantic import Field

from .base import Query, QueryHandler
from ...domain.repositories.session_repository import SessionRepository
from ..dto.session_dto import SessionDTO


class GetSessionQuery(Query):
    """
    Запрос получения сессии по ID.
    
    Атрибуты:
        session_id: ID сессии
        include_messages: Включить ли сообщения в результат
    
    Пример:
        >>> query = GetSessionQuery(
        ...     session_id="session-1",
        ...     include_messages=True
        ... )
    """
    
    session_id: str = Field(description="ID сессии")
    include_messages: bool = Field(
        default=False,
        description="Включить ли сообщения в результат"
    )


class GetSessionHandler(QueryHandler[Optional[SessionDTO]]):
    """
    Обработчик запроса получения сессии.
    
    Получает сессию из репозитория и преобразует в DTO.
    
    Атрибуты:
        _repository: Репозиторий сессий
    
    Пример:
        >>> handler = GetSessionHandler(repository)
        >>> query = GetSessionQuery(session_id="session-1")
        >>> dto = await handler.handle(query)
        >>> if dto:
        ...     print(f"Found session: {dto.title}")
    """
    
    def __init__(self, repository: SessionRepository):
        """
        Инициализация обработчика.
        
        Args:
            repository: Репозиторий сессий
        """
        self._repository = repository
    
    async def handle(self, query: GetSessionQuery) -> Optional[SessionDTO]:
        """
        Обработать запрос получения сессии.
        
        Args:
            query: Запрос получения сессии
            
        Returns:
            DTO сессии если найдена, None иначе
            
        Пример:
            >>> query = GetSessionQuery(session_id="session-1", include_messages=True)
            >>> dto = await handler.handle(query)
        """
        # Получить сессию из репозитория
        session = await self._repository.find_by_id(query.session_id)
        
        if not session:
            return None
        
        # Преобразовать в DTO
        return SessionDTO.from_entity(
            session,
            include_messages=query.include_messages
        )

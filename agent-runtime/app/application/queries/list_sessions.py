"""
Запрос списка сессий.

Получает список сессий с пагинацией.
"""

from typing import List
from pydantic import Field

from .base import Query, QueryHandler
from ...domain.repositories.session_repository import SessionRepository
from ...domain.repositories.agent_context_repository import AgentContextRepository
from ..dto.session_dto import SessionListItemDTO


class ListSessionsQuery(Query):
    """
    Запрос списка сессий.
    
    Атрибуты:
        limit: Максимальное количество сессий
        offset: Смещение от начала списка
        active_only: Только активные сессии
    
    Пример:
        >>> # Первая страница (10 сессий)
        >>> query = ListSessionsQuery(limit=10, offset=0)
        >>> 
        >>> # Вторая страница
        >>> query = ListSessionsQuery(limit=10, offset=10)
        >>> 
        >>> # Только активные
        >>> query = ListSessionsQuery(active_only=True)
    """
    
    limit: int = Field(default=100, ge=1, le=1000, description="Максимальное количество сессий")
    offset: int = Field(default=0, ge=0, description="Смещение от начала списка")
    active_only: bool = Field(default=True, description="Только активные сессии")


class ListSessionsHandler(QueryHandler[List[SessionListItemDTO]]):
    """
    Обработчик запроса списка сессий.
    
    Получает список сессий из репозитория и преобразует в DTO.
    Также получает информацию о текущих агентах для каждой сессии.
    
    Атрибуты:
        _session_repository: Репозиторий сессий
        _context_repository: Репозиторий контекстов агентов
    
    Пример:
        >>> handler = ListSessionsHandler(session_repo, context_repo)
        >>> query = ListSessionsQuery(limit=10)
        >>> sessions = await handler.handle(query)
        >>> for session in sessions:
        ...     print(f"{session.title}: {session.current_agent}")
    """
    
    def __init__(
        self,
        session_repository: SessionRepository,
        context_repository: AgentContextRepository
    ):
        """
        Инициализация обработчика.
        
        Args:
            session_repository: Репозиторий сессий
            context_repository: Репозиторий контекстов агентов
        """
        self._session_repository = session_repository
        self._context_repository = context_repository
    
    async def handle(self, query: ListSessionsQuery) -> List[SessionListItemDTO]:
        """
        Обработать запрос списка сессий.
        
        Args:
            query: Запрос списка сессий
            
        Returns:
            Список DTO сессий
            
        Пример:
            >>> query = ListSessionsQuery(limit=10, active_only=True)
            >>> sessions = await handler.handle(query)
        """
        # Получить сессии из репозитория
        if query.active_only:
            sessions = await self._session_repository.find_active(
                limit=query.limit,
                offset=query.offset
            )
        else:
            sessions = await self._session_repository.list(
                limit=query.limit,
                offset=query.offset
            )
        
        # Преобразовать в DTO с информацией о текущих агентах
        result = []
        for session in sessions:
            # Получить текущего агента для сессии
            context = await self._context_repository.find_by_session_id(session.id)
            current_agent = context.current_agent.value if context else None
            
            # Создать DTO
            dto = SessionListItemDTO.from_entity(
                session,
                current_agent=current_agent
            )
            result.append(dto)
        
        return result

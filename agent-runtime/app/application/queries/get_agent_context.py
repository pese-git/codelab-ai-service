"""
Запрос получения контекста агента.

Получает информацию о текущем агенте и истории переключений для сессии.
"""

from typing import Optional
from pydantic import Field

from .base import Query, QueryHandler
from ...domain.repositories.agent_context_repository import AgentContextRepository
from ..dto.agent_context_dto import AgentContextDTO


class GetAgentContextQuery(Query):
    """
    Запрос получения контекста агента для сессии.
    
    Атрибуты:
        session_id: ID сессии
        include_history: Включить ли историю переключений
    
    Пример:
        >>> query = GetAgentContextQuery(
        ...     session_id="session-1",
        ...     include_history=True
        ... )
    """
    
    session_id: str = Field(description="ID сессии")
    include_history: bool = Field(
        default=False,
        description="Включить ли историю переключений"
    )


class GetAgentContextHandler(QueryHandler[Optional[AgentContextDTO]]):
    """
    Обработчик запроса получения контекста агента.
    
    Получает контекст из репозитория и преобразует в DTO.
    
    Атрибуты:
        _repository: Репозиторий контекстов агентов
    
    Пример:
        >>> handler = GetAgentContextHandler(repository)
        >>> query = GetAgentContextQuery(session_id="session-1")
        >>> dto = await handler.handle(query)
        >>> if dto:
        ...     print(f"Current agent: {dto.current_agent}")
    """
    
    def __init__(self, repository: AgentContextRepository):
        """
        Инициализация обработчика.
        
        Args:
            repository: Репозиторий контекстов агентов
        """
        self._repository = repository
    
    async def handle(self, query: GetAgentContextQuery) -> Optional[AgentContextDTO]:
        """
        Обработать запрос получения контекста агента.
        
        Args:
            query: Запрос получения контекста
            
        Returns:
            DTO контекста если найден, None иначе
            
        Пример:
            >>> query = GetAgentContextQuery(
            ...     session_id="session-1",
            ...     include_history=True
            ... )
            >>> dto = await handler.handle(query)
        """
        # Получить контекст из репозитория
        context = await self._repository.find_by_session_id(query.session_id)
        
        if not context:
            return None
        
        # Преобразовать в DTO
        return AgentContextDTO.from_entity(
            context,
            include_history=query.include_history
        )

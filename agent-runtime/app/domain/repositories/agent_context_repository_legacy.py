"""
Интерфейс репозитория контекстов агентов.

Определяет контракт для работы с контекстами агентов.
"""

from abc import abstractmethod
from typing import List, Optional

from .base import Repository
from ..entities.agent_context import AgentContext, AgentType


class AgentContextRepository(Repository[AgentContext]):
    """
    Интерфейс репозитория для контекстов агентов.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с контекстами агентов.
    
    Пример:
        >>> class AgentContextRepositoryImpl(AgentContextRepository):
        ...     async def find_by_session_id(self, session_id: str):
        ...         # Реализация поиска контекста
        ...         pass
    """
    
    @abstractmethod
    async def find_by_session_id(self, session_id: str) -> Optional[AgentContext]:
        """
        Найти контекст агента по ID сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Контекст агента если найден, None иначе
            
        Пример:
            >>> context = await repository.find_by_session_id("session-123")
            >>> if context:
            ...     print(f"Current agent: {context.current_agent.value}")
        """
        pass
    
    @abstractmethod
    async def find_by_agent_type(
        self,
        agent_type: AgentType,
        limit: int = 100
    ) -> List[AgentContext]:
        """
        Найти все контексты с указанным текущим агентом.
        
        Полезно для аналитики использования агентов.
        
        Args:
            agent_type: Тип агента
            limit: Максимальное количество контекстов
            
        Returns:
            Список контекстов с указанным агентом
            
        Пример:
            >>> coder_contexts = await repository.find_by_agent_type(
            ...     agent_type=AgentType.CODER,
            ...     limit=50
            ... )
            >>> print(f"Found {len(coder_contexts)} sessions using Coder")
        """
        pass
    
    @abstractmethod
    async def find_with_many_switches(
        self,
        min_switches: int = 5,
        limit: int = 100
    ) -> List[AgentContext]:
        """
        Найти контексты с большим количеством переключений.
        
        Полезно для выявления проблемных сессий или
        анализа паттернов использования.
        
        Args:
            min_switches: Минимальное количество переключений
            limit: Максимальное количество контекстов
            
        Returns:
            Список контекстов с >= min_switches переключений
            
        Пример:
            >>> problematic = await repository.find_with_many_switches(
            ...     min_switches=10
            ... )
            >>> for ctx in problematic:
            ...     print(f"Session {ctx.session_id}: {ctx.switch_count} switches")
        """
        pass
    
    @abstractmethod
    async def get_agent_usage_stats(self) -> dict:
        """
        Получить статистику использования агентов.
        
        Returns:
            Словарь с количеством сессий для каждого агента
            
        Пример:
            >>> stats = await repository.get_agent_usage_stats()
            >>> stats
            {
                'orchestrator': 100,
                'coder': 45,
                'architect': 20,
                'debug': 15,
                'ask': 30
            }
        """
        pass

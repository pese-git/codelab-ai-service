"""
AgentRepository Interface.

Интерфейс репозитория для работы с агентами.
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any

from ...shared.repository import Repository
from ..entities.agent import Agent
from ..value_objects.agent_id import AgentId
from ..value_objects.agent_capabilities import AgentType


class AgentRepository(Repository[Agent]):
    """
    Интерфейс репозитория для агентов.
    
    Расширяет базовый Repository дополнительными методами,
    специфичными для работы с агентами.
    
    Пример:
        >>> class AgentRepositoryImpl(AgentRepository):
        ...     async def find_by_session_id(self, session_id: str):
        ...         # Реализация поиска агента
        ...         pass
    """
    
    @abstractmethod
    async def find_by_session_id(self, session_id: str) -> Optional[Agent]:
        """
        Найти агента по ID сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Agent если найден, None иначе
            
        Пример:
            >>> agent = await repository.find_by_session_id("session-123")
            >>> if agent:
            ...     print(f"Current type: {agent.current_type.value}")
        """
        pass
    
    @abstractmethod
    async def find_by_agent_type(
        self,
        agent_type: AgentType,
        limit: int = 100
    ) -> List[Agent]:
        """
        Найти всех агентов с указанным текущим типом.
        
        Полезно для аналитики использования агентов.
        
        Args:
            agent_type: Тип агента
            limit: Максимальное количество агентов
            
        Returns:
            Список агентов с указанным типом
            
        Пример:
            >>> coder_agents = await repository.find_by_agent_type(
            ...     agent_type=AgentType.CODER,
            ...     limit=50
            ... )
            >>> print(f"Found {len(coder_agents)} coder agents")
        """
        pass
    
    @abstractmethod
    async def find_with_many_switches(
        self,
        min_switches: int = 5,
        limit: int = 100
    ) -> List[Agent]:
        """
        Найти агентов с большим количеством переключений.
        
        Полезно для выявления проблемных сессий или
        анализа паттернов использования.
        
        Args:
            min_switches: Минимальное количество переключений
            limit: Максимальное количество агентов
            
        Returns:
            Список агентов с >= min_switches переключений
            
        Пример:
            >>> problematic = await repository.find_with_many_switches(
            ...     min_switches=10
            ... )
            >>> for agent in problematic:
            ...     print(f"Session {agent.session_id}: {agent.switch_count} switches")
        """
        pass
    
    @abstractmethod
    async def get_agent_usage_stats(self) -> Dict[str, int]:
        """
        Получить статистику использования агентов.
        
        Returns:
            Словарь с количеством сессий для каждого типа агента
            
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
    
    @abstractmethod
    async def get_switch_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику переключений агентов.
        
        Returns:
            Словарь со статистикой переключений
            
        Пример:
            >>> stats = await repository.get_switch_statistics()
            >>> stats
            {
                'total_switches': 500,
                'avg_switches_per_session': 2.5,
                'max_switches': 15,
                'sessions_with_switches': 200
            }
        """
        pass
    
    @abstractmethod
    async def find_by_metadata(
        self,
        key: str,
        value: Any,
        limit: int = 100
    ) -> List[Agent]:
        """
        Найти агентов по метаданным.
        
        Args:
            key: Ключ метаданных
            value: Значение метаданных
            limit: Максимальное количество агентов
            
        Returns:
            Список агентов с указанными метаданными
            
        Пример:
            >>> agents = await repository.find_by_metadata(
            ...     key="user_preference",
            ...     value="verbose"
            ... )
        """
        pass
    
    @abstractmethod
    async def delete_by_session_id(self, session_id: str) -> bool:
        """
        Удалить агента по ID сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если агент был удален
            
        Пример:
            >>> deleted = await repository.delete_by_session_id("session-123")
            >>> if deleted:
            ...     print("Agent deleted successfully")
        """
        pass
    
    @abstractmethod
    async def count_by_type(self, agent_type: AgentType) -> int:
        """
        Подсчитать количество агентов указанного типа.
        
        Args:
            agent_type: Тип агента
            
        Returns:
            Количество агентов
            
        Пример:
            >>> count = await repository.count_by_type(AgentType.CODER)
            >>> print(f"Coder agents: {count}")
        """
        pass
    
    @abstractmethod
    async def get_recent_switches(
        self,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получить последние переключения агентов.
        
        Args:
            limit: Максимальное количество записей
            
        Returns:
            Список словарей с информацией о переключениях
            
        Пример:
            >>> switches = await repository.get_recent_switches(limit=10)
            >>> for switch in switches:
            ...     print(f"{switch['from_type']} -> {switch['to_type']}")
        """
        pass

"""
Реализация AgentRepository с использованием SQLAlchemy.

Конкретная реализация интерфейса AgentRepository для работы с БД.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from ....domain.agent_context.repositories import AgentRepository
from ....domain.agent_context.entities import Agent
from ....domain.agent_context.value_objects import AgentId, AgentType
from ..models import AgentContextModel, AgentSwitchModel
from ..mappers import AgentMapper

logger = logging.getLogger("agent-runtime.infrastructure.agent_repository")


class AgentRepositoryImpl(AgentRepository):
    """
    Реализация репозитория агентов для SQLAlchemy.
    
    Использует AgentMapper для преобразования между
    доменными сущностями и моделями БД.
    
    Атрибуты:
        _db: Сессия БД SQLAlchemy
        _mapper: Mapper для преобразования данных
    
    Пример:
        >>> repo = AgentRepositoryImpl(db_session)
        >>> agent = await repo.find_by_session_id("session-123")
    """
    
    def __init__(self, db: AsyncSession):
        """
        Инициализировать репозиторий.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
        self._mapper = AgentMapper()
    
    async def find_by_id(self, agent_id: AgentId) -> Optional[Agent]:
        """
        Найти агента по ID.
        
        Args:
            agent_id: ID агента
            
        Returns:
            Agent или None если не найден
        """
        result = await self._db.execute(
            select(AgentContextModel).where(
                AgentContextModel.id == agent_id.value
            )
        )
        model = result.scalar_one_or_none()
        
        if not model:
            logger.debug(f"Agent {agent_id.value} not found")
            return None
        
        agent = await self._mapper.to_entity(model, self._db)
        logger.debug(f"Found agent {agent_id.value}")
        return agent
    
    async def find_by_session_id(self, session_id: str) -> Optional[Agent]:
        """
        Найти агента по ID сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Agent если найден, None иначе
        """
        result = await self._db.execute(
            select(AgentContextModel).where(
                AgentContextModel.session_db_id == session_id
            )
        )
        model = result.scalar_one_or_none()
        
        if not model:
            logger.debug(f"Agent for session {session_id} not found")
            return None
        
        agent = await self._mapper.to_entity(model, self._db)
        logger.debug(f"Found agent for session {session_id}")
        return agent
    
    async def find_by_agent_type(
        self,
        agent_type: AgentType,
        limit: int = 100
    ) -> List[Agent]:
        """
        Найти всех агентов с указанным текущим типом.
        
        Args:
            agent_type: Тип агента
            limit: Максимальное количество агентов
            
        Returns:
            Список агентов с указанным типом
        """
        result = await self._db.execute(
            select(AgentContextModel)
            .where(AgentContextModel.current_agent == agent_type.value)
            .order_by(AgentContextModel.updated_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        
        agents = []
        for model in models:
            agent = await self._mapper.to_entity(model, self._db, load_switches=False)
            agents.append(agent)
        
        logger.debug(f"Found {len(agents)} agents of type {agent_type.value}")
        return agents
    
    async def find_with_many_switches(
        self,
        min_switches: int = 5,
        limit: int = 100
    ) -> List[Agent]:
        """
        Найти агентов с большим количеством переключений.
        
        Args:
            min_switches: Минимальное количество переключений
            limit: Максимальное количество агентов
            
        Returns:
            Список агентов с >= min_switches переключений
        """
        result = await self._db.execute(
            select(AgentContextModel)
            .where(AgentContextModel.switch_count >= min_switches)
            .order_by(AgentContextModel.switch_count.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        
        agents = []
        for model in models:
            agent = await self._mapper.to_entity(model, self._db)
            agents.append(agent)
        
        logger.debug(f"Found {len(agents)} agents with >= {min_switches} switches")
        return agents
    
    async def get_agent_usage_stats(self) -> Dict[str, int]:
        """
        Получить статистику использования агентов.
        
        Returns:
            Словарь с количеством сессий для каждого типа агента
        """
        result = await self._db.execute(
            select(
                AgentContextModel.current_agent,
                func.count(AgentContextModel.id).label('count')
            )
            .group_by(AgentContextModel.current_agent)
        )
        
        stats = {}
        for row in result:
            stats[row.current_agent] = row.count
        
        logger.debug(f"Agent usage stats: {stats}")
        return stats
    
    async def get_switch_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику переключений агентов.
        
        Returns:
            Словарь со статистикой переключений
        """
        # Общее количество переключений
        total_switches_result = await self._db.execute(
            select(func.sum(AgentContextModel.switch_count))
        )
        total_switches = total_switches_result.scalar() or 0
        
        # Количество сессий с переключениями
        sessions_with_switches_result = await self._db.execute(
            select(func.count(AgentContextModel.id))
            .where(AgentContextModel.switch_count > 0)
        )
        sessions_with_switches = sessions_with_switches_result.scalar() or 0
        
        # Среднее количество переключений
        avg_switches_result = await self._db.execute(
            select(func.avg(AgentContextModel.switch_count))
        )
        avg_switches = avg_switches_result.scalar() or 0.0
        
        # Максимальное количество переключений
        max_switches_result = await self._db.execute(
            select(func.max(AgentContextModel.switch_count))
        )
        max_switches = max_switches_result.scalar() or 0
        
        stats = {
            'total_switches': int(total_switches),
            'avg_switches_per_session': float(avg_switches),
            'max_switches': int(max_switches),
            'sessions_with_switches': int(sessions_with_switches)
        }
        
        logger.debug(f"Switch statistics: {stats}")
        return stats
    
    async def find_by_metadata(
        self,
        key: str,
        value: Any,
        limit: int = 100
    ) -> List[Agent]:
        """
        Найти агентов по метаданным.
        
        Note: Требует JSON query capabilities в SQLAlchemy.
        Текущая реализация загружает все агенты и фильтрует в памяти.
        
        Args:
            key: Ключ метаданных
            value: Значение метаданных
            limit: Максимальное количество агентов
            
        Returns:
            Список агентов с указанными метаданными
        """
        # TODO: Оптимизировать с использованием JSON queries
        result = await self._db.execute(
            select(AgentContextModel)
            .order_by(AgentContextModel.updated_at.desc())
            .limit(limit * 2)  # Загружаем больше для фильтрации
        )
        models = result.scalars().all()
        
        agents = []
        for model in models:
            agent = await self._mapper.to_entity(model, self._db, load_switches=False)
            if agent.get_metadata(key) == value:
                agents.append(agent)
                if len(agents) >= limit:
                    break
        
        logger.debug(f"Found {len(agents)} agents with metadata {key}={value}")
        return agents
    
    async def save(self, agent: Agent) -> None:
        """
        Сохранить агента.
        
        Создает нового или обновляет существующего.
        
        Args:
            agent: Agent для сохранения
        """
        await self._mapper.to_model(agent, self._db)
        await self._db.flush()
        logger.debug(f"Saved agent {agent.id}")
    
    async def delete(self, agent_id: AgentId) -> bool:
        """
        Удалить агента по ID.
        
        Args:
            agent_id: ID агента
            
        Returns:
            True если агент был удален
        """
        result = await self._db.execute(
            delete(AgentContextModel).where(
                AgentContextModel.id == agent_id.value
            )
        )
        deleted = result.rowcount > 0
        
        if deleted:
            logger.info(f"Deleted agent {agent_id.value}")
        else:
            logger.debug(f"Agent {agent_id.value} not found for deletion")
        
        return deleted
    
    async def delete_by_session_id(self, session_id: str) -> bool:
        """
        Удалить агента по ID сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если агент был удален
        """
        result = await self._db.execute(
            delete(AgentContextModel).where(
                AgentContextModel.session_db_id == session_id
            )
        )
        deleted = result.rowcount > 0
        
        if deleted:
            logger.info(f"Deleted agent for session {session_id}")
        else:
            logger.debug(f"Agent for session {session_id} not found for deletion")
        
        return deleted
    
    async def count_by_type(self, agent_type: AgentType) -> int:
        """
        Подсчитать количество агентов указанного типа.
        
        Args:
            agent_type: Тип агента
            
        Returns:
            Количество агентов
        """
        result = await self._db.execute(
            select(func.count(AgentContextModel.id))
            .where(AgentContextModel.current_agent == agent_type.value)
        )
        count = result.scalar()
        logger.debug(f"Found {count} agents of type {agent_type.value}")
        return count
    
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
        """
        result = await self._db.execute(
            select(AgentSwitchModel)
            .order_by(AgentSwitchModel.switched_at.desc())
            .limit(limit)
        )
        switch_models = result.scalars().all()
        
        switches = [model.to_dict() for model in switch_models]
        logger.debug(f"Retrieved {len(switches)} recent switches")
        return switches
    
    async def exists(self, agent_id: AgentId) -> bool:
        """
        Проверить существование агента.
        
        Args:
            agent_id: ID для проверки
            
        Returns:
            True если существует
        """
        result = await self._db.execute(
            select(func.count(AgentContextModel.id))
            .where(AgentContextModel.id == agent_id.value)
        )
        count = result.scalar()
        return count > 0
    
    # Базовые методы Repository
    
    async def get(self, id: AgentId) -> Optional[Agent]:
        """Alias для find_by_id (базовый метод Repository)."""
        return await self.find_by_id(id)
    
    async def add(self, entity: Agent) -> None:
        """Alias для save (базовый метод Repository)."""
        await self.save(entity)
    
    async def update(self, entity: Agent) -> None:
        """Alias для save (базовый метод Repository)."""
        await self.save(entity)
    
    async def remove(self, id: AgentId) -> None:
        """Alias для delete (базовый метод Repository)."""
        await self.delete(id)
    
    async def list_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Agent]:
        """Получить всех агентов с пагинацией."""
        result = await self._db.execute(
            select(AgentContextModel)
            .order_by(AgentContextModel.updated_at.desc())
            .limit(limit if limit else 1000)
            .offset(offset if offset else 0)
        )
        models = result.scalars().all()
        
        agents = []
        for model in models:
            agent = await self._mapper.to_entity(model, self._db, load_switches=False)
            agents.append(agent)
        
        return agents
    
    async def count(self) -> int:
        """Подсчитать общее количество агентов."""
        result = await self._db.execute(
            select(func.count(AgentContextModel.id))
        )
        return result.scalar()

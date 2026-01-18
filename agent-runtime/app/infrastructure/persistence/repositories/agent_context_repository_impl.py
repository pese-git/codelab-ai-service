"""
Реализация репозитория контекстов агентов.

Конкретная реализация AgentContextRepository для работы с SQLAlchemy.
"""

import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ....domain.repositories.agent_context_repository import AgentContextRepository
from ....domain.entities.agent_context import AgentContext, AgentType
from ....core.errors import RepositoryError
from ..models import AgentContextModel, SessionModel
from ..mappers.agent_context_mapper import AgentContextMapper

logger = logging.getLogger("agent-runtime.infrastructure.agent_context_repository")


class AgentContextRepositoryImpl(AgentContextRepository):
    """
    Реализация репозитория контекстов агентов для SQLAlchemy.
    
    Использует AgentContextMapper для преобразования между
    доменными сущностями и моделями БД.
    
    Атрибуты:
        _db: Сессия БД
        _mapper: Маппер для преобразований
    
    Пример:
        >>> repository = AgentContextRepositoryImpl(db_session)
        >>> context = await repository.find_by_session_id("session-1")
    """
    
    def __init__(self, db: AsyncSession):
        """
        Инициализация репозитория.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
        self._mapper = AgentContextMapper()
    
    async def get(self, id: str) -> Optional[AgentContext]:
        """
        Получить контекст по ID.
        
        Args:
            id: ID контекста
            
        Returns:
            Контекст если найден, None иначе
        """
        try:
            result = await self._db.execute(
                select(AgentContextModel).where(AgentContextModel.id == id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return await self._mapper.to_entity(model, self._db, load_history=True)
            
        except Exception as e:
            logger.error(f"Error getting context {id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="get",
                entity_type="AgentContext",
                reason=str(e),
                details={"context_id": id}
            )
    
    async def save(self, entity: AgentContext) -> None:
        """
        Сохранить контекст агента.
        
        Args:
            entity: Доменная сущность контекста
            
        Raises:
            RepositoryError: При ошибке сохранения
        """
        try:
            await self._mapper.to_model(entity, self._db)
            await self._db.commit()
            logger.debug(f"Saved agent context {entity.id}")
        except Exception as e:
            await self._db.rollback()
            logger.error(f"Error saving context {entity.id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="save",
                entity_type="AgentContext",
                reason=str(e),
                details={"context_id": entity.id}
            )
    
    async def delete(self, id: str) -> bool:
        """
        Удалить контекст агента.
        
        Args:
            id: ID контекста
            
        Returns:
            True если удален, False если не найден
        """
        try:
            result = await self._db.execute(
                select(AgentContextModel).where(AgentContextModel.id == id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return False
            
            await self._db.delete(model)
            await self._db.commit()
            logger.info(f"Deleted agent context {id}")
            return True
            
        except Exception as e:
            await self._db.rollback()
            logger.error(f"Error deleting context {id}: {e}")
            raise RepositoryError(
                operation="delete",
                entity_type="AgentContext",
                reason=str(e),
                details={"context_id": id}
            )
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[AgentContext]:
        """
        Получить список контекстов с пагинацией.
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список контекстов
        """
        try:
            result = await self._db.execute(
                select(AgentContextModel)
                .order_by(AgentContextModel.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            models = result.scalars().all()
            
            contexts = []
            for model in models:
                context = await self._mapper.to_entity(
                    model,
                    self._db,
                    load_history=False
                )
                contexts.append(context)
            
            return contexts
            
        except Exception as e:
            logger.error(f"Error listing contexts: {e}")
            raise RepositoryError(
                operation="list",
                entity_type="AgentContext",
                reason=str(e)
            )
    
    async def exists(self, id: str) -> bool:
        """
        Проверить существование контекста.
        
        Args:
            id: ID контекста
            
        Returns:
            True если существует
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(AgentContextModel)
                .where(AgentContextModel.id == id)
            )
            count = result.scalar()
            return count > 0
        except Exception as e:
            logger.error(f"Error checking context existence {id}: {e}")
            return False
    
    async def count(self) -> int:
        """
        Подсчитать общее количество контекстов.
        
        Returns:
            Количество контекстов
        """
        try:
            result = await self._db.execute(
                select(func.count()).select_from(AgentContextModel)
            )
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting contexts: {e}")
            return 0
    
    async def find_by_session_id(self, session_id: str) -> Optional[AgentContext]:
        """
        Найти контекст по ID сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Контекст если найден, None иначе
        """
        try:
            # Найти сессию
            result = await self._db.execute(
                select(SessionModel).where(
                    SessionModel.id == session_id,
                    SessionModel.deleted_at.is_(None)
                )
            )
            session_model = result.scalar_one_or_none()
            
            if not session_model:
                return None
            
            # Найти контекст
            result = await self._db.execute(
                select(AgentContextModel).where(
                    AgentContextModel.session_db_id == session_model.id
                )
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return await self._mapper.to_entity(model, self._db, load_history=True)
            
        except Exception as e:
            logger.error(f"Error finding context by session {session_id}: {e}")
            raise RepositoryError(
                operation="find_by_session_id",
                entity_type="AgentContext",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def find_by_agent_type(
        self,
        agent_type: AgentType,
        limit: int = 100
    ) -> List[AgentContext]:
        """
        Найти контексты с указанным текущим агентом.
        
        Args:
            agent_type: Тип агента
            limit: Максимальное количество
            
        Returns:
            Список контекстов
        """
        try:
            result = await self._db.execute(
                select(AgentContextModel)
                .where(AgentContextModel.current_agent == agent_type.value)
                .order_by(AgentContextModel.updated_at.desc())
                .limit(limit)
            )
            models = result.scalars().all()
            
            contexts = []
            for model in models:
                context = await self._mapper.to_entity(
                    model,
                    self._db,
                    load_history=False
                )
                contexts.append(context)
            
            return contexts
            
        except Exception as e:
            logger.error(f"Error finding contexts by agent type: {e}")
            raise RepositoryError(
                operation="find_by_agent_type",
                entity_type="AgentContext",
                reason=str(e)
            )
    
    async def find_with_many_switches(
        self,
        min_switches: int = 5,
        limit: int = 100
    ) -> List[AgentContext]:
        """
        Найти контексты с большим количеством переключений.
        
        Args:
            min_switches: Минимальное количество переключений
            limit: Максимальное количество
            
        Returns:
            Список контекстов
        """
        try:
            result = await self._db.execute(
                select(AgentContextModel)
                .where(AgentContextModel.switch_count >= min_switches)
                .order_by(AgentContextModel.switch_count.desc())
                .limit(limit)
            )
            models = result.scalars().all()
            
            contexts = []
            for model in models:
                context = await self._mapper.to_entity(
                    model,
                    self._db,
                    load_history=True  # Загрузить историю для анализа
                )
                contexts.append(context)
            
            return contexts
            
        except Exception as e:
            logger.error(f"Error finding contexts with many switches: {e}")
            raise RepositoryError(
                operation="find_with_many_switches",
                entity_type="AgentContext",
                reason=str(e)
            )
    
    async def get_agent_usage_stats(self) -> dict:
        """
        Получить статистику использования агентов.
        
        Returns:
            Словарь с количеством сессий для каждого агента
        """
        try:
            result = await self._db.execute(
                select(
                    AgentContextModel.current_agent,
                    func.count(AgentContextModel.id).label('count')
                )
                .group_by(AgentContextModel.current_agent)
            )
            rows = result.all()
            
            stats = {row.current_agent: row.count for row in rows}
            
            # Добавить нулевые значения для агентов без сессий
            for agent_type in AgentType:
                if agent_type.value not in stats:
                    stats[agent_type.value] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting agent usage stats: {e}")
            return {}

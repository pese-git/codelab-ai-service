"""
Реализация репозитория сессий.

Конкретная реализация SessionRepository для работы с SQLAlchemy.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from ....domain.repositories.session_repository import SessionRepository
from ....domain.entities.session import Session
from ....core.errors import RepositoryError
from ..models import SessionModel, MessageModel
from ..mappers.session_mapper import SessionMapper

logger = logging.getLogger("agent-runtime.infrastructure.session_repository")


class SessionRepositoryImpl(SessionRepository):
    """
    Реализация репозитория сессий для SQLAlchemy.
    
    Использует SessionMapper для преобразования между
    доменными сущностями и моделями БД.
    
    Атрибуты:
        _db: Сессия БД
        _mapper: Маппер для преобразований
        _snapshots: In-memory хранилище snapshots (TODO: заменить на Redis)
    
    Пример:
        >>> repository = SessionRepositoryImpl(db_session)
        >>> session = await repository.find_by_id("session-1")
    """
    
    # Class-level хранилище snapshots (shared между instances)
    # TODO: Заменить на Redis для production
    _snapshots: Dict[str, Dict[str, Any]] = {}
    
    def __init__(self, db: AsyncSession):
        """
        Инициализация репозитория.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
        self._mapper = SessionMapper()
    
    async def get(self, id: str) -> Optional[Session]:
        """
        Получить сессию по ID.
        
        Args:
            id: ID сессии
            
        Returns:
            Сессия если найдена, None иначе
        """
        return await self.find_by_id(id)
    
    async def save(self, entity: Session) -> None:
        """
        Сохранить сессию.
        
        Args:
            entity: Доменная сущность сессии
            
        Raises:
            RepositoryError: При ошибке сохранения
        """
        try:
            await self._mapper.to_model(entity, self._db)
            await self._db.flush()  # Flush changes within transaction, don't commit
            logger.debug(f"Saved session {entity.id}")
        except Exception as e:
            logger.error(f"Error saving session {entity.id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="save",
                entity_type="Session",
                reason=str(e),
                details={"session_id": entity.id}
            )
    
    async def delete(self, id: str) -> bool:
        """
        Удалить сессию (soft delete).
        
        Args:
            id: ID сессии
            
        Returns:
            True если удалена, False если не найдена
        """
        try:
            result = await self._db.execute(
                select(SessionModel).where(SessionModel.id == id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return False
            
            # Soft delete
            model.deleted_at = datetime.now(timezone.utc)
            model.is_active = False
            
            await self._db.flush()  # Flush changes within transaction, don't commit
            logger.info(f"Soft deleted session {id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting session {id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="delete",
                entity_type="Session",
                reason=str(e),
                details={"session_id": id}
            )
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """
        Получить список сессий с пагинацией.
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список сессий
        """
        try:
            result = await self._db.execute(
                select(SessionModel)
                .where(SessionModel.deleted_at.is_(None))
                .order_by(SessionModel.last_activity.desc())
                .limit(limit)
                .offset(offset)
            )
            models = result.scalars().all()
            
            # Преобразовать в сущности
            sessions = []
            for model in models:
                session = await self._mapper.to_entity(
                    model,
                    self._db,
                    load_messages=False  # Не загружать сообщения для списка
                )
                
                # Загрузить количество сообщений отдельным запросом
                message_count_result = await self._db.execute(
                    select(func.count())
                    .select_from(MessageModel)
                    .where(MessageModel.session_db_id == model.id)
                )
                message_count = message_count_result.scalar() or 0
                
                # Установить количество сообщений в метаданные для использования в DTO
                session.metadata['_message_count'] = message_count
                
                sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}", exc_info=True)
            raise RepositoryError(
                operation="list",
                entity_type="Session",
                reason=str(e)
            )
    
    async def exists(self, id: str) -> bool:
        """
        Проверить существование сессии.
        
        Args:
            id: ID сессии
            
        Returns:
            True если существует
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(
                    SessionModel.id == id,
                    SessionModel.deleted_at.is_(None)
                )
            )
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking session existence {id}: {e}")
            return False
    
    async def count(self) -> int:
        """
        Подсчитать общее количество сессий.
        
        Returns:
            Количество сессий
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.deleted_at.is_(None))
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting sessions: {e}")
            return 0
    
    async def find_by_id(self, session_id: str) -> Optional[Session]:
        """
        Найти сессию по ID.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Сессия если найдена, None иначе
        """
        try:
            result = await self._db.execute(
                select(SessionModel).where(
                    SessionModel.id == session_id,
                    SessionModel.deleted_at.is_(None)
                )
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            # Преобразовать в сущность с загрузкой сообщений
            return await self._mapper.to_entity(
                model,
                self._db,
                load_messages=True
            )
            
        except Exception as e:
            logger.error(f"Error finding session {session_id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="find_by_id",
                entity_type="Session",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def find_active(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """
        Найти активные сессии.
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список активных сессий
        """
        try:
            result = await self._db.execute(
                select(SessionModel)
                .where(
                    SessionModel.is_active == True,
                    SessionModel.deleted_at.is_(None)
                )
                .order_by(SessionModel.last_activity.desc())
                .limit(limit)
                .offset(offset)
            )
            models = result.scalars().all()
            
            # Преобразовать в сущности
            sessions = []
            for model in models:
                session = await self._mapper.to_entity(
                    model,
                    self._db,
                    load_messages=False
                )
                
                # Загрузить количество сообщений отдельным запросом
                message_count_result = await self._db.execute(
                    select(func.count())
                    .select_from(MessageModel)
                    .where(MessageModel.session_db_id == model.id)
                )
                message_count = message_count_result.scalar() or 0
                
                # Установить количество сообщений в метаданные для использования в DTO
                session.metadata['_message_count'] = message_count
                
                sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error finding active sessions: {e}", exc_info=True)
            raise RepositoryError(
                operation="find_active",
                entity_type="Session",
                reason=str(e)
            )
    
    async def find_by_activity_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[Session]:
        """
        Найти сессии по диапазону активности.
        
        Args:
            start_time: Начало диапазона
            end_time: Конец диапазона
            limit: Максимальное количество
            
        Returns:
            Список сессий
        """
        try:
            result = await self._db.execute(
                select(SessionModel)
                .where(
                    SessionModel.last_activity >= start_time,
                    SessionModel.last_activity <= end_time,
                    SessionModel.deleted_at.is_(None)
                )
                .order_by(SessionModel.last_activity.desc())
                .limit(limit)
            )
            models = result.scalars().all()
            
            sessions = []
            for model in models:
                session = await self._mapper.to_entity(
                    model,
                    self._db,
                    load_messages=False
                )
                sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error finding sessions by activity range: {e}")
            raise RepositoryError(
                operation="find_by_activity_range",
                entity_type="Session",
                reason=str(e)
            )
    
    async def cleanup_old(
        self,
        max_age_hours: int = 24,
        batch_size: int = 100
    ) -> int:
        """
        Очистить старые неактивные сессии.
        
        Args:
            max_age_hours: Максимальный возраст в часах
            batch_size: Размер батча
            
        Returns:
            Количество очищенных сессий
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            
            # Найти старые неактивные сессии
            result = await self._db.execute(
                select(SessionModel)
                .where(
                    SessionModel.last_activity < cutoff_time,
                    SessionModel.is_active == False,
                    SessionModel.deleted_at.is_(None)
                )
                .limit(batch_size)
            )
            models = result.scalars().all()
            
            # Пометить как удаленные
            count = 0
            for model in models:
                model.deleted_at = datetime.now(timezone.utc)
                count += 1
            
            await self._db.flush()  # Flush changes within transaction, don't commit
            
            if count > 0:
                logger.info(
                    f"Cleaned up {count} old sessions "
                    f"(older than {max_age_hours} hours)"
                )
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {e}")
            raise RepositoryError(
                operation="cleanup_old",
                entity_type="Session",
                reason=str(e)
            )
    
    async def count_active(self) -> int:
        """
        Подсчитать количество активных сессий.
        
        Returns:
            Количество активных сессий
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(
                    SessionModel.is_active == True,
                    SessionModel.deleted_at.is_(None)
                )
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting active sessions: {e}")
            return 0
    
    async def save_snapshot(
        self,
        snapshot_id: str,
        snapshot: Dict[str, Any]
    ) -> None:
        """
        Сохранить snapshot сессии в in-memory хранилище.
        
        Args:
            snapshot_id: Уникальный ID snapshot
            snapshot: Данные snapshot
        """
        try:
            # Добавить timestamp для возможной очистки старых snapshots
            snapshot_with_meta = {
                **snapshot,
                "_saved_at": datetime.now(timezone.utc).isoformat()
            }
            
            SessionRepositoryImpl._snapshots[snapshot_id] = snapshot_with_meta
            
            logger.debug(
                f"Saved snapshot {snapshot_id} "
                f"(messages: {snapshot.get('message_count', 0)})"
            )
            
        except Exception as e:
            logger.error(f"Error saving snapshot {snapshot_id}: {e}")
            raise RepositoryError(
                operation="save_snapshot",
                entity_type="SessionSnapshot",
                reason=str(e),
                details={"snapshot_id": snapshot_id}
            )
    
    async def get_snapshot(
        self,
        snapshot_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получить snapshot сессии из in-memory хранилища.
        
        Args:
            snapshot_id: Уникальный ID snapshot
            
        Returns:
            Данные snapshot или None
        """
        try:
            snapshot = SessionRepositoryImpl._snapshots.get(snapshot_id)
            
            if snapshot:
                logger.debug(f"Retrieved snapshot {snapshot_id}")
            else:
                logger.warning(f"Snapshot {snapshot_id} not found")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error getting snapshot {snapshot_id}: {e}")
            return None
    
    async def delete_snapshot(
        self,
        snapshot_id: str
    ) -> bool:
        """
        Удалить snapshot сессии из in-memory хранилища.
        
        Args:
            snapshot_id: Уникальный ID snapshot
            
        Returns:
            True если удален, False если не найден
        """
        try:
            if snapshot_id in SessionRepositoryImpl._snapshots:
                del SessionRepositoryImpl._snapshots[snapshot_id]
                logger.debug(f"Deleted snapshot {snapshot_id}")
                return True
            else:
                logger.warning(f"Snapshot {snapshot_id} not found for deletion")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting snapshot {snapshot_id}: {e}")
            return False

"""
Реализация репозитория планов.

Конкретная реализация PlanRepository для работы с SQLAlchemy.
"""

import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, and_

from app.domain.repositories.plan_repository import PlanRepository
from app.domain.entities.plan import Plan, PlanStatus
from app.core.errors import RepositoryError
from app.infrastructure.persistence.models.plan import PlanModel, SubtaskModel
from app.infrastructure.persistence.mappers.plan_mapper import PlanMapper

logger = logging.getLogger("agent-runtime.infrastructure.plan_repository")


class PlanRepositoryImpl(PlanRepository):
    """
    Реализация репозитория планов для SQLAlchemy.
    
    Использует PlanMapper для преобразования между
    доменными сущностями и моделями БД.
    
    Атрибуты:
        _db: Сессия БД
        _mapper: Маппер для преобразований
    
    Пример:
        >>> repository = PlanRepositoryImpl(db_session)
        >>> plan = await repository.find_by_id("plan-1")
    """
    
    def __init__(self, db: AsyncSession):
        """
        Инициализация репозитория.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
        self._mapper = PlanMapper()
    
    async def get(self, id: str) -> Optional[Plan]:
        """
        Получить план по ID.
        
        Args:
            id: ID плана
            
        Returns:
            План если найден, None иначе
        """
        return await self.find_by_id(id)
    
    async def save(self, entity: Plan) -> None:
        """
        Сохранить план.
        
        Выполняет upsert: создаёт новый план или обновляет существующий.
        
        Args:
            entity: Доменная сущность плана
            
        Raises:
            RepositoryError: При ошибке сохранения
        """
        try:
            # Проверить, существует ли план
            result = await self._db.execute(
                select(PlanModel).where(PlanModel.id == entity.id)
            )
            existing_model = result.scalar_one_or_none()
            
            if existing_model:
                # Обновить существующий план
                await self._update_plan(existing_model, entity)
            else:
                # Создать новый план
                await self._create_plan(entity)
            
            await self._db.flush()  # Flush changes within transaction
            logger.debug(f"Saved plan {entity.id}")
            
        except Exception as e:
            logger.error(f"Error saving plan {entity.id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="save",
                entity_type="Plan",
                reason=str(e),
                details={"plan_id": entity.id}
            )
    
    async def _create_plan(self, plan: Plan) -> None:
        """Создать новый план в БД"""
        plan_model = self._mapper.to_persistence(plan)
        self._db.add(plan_model)
        logger.debug(f"Created new plan {plan.id} with {len(plan.subtasks)} subtasks")
    
    async def _update_plan(self, existing_model: PlanModel, plan: Plan) -> None:
        """Обновить существующий план"""
        # Обновить поля плана
        existing_model.goal = plan.goal
        existing_model.status = plan.status.value
        existing_model.current_subtask_id = plan.current_subtask_id
        existing_model.approved_at = plan.approved_at
        existing_model.started_at = plan.started_at
        existing_model.completed_at = plan.completed_at
        
        # Сериализация metadata
        import json
        if plan.metadata:
            existing_model.metadata_json = json.dumps(plan.metadata)
        
        # Очистить коллекцию subtasks (это не удаляет из БД, только из relationship)
        existing_model.subtasks.clear()
        
        # Удалить все старые subtasks из БД
        await self._db.execute(
            delete(SubtaskModel).where(SubtaskModel.plan_id == plan.id)
        )
        
        # Flush удаления перед добавлением новых subtasks
        # Это критично для избежания UNIQUE constraint при повторной вставке
        await self._db.flush()
        
        # Добавить новые subtasks
        for subtask in plan.subtasks:
            subtask_model = self._mapper._subtask_to_persistence(subtask, plan.id)
            self._db.add(subtask_model)
            existing_model.subtasks.append(subtask_model)
        
        logger.debug(f"Updated plan {plan.id} with {len(plan.subtasks)} subtasks")
    
    async def delete(self, id: str) -> bool:
        """
        Удалить план (hard delete).
        
        Args:
            id: ID плана
            
        Returns:
            True если удалён, False если не найден
        """
        try:
            # Удалить subtasks (cascade должен сработать, но делаем явно)
            await self._db.execute(
                delete(SubtaskModel).where(SubtaskModel.plan_id == id)
            )
            
            # Удалить план
            result = await self._db.execute(
                delete(PlanModel).where(PlanModel.id == id)
            )
            
            deleted = result.rowcount > 0
            
            if deleted:
                await self._db.flush()
                logger.info(f"Deleted plan {id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting plan {id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="delete",
                entity_type="Plan",
                reason=str(e),
                details={"plan_id": id}
            )
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Plan]:
        """
        Получить список планов с пагинацией.
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список планов
        """
        try:
            result = await self._db.execute(
                select(PlanModel)
                .order_by(PlanModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            models = result.scalars().all()
            
            # Преобразовать в сущности
            plans = [self._mapper.to_domain(model) for model in models]
            
            return plans
            
        except Exception as e:
            logger.error(f"Error listing plans: {e}", exc_info=True)
            raise RepositoryError(
                operation="list",
                entity_type="Plan",
                reason=str(e)
            )
    
    async def exists(self, id: str) -> bool:
        """
        Проверить существование плана.
        
        Args:
            id: ID плана
            
        Returns:
            True если существует
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(PlanModel)
                .where(PlanModel.id == id)
            )
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking plan existence {id}: {e}")
            return False
    
    async def count(self) -> int:
        """
        Подсчитать общее количество планов.
        
        Returns:
            Количество планов
        """
        try:
            result = await self._db.execute(
                select(func.count()).select_from(PlanModel)
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting plans: {e}")
            return 0
    
    async def find_by_id(self, plan_id: str) -> Optional[Plan]:
        """
        Найти план по ID.
        
        Args:
            plan_id: ID плана
            
        Returns:
            План если найден, None иначе
        """
        try:
            result = await self._db.execute(
                select(PlanModel).where(PlanModel.id == plan_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            # Преобразовать в сущность (subtasks загружаются через selectin)
            return self._mapper.to_domain(model)
            
        except Exception as e:
            logger.error(f"Error finding plan {plan_id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="find_by_id",
                entity_type="Plan",
                reason=str(e),
                details={"plan_id": plan_id}
            )
    
    async def find_by_session_id(self, session_id: str) -> Optional[Plan]:
        """
        Найти активный план для сессии.
        
        Возвращает последний план в статусе IN_PROGRESS или APPROVED.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Активный план или None
        """
        try:
            result = await self._db.execute(
                select(PlanModel)
                .where(
                    and_(
                        PlanModel.session_id == session_id,
                        PlanModel.status.in_([
                            PlanStatus.IN_PROGRESS.value,
                            PlanStatus.APPROVED.value
                        ])
                    )
                )
                .order_by(PlanModel.created_at.desc())
                .limit(1)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return self._mapper.to_domain(model)
            
        except Exception as e:
            logger.error(
                f"Error finding plan by session {session_id}: {e}",
                exc_info=True
            )
            raise RepositoryError(
                operation="find_by_session_id",
                entity_type="Plan",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def find_all_by_session_id(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Plan]:
        """
        Найти все планы для сессии.
        
        Args:
            session_id: ID сессии
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список планов
        """
        try:
            result = await self._db.execute(
                select(PlanModel)
                .where(PlanModel.session_id == session_id)
                .order_by(PlanModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            models = result.scalars().all()
            
            # Преобразовать в сущности
            plans = [self._mapper.to_domain(model) for model in models]
            
            return plans
            
        except Exception as e:
            logger.error(
                f"Error finding plans by session {session_id}: {e}",
                exc_info=True
            )
            raise RepositoryError(
                operation="find_all_by_session_id",
                entity_type="Plan",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def find_by_status(
        self,
        status: PlanStatus,
        limit: int = 100
    ) -> List[Plan]:
        """
        Найти планы по статусу.
        
        Args:
            status: Статус плана
            limit: Максимальное количество
            
        Returns:
            Список планов
        """
        try:
            result = await self._db.execute(
                select(PlanModel)
                .where(PlanModel.status == status.value)
                .order_by(PlanModel.created_at.desc())
                .limit(limit)
            )
            models = result.scalars().all()
            
            plans = [self._mapper.to_domain(model) for model in models]
            
            return plans
            
        except Exception as e:
            logger.error(f"Error finding plans by status {status}: {e}")
            raise RepositoryError(
                operation="find_by_status",
                entity_type="Plan",
                reason=str(e),
                details={"status": status.value}
            )
    
    async def count_by_session(self, session_id: str) -> int:
        """
        Подсчитать количество планов для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Количество планов
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(PlanModel)
                .where(PlanModel.session_id == session_id)
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting plans for session {session_id}: {e}")
            return 0

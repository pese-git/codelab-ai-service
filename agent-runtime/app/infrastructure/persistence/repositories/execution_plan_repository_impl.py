"""
Реализация ExecutionPlanRepository с использованием SQLAlchemy.

Конкретная реализация интерфейса ExecutionPlanRepository для работы с БД.
"""

import logging
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ....domain.execution_context.repositories import ExecutionPlanRepository
from ....domain.execution_context.entities import ExecutionPlan
from ....domain.execution_context.value_objects import PlanId
from ....domain.session_context.value_objects import ConversationId
from ..models import PlanModel

if TYPE_CHECKING:
    from ..mappers.execution_plan_mapper import ExecutionPlanMapper

logger = logging.getLogger("agent-runtime.infrastructure.execution_plan_repository")


class ExecutionPlanRepositoryImpl(ExecutionPlanRepository):
    """
    Реализация репозитория execution plans для SQLAlchemy.
    
    Использует ExecutionPlanMapper для преобразования между
    доменными сущностями и моделями БД.
    
    Атрибуты:
        _db: Сессия БД SQLAlchemy
        _mapper: Mapper для преобразования данных
    
    Пример:
        >>> repo = ExecutionPlanRepositoryImpl(db_session)
        >>> plan = await repo.find_by_id(PlanId("plan-123"))
    """
    
    def __init__(self, db: AsyncSession):
        """
        Инициализировать репозиторий.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
        # Lazy import для избежания циклических зависимостей
        from ..mappers.execution_plan_mapper import ExecutionPlanMapper
        self._mapper = ExecutionPlanMapper()
    
    async def find_by_id(self, plan_id: PlanId) -> Optional[ExecutionPlan]:
        """
        Найти план по ID.
        
        Args:
            plan_id: ID плана
            
        Returns:
            ExecutionPlan или None если не найден
            
        Example:
            >>> plan = await repo.find_by_id(PlanId("plan-123"))
            >>> if plan:
            ...     print(f"Found plan: {plan.goal}")
        """
        try:
            result = await self._db.execute(
                select(PlanModel).where(PlanModel.id == plan_id.value)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                logger.debug(f"ExecutionPlan {plan_id.value} not found")
                return None
            
            plan = await self._mapper.to_entity(model, self._db)
            logger.debug(f"Found ExecutionPlan {plan_id.value}")
            return plan
            
        except Exception as e:
            logger.error(
                f"Error finding ExecutionPlan {plan_id.value}: {e}",
                exc_info=True
            )
            raise
    
    async def find_by_conversation_id(
        self,
        conversation_id: ConversationId
    ) -> List[ExecutionPlan]:
        """
        Найти все планы для conversation.
        
        Args:
            conversation_id: ID conversation
            
        Returns:
            Список ExecutionPlan (может быть пустым)
            
        Example:
            >>> plans = await repo.find_by_conversation_id(ConversationId("conv-123"))
            >>> print(f"Found {len(plans)} plans")
        """
        try:
            result = await self._db.execute(
                select(PlanModel)
                .where(PlanModel.session_id == conversation_id.value)
                .order_by(PlanModel.created_at.desc())
            )
            models = result.scalars().all()
            
            plans = []
            for model in models:
                plan = await self._mapper.to_entity(model, self._db)
                plans.append(plan)
            
            logger.debug(
                f"Found {len(plans)} plans for conversation {conversation_id.value}"
            )
            return plans
            
        except Exception as e:
            logger.error(
                f"Error finding plans for conversation {conversation_id.value}: {e}",
                exc_info=True
            )
            raise
    
    async def save(self, plan: ExecutionPlan) -> None:
        """
        Сохранить план.
        
        Выполняет upsert: создает новый план или обновляет существующий.
        
        Args:
            plan: ExecutionPlan entity
            
        Raises:
            Exception: При ошибке сохранения
            
        Example:
            >>> plan = ExecutionPlan(id=PlanId("plan-123"), ...)
            >>> await repo.save(plan)
        """
        try:
            await self._mapper.to_model(plan, self._db)
            await self._db.flush()
            logger.debug(f"Saved ExecutionPlan {plan.id.value}")
            
        except Exception as e:
            logger.error(
                f"Error saving ExecutionPlan {plan.id.value}: {e}",
                exc_info=True
            )
            raise
    
    async def delete(self, plan_id: PlanId) -> bool:
        """
        Удалить план.
        
        Также удаляет все связанные subtasks (cascade delete).
        
        Args:
            plan_id: ID плана
            
        Returns:
            True если план был удален, False если не найден
            
        Raises:
            Exception: При ошибке удаления
            
        Example:
            >>> deleted = await repo.delete(PlanId("plan-123"))
        """
        try:
            # Проверяем существование
            exists = await self.exists(plan_id)
            if not exists:
                logger.debug(f"ExecutionPlan {plan_id.value} not found for deletion")
                return False
            
            await self._db.execute(
                delete(PlanModel).where(PlanModel.id == plan_id.value)
            )
            await self._db.flush()
            logger.debug(f"Deleted ExecutionPlan {plan_id.value}")
            return True
            
        except Exception as e:
            logger.error(
                f"Error deleting ExecutionPlan {plan_id.value}: {e}",
                exc_info=True
            )
            raise
    
    # Дополнительные методы для удобства
    
    async def find_active_by_conversation_id(
        self,
        conversation_id: ConversationId
    ) -> List[ExecutionPlan]:
        """
        Найти активные планы для conversation.
        
        Активные планы - это планы в статусах: approved, in_progress.
        
        Args:
            conversation_id: ID conversation
            
        Returns:
            Список активных ExecutionPlan
            
        Example:
            >>> active_plans = await repo.find_active_by_conversation_id(
            ...     ConversationId("conv-123")
            ... )
        """
        try:
            result = await self._db.execute(
                select(PlanModel)
                .where(
                    PlanModel.session_id == conversation_id.value,
                    PlanModel.status.in_(["draft", "approved", "in_progress"])
                )
                .order_by(PlanModel.created_at.desc())
            )
            models = result.scalars().all()
            
            plans = []
            for model in models:
                plan = await self._mapper.to_entity(model, self._db)
                plans.append(plan)
            
            logger.debug(
                f"Found {len(plans)} active plans for conversation {conversation_id.value}"
            )
            return plans
            
        except Exception as e:
            logger.error(
                f"Error finding active plans for conversation {conversation_id.value}: {e}",
                exc_info=True
            )
            raise
    
    async def count_by_conversation_id(
        self,
        conversation_id: ConversationId
    ) -> int:
        """
        Подсчитать количество планов для conversation.
        
        Args:
            conversation_id: ID conversation
            
        Returns:
            Количество планов
            
        Example:
            >>> count = await repo.count_by_conversation_id(ConversationId("conv-123"))
            >>> print(f"Total plans: {count}")
        """
        try:
            from sqlalchemy import func
            
            result = await self._db.execute(
                select(func.count(PlanModel.id))
                .where(PlanModel.session_id == conversation_id.value)
            )
            count = result.scalar_one()
            
            logger.debug(
                f"Found {count} plans for conversation {conversation_id.value}"
            )
            return count
            
        except Exception as e:
            logger.error(
                f"Error counting plans for conversation {conversation_id.value}: {e}",
                exc_info=True
            )
            raise
    
    async def exists(self, plan_id: PlanId) -> bool:
        """
        Проверить существование плана.
        
        Args:
            plan_id: ID плана
            
        Returns:
            True если план существует, False иначе
            
        Example:
            >>> if await repo.exists(PlanId("plan-123")):
            ...     print("Plan exists")
        """
        try:
            from sqlalchemy import func
            
            result = await self._db.execute(
                select(func.count(PlanModel.id))
                .where(PlanModel.id == plan_id.value)
            )
            count = result.scalar_one()
            return count > 0
            
        except Exception as e:
            logger.error(
                f"Error checking existence of ExecutionPlan {plan_id.value}: {e}",
                exc_info=True
            )
            raise
    
    # Методы базового Repository интерфейса (aliases)
    
    async def get(self, id: PlanId) -> Optional[ExecutionPlan]:
        """
        Получить план по ID (alias для find_by_id).
        
        Args:
            id: ID плана
            
        Returns:
            ExecutionPlan или None
        """
        return await self.find_by_id(id)
    
    async def add(self, entity: ExecutionPlan) -> None:
        """
        Добавить новый план (alias для save).
        
        Args:
            entity: ExecutionPlan entity
        """
        await self.save(entity)
    
    async def update(self, entity: ExecutionPlan) -> None:
        """
        Обновить существующий план (alias для save).
        
        Args:
            entity: ExecutionPlan entity
        """
        await self.save(entity)
    
    async def remove(self, id: PlanId) -> None:
        """
        Удалить план (alias для delete).
        
        Args:
            id: ID плана
        """
        await self.delete(id)
    
    async def list_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ExecutionPlan]:
        """
        Получить все планы с пагинацией.
        
        Args:
            limit: Максимальное количество планов
            offset: Смещение от начала
            
        Returns:
            Список ExecutionPlan
            
        Example:
            >>> plans = await repo.list_all(limit=10, offset=0)
        """
        try:
            query = select(PlanModel).order_by(PlanModel.created_at.desc())
            
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            result = await self._db.execute(query)
            models = result.scalars().all()
            
            plans = []
            for model in models:
                plan = await self._mapper.to_entity(model, self._db)
                plans.append(plan)
            
            logger.debug(f"Listed {len(plans)} plans")
            return plans
            
        except Exception as e:
            logger.error(f"Error listing plans: {e}", exc_info=True)
            raise
    
    async def count(self) -> int:
        """
        Подсчитать общее количество планов.
        
        Returns:
            Общее количество планов
            
        Example:
            >>> total = await repo.count()
        """
        try:
            from sqlalchemy import func
            
            result = await self._db.execute(
                select(func.count(PlanModel.id))
            )
            count = result.scalar_one()
            logger.debug(f"Total plans count: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Error counting plans: {e}", exc_info=True)
            raise
    
    async def find_by_status(
        self,
        status: str,
        limit: Optional[int] = None
    ) -> List[ExecutionPlan]:
        """
        Найти планы по статусу.
        
        Args:
            status: Статус плана (draft, approved, in_progress, etc.)
            limit: Максимальное количество планов
            
        Returns:
            Список ExecutionPlan
            
        Example:
            >>> active_plans = await repo.find_by_status("in_progress")
        """
        try:
            query = select(PlanModel).where(
                PlanModel.status == status
            ).order_by(PlanModel.created_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            result = await self._db.execute(query)
            models = result.scalars().all()
            
            plans = []
            for model in models:
                plan = await self._mapper.to_entity(model, self._db)
                plans.append(plan)
            
            logger.debug(f"Found {len(plans)} plans with status {status}")
            return plans
            
        except Exception as e:
            logger.error(f"Error finding plans by status {status}: {e}", exc_info=True)
            raise
    
    async def count_by_conversation(
        self,
        conversation_id: ConversationId
    ) -> int:
        """
        Подсчитать планы для conversation (alias для count_by_conversation_id).
        
        Args:
            conversation_id: ID conversation
            
        Returns:
            Количество планов
        """
        return await self.count_by_conversation_id(conversation_id)
    
    async def find_all_by_conversation_id(
        self,
        conversation_id: ConversationId,
        limit: int = 50,
        offset: int = 0
    ) -> List[ExecutionPlan]:
        """
        Найти все планы для conversation (расширенная версия find_by_conversation_id).
        
        Args:
            conversation_id: ID conversation
            limit: Максимальное количество планов
            offset: Смещение
            
        Returns:
            Список ExecutionPlan
        """
        try:
            query = select(PlanModel).where(
                PlanModel.session_id == conversation_id.value
            ).order_by(PlanModel.created_at.desc())
            
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            result = await self._db.execute(query)
            models = result.scalars().all()
            
            plans = []
            for model in models:
                plan = await self._mapper.to_entity(model, self._db)
                plans.append(plan)
            
            logger.debug(
                f"Found {len(plans)} plans for conversation {conversation_id.value}"
            )
            return plans
            
        except Exception as e:
            logger.error(
                f"Error finding plans for conversation {conversation_id.value}: {e}",
                exc_info=True
            )
            raise

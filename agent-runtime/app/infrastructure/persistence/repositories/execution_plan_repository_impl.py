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
    
    async def delete(self, plan_id: PlanId) -> None:
        """
        Удалить план.
        
        Также удаляет все связанные subtasks (cascade delete).
        
        Args:
            plan_id: ID плана
            
        Raises:
            Exception: При ошибке удаления
            
        Example:
            >>> await repo.delete(PlanId("plan-123"))
        """
        try:
            await self._db.execute(
                delete(PlanModel).where(PlanModel.id == plan_id.value)
            )
            await self._db.flush()
            logger.debug(f"Deleted ExecutionPlan {plan_id.value}")
            
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
                    PlanModel.status.in_(["approved", "in_progress"])
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

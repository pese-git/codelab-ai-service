"""
Mapper для преобразования между ExecutionPlan Entity и PlanModel.

Изолирует доменный слой от деталей персистентности.
Использует новую ExecutionPlan entity вместо старой Plan.
"""

import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ....domain.execution_context.entities import ExecutionPlan, Subtask
from ....domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus,
)
from ....domain.session_context.value_objects import ConversationId
from ....domain.agent_context.value_objects import AgentId
from ..models import PlanModel, SubtaskModel

logger = logging.getLogger("agent-runtime.infrastructure.execution_plan_mapper")


class ExecutionPlanMapper:
    """
    Mapper между доменной сущностью ExecutionPlan и моделью БД PlanModel.
    
    Отвечает за преобразование данных между доменным слоем
    и слоем персистентности.
    
    Пример:
        >>> mapper = ExecutionPlanMapper()
        >>> # Entity -> Model
        >>> model = await mapper.to_model(execution_plan, db)
        >>> # Model -> Entity
        >>> entity = await mapper.to_entity(model, db)
    """
    
    async def to_entity(
        self,
        model: PlanModel,
        db: AsyncSession,
        load_subtasks: bool = True
    ) -> ExecutionPlan:
        """
        Преобразовать модель БД в доменную сущность ExecutionPlan.
        
        Args:
            model: Модель БД PlanModel
            db: Сессия БД для загрузки связанных данных
            load_subtasks: Загружать ли subtasks
            
        Returns:
            Доменная сущность ExecutionPlan
            
        Пример:
            >>> execution_plan = await mapper.to_entity(plan_model, db)
        """
        # Загрузить subtasks если требуется
        subtasks: List[Subtask] = []
        if load_subtasks:
            # Сначала проверяем, есть ли уже загруженные subtasks в модели
            if hasattr(model, 'subtasks') and model.subtasks:
                subtask_models = model.subtasks
            else:
                # Загружаем из БД
                result = await db.execute(
                    select(SubtaskModel)
                    .where(SubtaskModel.plan_id == model.id)
                    .order_by(SubtaskModel.created_at.asc())
                )
                subtask_models = result.scalars().all()
            
            # Преобразовать модели subtasks в entities
            for st_model in subtask_models:
                subtask = self._subtask_to_entity(st_model)
                subtasks.append(subtask)
        
        # Парсинг metadata
        metadata = {}
        if model.metadata_json:
            try:
                metadata = json.loads(model.metadata_json)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse metadata for plan {model.id}"
                )
        
        # Создать ExecutionPlan
        execution_plan = ExecutionPlan(
            id=PlanId(model.id),
            conversation_id=ConversationId(model.session_id),
            goal=model.goal,
            subtasks=subtasks,
            status=PlanStatus.from_string(model.status),
            current_subtask_id=SubtaskId(model.current_subtask_id) if model.current_subtask_id else None,
            metadata=metadata,
            approved_at=model.approved_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        
        return execution_plan
    
    def _subtask_to_entity(self, model: SubtaskModel) -> Subtask:
        """
        Преобразовать SubtaskModel в Subtask entity.
        
        Args:
            model: Модель БД SubtaskModel
            
        Returns:
            Доменная сущность Subtask
        """
        # Парсинг dependencies
        dependencies = []
        if model.dependencies_json:
            try:
                deps = json.loads(model.dependencies_json)
                dependencies = [SubtaskId(d) for d in deps]
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse dependencies for subtask {model.id}"
                )
        
        return Subtask(
            id=SubtaskId(model.id),
            description=model.description,
            agent_id=AgentId(value=model.agent),
            dependencies=dependencies,
            status=SubtaskStatus.from_string(model.status),
            estimated_time=model.estimated_time,
            result=model.result,
            error=model.error,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    async def to_model(
        self,
        entity: ExecutionPlan,
        db: AsyncSession
    ) -> PlanModel:
        """
        Преобразовать доменную сущность ExecutionPlan в модель БД.
        
        Также сохраняет связанные subtasks.
        
        Args:
            entity: Доменная сущность ExecutionPlan
            db: Сессия БД
            
        Returns:
            Модель БД PlanModel
            
        Пример:
            >>> plan_model = await mapper.to_model(execution_plan, db)
        """
        # Найти существующую модель или создать новую
        result = await db.execute(
            select(PlanModel).where(PlanModel.id == entity.id.value)
        )
        model = result.scalar_one_or_none()
        
        if model is None:
            model = PlanModel(id=entity.id.value)
            db.add(model)
            # Установить timestamps из entity если они есть
            if entity.created_at:
                model.created_at = entity.created_at
            if entity.updated_at:
                model.updated_at = entity.updated_at
        
        # Обновить поля
        model.session_id = entity.conversation_id.value
        model.goal = entity.goal
        model.status = entity.status.value
        model.current_subtask_id = entity.current_subtask_id.value if entity.current_subtask_id else None
        model.metadata_json = json.dumps(entity.metadata) if entity.metadata else None
        model.approved_at = entity.approved_at
        model.started_at = entity.started_at
        model.completed_at = entity.completed_at
        if entity.updated_at:
            model.updated_at = entity.updated_at
        
        # Сохранить subtasks
        await self._save_subtasks(entity, db)
        
        return model
    
    async def _save_subtasks(
        self,
        entity: ExecutionPlan,
        db: AsyncSession
    ) -> None:
        """
        Сохранить subtasks в БД.
        
        Удаляет старые subtasks и создает новые.
        
        Args:
            entity: ExecutionPlan entity
            db: Сессия БД
        """
        # Удалить старые subtasks (если есть)
        await db.execute(
            delete(SubtaskModel).where(
                SubtaskModel.plan_id == entity.id.value
            )
        )
        
        # Создать новые subtasks
        for subtask in entity.subtasks:
            st_model = SubtaskModel(
                id=subtask.id.value,
                plan_id=entity.id.value,
                description=subtask.description,
                agent=subtask.agent_id.value,
                status=subtask.status.value,
                dependencies_json=json.dumps([d.value for d in subtask.dependencies]) if subtask.dependencies else "[]",
                estimated_time=subtask.estimated_time,
                result=subtask.result,
                error=subtask.error,
                started_at=subtask.started_at,
                completed_at=subtask.completed_at,
                created_at=subtask.created_at,
                updated_at=subtask.updated_at,
            )
            db.add(st_model)

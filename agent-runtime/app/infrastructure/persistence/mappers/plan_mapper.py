"""
Mapper between domain Plan entities and database models.

Handles conversion between:
- Plan (domain) ↔ PlanModel (database)
- Subtask (domain) ↔ SubtaskModel (database)
"""
import json
import logging
from typing import List, Union
from datetime import datetime, timezone

from app.domain.execution_context.entities.execution_plan import ExecutionPlan
from app.domain.execution_context.entities.subtask import Subtask
from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus,
)
from app.domain.session_context.value_objects import ConversationId
from app.domain.agent_context.value_objects import AgentId
from app.infrastructure.persistence.models.plan import PlanModel, SubtaskModel

logger = logging.getLogger("agent-runtime.plan_mapper")


class PlanMapper:
    """
    Mapper для преобразования Plan между доменной и БД моделями.
    
    Следует паттерну Clean Architecture:
    - Domain entities не зависят от БД
    - Mapper изолирует преобразование
    - Обработка JSON сериализации
    
    Поддерживает Value Objects (PlanId, SubtaskId) для совместимости
    с новой архитектурой.
    """
    
    @staticmethod
    def _convert_plan_id(value: Union[str, 'PlanId']) -> str:
        """
        Конвертировать PlanId в строку для БД.
        
        Поддерживает как строки, так и PlanId Value Objects.
        
        Args:
            value: str или PlanId
            
        Returns:
            Строковое представление ID
            
        Example:
            >>> plan_id_str = PlanMapper._convert_plan_id(PlanId("plan-123"))
            >>> plan_id_str = PlanMapper._convert_plan_id("plan-123")
        """
        if PlanId and isinstance(value, PlanId):
            return value.value
        return str(value) if value else None
    
    @staticmethod
    def _convert_subtask_id(value: Union[str, 'SubtaskId']) -> str:
        """
        Конвертировать SubtaskId в строку для БД.
        
        Поддерживает как строки, так и SubtaskId Value Objects.
        
        Args:
            value: str или SubtaskId
            
        Returns:
            Строковое представление ID
            
        Example:
            >>> subtask_id_str = PlanMapper._convert_subtask_id(SubtaskId("st-123"))
            >>> subtask_id_str = PlanMapper._convert_subtask_id("st-123")
        """
        if SubtaskId and isinstance(value, SubtaskId):
            return value.value
        return str(value) if value else None
    
    @staticmethod
    def to_domain(plan_model: PlanModel) -> ExecutionPlan:
        """
        Преобразовать БД модель в доменную сущность.
        
        Args:
            plan_model: SQLAlchemy модель плана (с загруженными subtasks)
            
        Returns:
            ExecutionPlan: Доменная сущность
        """
        # Преобразовать subtasks
        subtasks = [
            PlanMapper._subtask_to_domain(st_model)
            for st_model in plan_model.subtasks
        ]
        
        # Парсинг metadata
        metadata = {}
        if plan_model.metadata_json:
            try:
                metadata = json.loads(plan_model.metadata_json)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse metadata JSON for plan {plan_model.id}"
                )
                metadata = {}
        
        # Создать ExecutionPlan с Value Objects
        plan = ExecutionPlan(
            id=PlanId(value=plan_model.id),
            conversation_id=ConversationId(value=plan_model.session_id),
            goal=plan_model.goal,
            subtasks=subtasks,
            status=PlanStatus.from_string(plan_model.status),
            current_subtask_id=SubtaskId(value=plan_model.current_subtask_id) if plan_model.current_subtask_id else None,
            metadata=metadata,
            approved_at=plan_model.approved_at,
            started_at=plan_model.started_at,
            completed_at=plan_model.completed_at,
            created_at=plan_model.created_at,
            updated_at=plan_model.updated_at,
        )
        
        return plan
    
    @staticmethod
    def _subtask_to_domain(subtask_model: SubtaskModel) -> Subtask:
        """
        Преобразовать БД модель subtask в доменную сущность.
        
        Args:
            subtask_model: SQLAlchemy модель subtask
            
        Returns:
            Subtask: Доменная сущность
        """
        # Парсинг dependencies
        dependencies = []
        if subtask_model.dependencies_json:
            try:
                dependencies = json.loads(subtask_model.dependencies_json)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse dependencies JSON for subtask {subtask_model.id}"
                )
                dependencies = []
        
        # Создать Subtask с Value Objects
        subtask = Subtask(
            id=SubtaskId(value=subtask_model.id),
            description=subtask_model.description,
            agent_id=AgentId(value=subtask_model.agent),
            dependencies=[SubtaskId(value=dep_id) for dep_id in dependencies],
            status=SubtaskStatus.from_string(subtask_model.status),
            estimated_time=subtask_model.estimated_time,
            result=subtask_model.result,
            error=subtask_model.error,
            started_at=subtask_model.started_at,
            completed_at=subtask_model.completed_at,
            metadata={},  # Subtask metadata не хранится в БД пока
            created_at=subtask_model.created_at,
            updated_at=subtask_model.updated_at,
        )
        
        return subtask
    
    @staticmethod
    def to_persistence(plan: ExecutionPlan) -> PlanModel:
        """
        Преобразовать доменную сущность в БД модель.
        
        Args:
            plan: Доменная сущность ExecutionPlan
            
        Returns:
            PlanModel: SQLAlchemy модель (с subtasks)
        """
        # Сериализация metadata
        metadata_json = None
        if plan.metadata:
            try:
                metadata_json = json.dumps(plan.metadata)
            except (TypeError, ValueError) as e:
                logger.warning(
                    f"Failed to serialize metadata for plan {plan.id.value}: {e}"
                )
                metadata_json = "{}"
        
        # Создать PlanModel, извлекая значения из Value Objects
        plan_model = PlanModel(
            id=plan.id.value,
            session_id=plan.conversation_id.value,
            goal=plan.goal,
            status=plan.status.value,
            current_subtask_id=plan.current_subtask_id.value if plan.current_subtask_id else None,
            metadata_json=metadata_json,
            approved_at=plan.approved_at,
            started_at=plan.started_at,
            completed_at=plan.completed_at,
            created_at=plan.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        
        # Преобразовать subtasks
        plan_model.subtasks = [
            PlanMapper._subtask_to_persistence(st, plan.id.value)
            for st in plan.subtasks
        ]
        
        return plan_model
    
    @staticmethod
    def _subtask_to_persistence(subtask: Subtask, plan_id: str) -> SubtaskModel:
        """
        Преобразовать доменную subtask в БД модель.
        
        Args:
            subtask: Доменная сущность Subtask
            plan_id: ID плана (для foreign key)
            
        Returns:
            SubtaskModel: SQLAlchemy модель
        """
        # Сериализация dependencies (извлекаем значения из SubtaskId)
        dependencies_json = "[]"
        if subtask.dependencies:
            try:
                dep_values = [dep.value for dep in subtask.dependencies]
                dependencies_json = json.dumps(dep_values)
            except (TypeError, ValueError) as e:
                logger.warning(
                    f"Failed to serialize dependencies for subtask {subtask.id.value}: {e}"
                )
                dependencies_json = "[]"
        
        # Извлечь значения из Value Objects
        subtask_model = SubtaskModel(
            id=subtask.id.value,
            plan_id=plan_id,
            description=subtask.description,
            agent=subtask.agent_id.value,
            status=subtask.status.value,
            dependencies_json=dependencies_json,
            estimated_time=subtask.estimated_time,
            result=subtask.result,
            error=subtask.error,
            started_at=subtask.started_at,
            completed_at=subtask.completed_at,
            created_at=subtask.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        
        return subtask_model

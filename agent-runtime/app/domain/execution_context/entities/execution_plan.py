"""
ExecutionPlan Entity для Execution Context.

Представляет план выполнения задачи с подзадачами.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import Field

from app.domain.shared.base_entity import Entity
from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    PlanStatusEnum,
)
from app.domain.session_context.value_objects import ConversationId
from app.domain.execution_context.entities.subtask import Subtask
from app.domain.agent_context.value_objects import AgentId


class ExecutionPlan(Entity):
    """
    План выполнения задачи.
    
    Содержит декомпозицию задачи на подзадачи и управляет их выполнением.
    
    Бизнес-правила:
    - План должен быть утвержден перед выполнением
    - Подзадачи выполняются с учетом зависимостей
    - Нельзя назначить подзадачу Architect агенту
    - Все подзадачи должны быть атомарными
    - План не может быть пустым при утверждении
    
    Attributes:
        id: Уникальный идентификатор плана
        conversation_id: ID диалога, к которому относится план
        goal: Цель плана (описание задачи)
        subtasks: Список подзадач
        status: Текущий статус плана
        current_subtask_id: ID текущей выполняемой подзадачи
        metadata: Дополнительные метаданные
        approved_at: Время утверждения плана
        started_at: Время начала выполнения
        completed_at: Время завершения
    
    Example:
        >>> plan = ExecutionPlan(
        ...     id=PlanId("plan-1"),
        ...     conversation_id=ConversationId("conv-1"),
        ...     goal="Create a widget"
        ... )
        >>> subtask = Subtask(id=SubtaskId("st-1"), ...)
        >>> plan.add_subtask(subtask)
        >>> plan.approve()
        >>> plan.start_execution()
    """
    
    id: PlanId = Field(
        ...,
        description="Уникальный идентификатор плана"
    )
    
    conversation_id: ConversationId = Field(
        ...,
        description="ID диалога, к которому относится план"
    )
    
    goal: str = Field(
        ...,
        description="Цель плана (описание задачи)",
        min_length=1,
        max_length=5000
    )
    
    subtasks: List[Subtask] = Field(
        default_factory=list,
        description="Список подзадач"
    )
    
    status: PlanStatus = Field(
        default_factory=PlanStatus.draft,
        description="Текущий статус плана"
    )
    
    current_subtask_id: Optional[SubtaskId] = Field(
        default=None,
        description="ID текущей выполняемой подзадачи"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные"
    )
    
    approved_at: Optional[datetime] = Field(
        default=None,
        description="Время утверждения плана"
    )
    
    started_at: Optional[datetime] = Field(
        default=None,
        description="Время начала выполнения"
    )
    
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Время завершения"
    )
    
    def add_subtask(self, subtask: Subtask) -> None:
        """
        Добавить подзадачу в план.
        
        Args:
            subtask: Подзадача для добавления
            
        Raises:
            ValueError: Если план уже утвержден или подзадача назначена Architect
        
        Example:
            >>> plan = ExecutionPlan(id=PlanId("plan-1"), ...)
            >>> subtask = Subtask(id=SubtaskId("st-1"), agent_id=AgentId("coder"), ...)
            >>> plan.add_subtask(subtask)
        """
        if not self.status.is_draft():
            raise ValueError(
                f"Cannot add subtask to plan in status {self.status}. "
                f"Expected status: DRAFT"
            )
        
        # Проверка: Architect не может исполнять подзадачи
        if subtask.agent_id.value == "architect":
            raise ValueError(
                "Architect agent cannot be assigned to subtasks. "
                "Architect only creates plans, not executes them."
            )
        
        self.subtasks.append(subtask)
        self.mark_updated()
    
    def approve(self) -> None:
        """
        Утвердить план для выполнения.
        
        Переводит статус из DRAFT в APPROVED.
        
        Raises:
            ValueError: Если план пустой или уже утвержден
        
        Example:
            >>> plan.add_subtask(subtask)
            >>> plan.approve()
            >>> assert plan.status.is_approved()
        """
        if not self.status.is_draft():
            raise ValueError(
                f"Cannot approve plan in status {self.status}. "
                f"Expected status: DRAFT"
            )
        
        if not self.subtasks:
            raise ValueError("Cannot approve empty plan")
        
        self.status = PlanStatus.approved()
        self.approved_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def start_execution(self) -> None:
        """
        Начать выполнение плана.
        
        Переводит статус из APPROVED в IN_PROGRESS.
        
        Raises:
            ValueError: Если план не утвержден
        
        Example:
            >>> plan.approve()
            >>> plan.start_execution()
            >>> assert plan.status.is_in_progress()
        """
        if not self.status.is_approved():
            raise ValueError(
                f"Cannot start execution of plan in status {self.status}. "
                f"Expected status: APPROVED"
            )
        
        self.status = PlanStatus.in_progress()
        self.started_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def get_next_subtask(self) -> Optional[Subtask]:
        """
        Получить следующую подзадачу для выполнения.
        
        Учитывает зависимости между подзадачами.
        
        Returns:
            Следующая подзадача или None если все выполнены
        
        Example:
            >>> plan.start_execution()
            >>> next_task = plan.get_next_subtask()
            >>> if next_task:
            ...     next_task.start()
        """
        if not self.status.is_in_progress():
            return None
        
        # Получить список завершенных подзадач
        completed_ids = [
            st.id for st in self.subtasks
            if st.status.is_done()
        ]
        
        # Найти первую готовую к выполнению подзадачу
        for subtask in self.subtasks:
            if subtask.is_ready(completed_ids):
                return subtask
        
        return None
    
    def get_subtask_by_id(self, subtask_id: SubtaskId) -> Optional[Subtask]:
        """
        Получить подзадачу по ID.
        
        Args:
            subtask_id: ID подзадачи
            
        Returns:
            Подзадача или None
        
        Example:
            >>> subtask = plan.get_subtask_by_id(SubtaskId("st-1"))
            >>> if subtask:
            ...     print(subtask.description)
        """
        for subtask in self.subtasks:
            if subtask.id == subtask_id:
                return subtask
        return None
    
    def complete(self) -> None:
        """
        Завершить план успешно.
        
        Переводит статус из IN_PROGRESS в COMPLETED.
        
        Raises:
            ValueError: Если не все подзадачи выполнены
        
        Example:
            >>> # После выполнения всех подзадач
            >>> plan.complete()
            >>> assert plan.status.is_completed()
        """
        if not self.status.is_in_progress():
            raise ValueError(
                f"Cannot complete plan in status {self.status}. "
                f"Expected status: IN_PROGRESS"
            )
        
        # Проверить, что все подзадачи выполнены
        if not all(st.status.is_done() for st in self.subtasks):
            raise ValueError("Cannot complete plan with unfinished subtasks")
        
        self.status = PlanStatus.completed()
        self.completed_at = datetime.now(timezone.utc)
        self.current_subtask_id = None
        self.mark_updated()
    
    def fail(self, reason: str) -> None:
        """
        Завершить план с ошибкой.
        
        Переводит статус в FAILED.
        
        Args:
            reason: Причина ошибки
        
        Example:
            >>> plan.fail("Critical subtask failed")
            >>> assert plan.status.is_failed()
        """
        if self.status.is_terminal():
            raise ValueError(
                f"Cannot fail plan in terminal status {self.status}"
            )
        
        if not reason:
            raise ValueError("Failure reason cannot be empty")
        
        self.status = PlanStatus.failed()
        self.completed_at = datetime.now(timezone.utc)
        self.metadata["failure_reason"] = reason
        self.mark_updated()
    
    def cancel(self, reason: str) -> None:
        """
        Отменить план.
        
        Переводит статус в CANCELLED.
        
        Args:
            reason: Причина отмены
        
        Example:
            >>> plan.cancel("User requested cancellation")
            >>> assert plan.status.is_cancelled()
        """
        if self.status.is_completed():
            raise ValueError("Cannot cancel completed plan")
        
        if not reason:
            raise ValueError("Cancellation reason cannot be empty")
        
        self.status = PlanStatus.cancelled()
        self.completed_at = datetime.now(timezone.utc)
        self.metadata["cancellation_reason"] = reason
        self.mark_updated()
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Получить информацию о прогрессе выполнения.
        
        Returns:
            Словарь с информацией о прогрессе
        
        Example:
            >>> progress = plan.get_progress()
            >>> print(f"Progress: {progress['percentage']}%")
        """
        total = len(self.subtasks)
        done = sum(1 for st in self.subtasks if st.status.is_done())
        failed = sum(1 for st in self.subtasks if st.status.is_failed())
        running = sum(1 for st in self.subtasks if st.status.is_running())
        
        return {
            "total": total,
            "done": done,
            "failed": failed,
            "running": running,
            "pending": total - done - failed - running,
            "percentage": (done / total * 100) if total > 0 else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать план в словарь.
        
        Returns:
            Словарь с данными плана
        
        Example:
            >>> plan_dict = plan.to_dict()
            >>> print(plan_dict["goal"])
        """
        return {
            "plan_id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "goal": self.goal,
            "status": str(self.status),
            "subtasks": [
                {
                    "id": str(st.id),
                    "description": st.description,
                    "agent": str(st.agent_id),
                    "dependencies": [str(dep) for dep in st.dependencies],
                    "status": str(st.status),
                    "estimated_time": st.estimated_time
                }
                for st in self.subtasks
            ],
            "progress": self.get_progress(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    def __repr__(self) -> str:
        """Строковое представление плана."""
        return (
            f"<ExecutionPlan(id='{self.id}', "
            f"conversation_id='{self.conversation_id}', "
            f"status='{self.status}', "
            f"subtasks={len(self.subtasks)})>"
        )

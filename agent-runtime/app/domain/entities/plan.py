"""
Доменные сущности для планирования и декомпозиции задач.

Представляют план выполнения задачи и его подзадачи.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import Field

from .base import Entity
from .agent_context import AgentType


class SubtaskStatus(str, Enum):
    """
    Статусы выполнения подзадачи.
    """
    PENDING = "pending"      # Ожидает выполнения
    RUNNING = "running"      # В процессе выполнения
    DONE = "done"           # Успешно завершена
    FAILED = "failed"       # Завершена с ошибкой
    BLOCKED = "blocked"     # Заблокирована зависимостями


class Subtask(Entity):
    """
    Подзадача в плане выполнения.
    
    Атрибуты:
        description: Описание подзадачи
        agent: Агент, ответственный за выполнение
        dependencies: ID подзадач, от которых зависит эта
        status: Текущий статус выполнения
        estimated_time: Оценка времени выполнения
        result: Результат выполнения (после завершения)
        error: Информация об ошибке (если failed)
        started_at: Время начала выполнения
        completed_at: Время завершения
        metadata: Дополнительные метаданные
    """
    
    description: str = Field(
        ...,
        description="Описание подзадачи"
    )
    
    agent: AgentType = Field(
        ...,
        description="Агент, ответственный за выполнение"
    )
    
    dependencies: List[str] = Field(
        default_factory=list,
        description="ID подзадач, от которых зависит эта"
    )
    
    status: SubtaskStatus = Field(
        default=SubtaskStatus.PENDING,
        description="Текущий статус выполнения"
    )
    
    estimated_time: Optional[str] = Field(
        default=None,
        description="Оценка времени выполнения"
    )
    
    result: Optional[str] = Field(
        default=None,
        description="Результат выполнения"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Информация об ошибке"
    )
    
    started_at: Optional[datetime] = Field(
        default=None,
        description="Время начала выполнения"
    )
    
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Время завершения"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные"
    )
    
    def start(self) -> None:
        """
        Начать выполнение подзадачи.
        
        Raises:
            ValueError: Если подзадача не в статусе PENDING
        """
        if self.status != SubtaskStatus.PENDING:
            raise ValueError(
                f"Cannot start subtask in status {self.status.value}"
            )
        
        self.status = SubtaskStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def complete(self, result: str) -> None:
        """
        Завершить подзадачу успешно.
        
        Args:
            result: Результат выполнения
            
        Raises:
            ValueError: Если подзадача не в статусе RUNNING
        """
        if self.status != SubtaskStatus.RUNNING:
            raise ValueError(
                f"Cannot complete subtask in status {self.status.value}"
            )
        
        self.status = SubtaskStatus.DONE
        self.result = result
        self.completed_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def fail(self, error: str) -> None:
        """
        Завершить подзадачу с ошибкой.
        
        Args:
            error: Описание ошибки
            
        Raises:
            ValueError: Если подзадача не в статусе RUNNING
        """
        if self.status != SubtaskStatus.RUNNING:
            raise ValueError(
                f"Cannot fail subtask in status {self.status.value}"
            )
        
        self.status = SubtaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def block(self) -> None:
        """
        Заблокировать подзадачу из-за невыполненных зависимостей.
        """
        if self.status == SubtaskStatus.PENDING:
            self.status = SubtaskStatus.BLOCKED
            self.mark_updated()
    
    def unblock(self) -> None:
        """
        Разблокировать подзадачу.
        """
        if self.status == SubtaskStatus.BLOCKED:
            self.status = SubtaskStatus.PENDING
            self.mark_updated()
    
    def is_ready(self, completed_subtasks: List[str]) -> bool:
        """
        Проверить, готова ли подзадача к выполнению.
        
        Args:
            completed_subtasks: Список ID завершенных подзадач
            
        Returns:
            True если все зависимости выполнены
        """
        if self.status != SubtaskStatus.PENDING:
            return False
        
        return all(dep_id in completed_subtasks for dep_id in self.dependencies)
    
    def __repr__(self) -> str:
        """Строковое представление подзадачи"""
        return (
            f"<Subtask(id='{self.id}', "
            f"agent='{self.agent.value}', "
            f"status='{self.status.value}')>"
        )


class PlanStatus(str, Enum):
    """
    Статусы выполнения плана.
    """
    DRAFT = "draft"           # Черновик, не утвержден
    APPROVED = "approved"     # Утвержден, готов к выполнению
    IN_PROGRESS = "in_progress"  # В процессе выполнения
    COMPLETED = "completed"   # Успешно завершен
    FAILED = "failed"         # Завершен с ошибкой
    CANCELLED = "cancelled"   # Отменен


class Plan(Entity):
    """
    План выполнения задачи.
    
    Содержит декомпозицию задачи на подзадачи и управляет их выполнением.
    
    Атрибуты:
        session_id: ID сессии, к которой относится план
        goal: Цель плана (описание задачи)
        subtasks: Список подзадач
        status: Текущий статус плана
        current_subtask_id: ID текущей выполняемой подзадачи
        metadata: Дополнительные метаданные
        approved_at: Время утверждения плана
        started_at: Время начала выполнения
        completed_at: Время завершения
    
    Бизнес-правила:
        - План должен быть утвержден перед выполнением
        - Подзадачи выполняются с учетом зависимостей
        - Нельзя назначить подзадачу Architect агенту
        - Все подзадачи должны быть атомарными
    """
    
    session_id: str = Field(
        ...,
        description="ID сессии, к которой относится план"
    )
    
    goal: str = Field(
        ...,
        description="Цель плана (описание задачи)"
    )
    
    subtasks: List[Subtask] = Field(
        default_factory=list,
        description="Список подзадач"
    )
    
    status: PlanStatus = Field(
        default=PlanStatus.DRAFT,
        description="Текущий статус плана"
    )
    
    current_subtask_id: Optional[str] = Field(
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
        """
        if self.status != PlanStatus.DRAFT:
            raise ValueError(
                f"Cannot add subtask to plan in status {self.status.value}"
            )
        
        # Проверка: Architect не может исполнять подзадачи
        if subtask.agent == AgentType.ARCHITECT:
            raise ValueError(
                "Architect agent cannot be assigned to subtasks. "
                "Architect only creates plans, not executes them."
            )
        
        self.subtasks.append(subtask)
        self.mark_updated()
    
    def approve(self) -> None:
        """
        Утвердить план для выполнения.
        
        Raises:
            ValueError: Если план пустой или уже утвержден
        """
        if self.status != PlanStatus.DRAFT:
            raise ValueError(
                f"Cannot approve plan in status {self.status.value}"
            )
        
        if not self.subtasks:
            raise ValueError("Cannot approve empty plan")
        
        self.status = PlanStatus.APPROVED
        self.approved_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def start_execution(self) -> None:
        """
        Начать выполнение плана.
        
        Raises:
            ValueError: Если план не утвержден
        """
        if self.status != PlanStatus.APPROVED:
            raise ValueError(
                f"Cannot start execution of plan in status {self.status.value}"
            )
        
        self.status = PlanStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def get_next_subtask(self) -> Optional[Subtask]:
        """
        Получить следующую подзадачу для выполнения.
        
        Учитывает зависимости между подзадачами.
        
        Returns:
            Следующая подзадача или None если все выполнены
        """
        if self.status != PlanStatus.IN_PROGRESS:
            return None
        
        # Получить список завершенных подзадач
        completed_ids = [
            st.id for st in self.subtasks
            if st.status == SubtaskStatus.DONE
        ]
        
        # Найти первую готовую к выполнению подзадачу
        for subtask in self.subtasks:
            if subtask.is_ready(completed_ids):
                return subtask
        
        return None
    
    def get_subtask_by_id(self, subtask_id: str) -> Optional[Subtask]:
        """
        Получить подзадачу по ID.
        
        Args:
            subtask_id: ID подзадачи
            
        Returns:
            Подзадача или None
        """
        for subtask in self.subtasks:
            if subtask.id == subtask_id:
                return subtask
        return None
    
    def complete(self) -> None:
        """
        Завершить план успешно.
        
        Raises:
            ValueError: Если не все подзадачи выполнены
        """
        if self.status != PlanStatus.IN_PROGRESS:
            raise ValueError(
                f"Cannot complete plan in status {self.status.value}"
            )
        
        # Проверить, что все подзадачи выполнены
        if not all(st.status == SubtaskStatus.DONE for st in self.subtasks):
            raise ValueError("Cannot complete plan with unfinished subtasks")
        
        self.status = PlanStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.current_subtask_id = None
        self.mark_updated()
    
    def fail(self, reason: str) -> None:
        """
        Завершить план с ошибкой.
        
        Args:
            reason: Причина ошибки
        """
        if self.status not in [PlanStatus.IN_PROGRESS, PlanStatus.APPROVED]:
            raise ValueError(
                f"Cannot fail plan in status {self.status.value}"
            )
        
        self.status = PlanStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.metadata["failure_reason"] = reason
        self.mark_updated()
    
    def cancel(self, reason: str) -> None:
        """
        Отменить план.
        
        Args:
            reason: Причина отмены
        """
        if self.status == PlanStatus.COMPLETED:
            raise ValueError("Cannot cancel completed plan")
        
        self.status = PlanStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        self.metadata["cancellation_reason"] = reason
        self.mark_updated()
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Получить информацию о прогрессе выполнения.
        
        Returns:
            Словарь с информацией о прогрессе
        """
        total = len(self.subtasks)
        done = sum(1 for st in self.subtasks if st.status == SubtaskStatus.DONE)
        failed = sum(1 for st in self.subtasks if st.status == SubtaskStatus.FAILED)
        running = sum(1 for st in self.subtasks if st.status == SubtaskStatus.RUNNING)
        
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
        """
        return {
            "plan_id": self.id,
            "session_id": self.session_id,
            "goal": self.goal,
            "status": self.status.value,
            "subtasks": [
                {
                    "id": st.id,
                    "description": st.description,
                    "agent": st.agent.value,
                    "dependencies": st.dependencies,
                    "status": st.status.value,
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
        """Строковое представление плана"""
        return (
            f"<Plan(id='{self.id}', "
            f"session_id='{self.session_id}', "
            f"status='{self.status.value}', "
            f"subtasks={len(self.subtasks)})>"
        )

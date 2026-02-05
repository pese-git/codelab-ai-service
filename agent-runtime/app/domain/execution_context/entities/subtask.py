"""
Subtask Entity для Execution Context.

Представляет подзадачу в плане выполнения.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import Field

from app.domain.shared.base_entity import Entity
from app.domain.execution_context.value_objects import (
    SubtaskId,
    SubtaskStatus,
    SubtaskStatusEnum,
)
from app.domain.agent_context.value_objects import AgentId


class Subtask(Entity):
    """
    Подзадача в плане выполнения.
    
    Бизнес-правила:
    - Подзадача может быть запущена только из статуса PENDING
    - Подзадача может быть завершена только из статуса RUNNING
    - Architect агент не может исполнять подзадачи
    - Зависимости должны быть выполнены перед запуском
    
    Attributes:
        id: Уникальный идентификатор подзадачи
        description: Описание подзадачи
        agent_id: ID агента, ответственного за выполнение
        dependencies: Список ID подзадач-зависимостей
        status: Текущий статус выполнения
        estimated_time: Оценка времени выполнения
        result: Результат выполнения (после завершения)
        error: Информация об ошибке (если failed)
        started_at: Время начала выполнения
        completed_at: Время завершения
        metadata: Дополнительные метаданные
    
    Example:
        >>> subtask = Subtask(
        ...     id=SubtaskId("st-1"),
        ...     description="Create widget",
        ...     agent_id=AgentId("coder")
        ... )
        >>> subtask.start()
        >>> subtask.complete("Widget created successfully")
    """
    
    id: SubtaskId = Field(
        ...,
        description="Уникальный идентификатор подзадачи"
    )
    
    description: str = Field(
        ...,
        description="Описание подзадачи",
        min_length=1,
        max_length=5000
    )
    
    agent_id: AgentId = Field(
        ...,
        description="ID агента, ответственного за выполнение"
    )
    
    dependencies: List[SubtaskId] = Field(
        default_factory=list,
        description="Список ID подзадач-зависимостей"
    )
    
    status: SubtaskStatus = Field(
        default_factory=SubtaskStatus.pending,
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
        
        Переводит статус из PENDING в RUNNING.
        
        Raises:
            ValueError: Если подзадача не в статусе PENDING
        
        Example:
            >>> subtask = Subtask(id=SubtaskId("st-1"), ...)
            >>> subtask.start()
            >>> assert subtask.status.is_running()
        """
        if not self.status.is_pending():
            raise ValueError(
                f"Cannot start subtask in status {self.status}. "
                f"Expected status: PENDING"
            )
        
        self.status = SubtaskStatus.running()
        self.started_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def complete(self, result: str) -> None:
        """
        Завершить подзадачу успешно.
        
        Переводит статус из RUNNING в DONE.
        
        Args:
            result: Результат выполнения
            
        Raises:
            ValueError: Если подзадача не в статусе RUNNING или result пустой
        
        Example:
            >>> subtask.start()
            >>> subtask.complete("Task completed successfully")
            >>> assert subtask.status.is_done()
        """
        if not self.status.is_running():
            raise ValueError(
                f"Cannot complete subtask in status {self.status}. "
                f"Expected status: RUNNING"
            )
        
        if not result:
            raise ValueError("Result cannot be empty")
        
        self.status = SubtaskStatus.done()
        self.result = result
        self.completed_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def fail(self, error: str) -> None:
        """
        Завершить подзадачу с ошибкой.
        
        Переводит статус из RUNNING в FAILED.
        
        Args:
            error: Описание ошибки
            
        Raises:
            ValueError: Если подзадача не в статусе RUNNING или error пустой
        
        Example:
            >>> subtask.start()
            >>> subtask.fail("Connection timeout")
            >>> assert subtask.status.is_failed()
        """
        if not self.status.is_running():
            raise ValueError(
                f"Cannot fail subtask in status {self.status}. "
                f"Expected status: RUNNING"
            )
        
        if not error:
            raise ValueError("Error message cannot be empty")
        
        self.status = SubtaskStatus.failed()
        self.error = error
        self.completed_at = datetime.now(timezone.utc)
        self.mark_updated()
    
    def block(self) -> None:
        """
        Заблокировать подзадачу из-за невыполненных зависимостей.
        
        Переводит статус из PENDING в BLOCKED.
        
        Example:
            >>> subtask = Subtask(id=SubtaskId("st-2"), dependencies=[SubtaskId("st-1")])
            >>> subtask.block()
            >>> assert subtask.status.is_blocked()
        """
        if self.status.is_pending():
            self.status = SubtaskStatus.blocked()
            self.mark_updated()
    
    def unblock(self) -> None:
        """
        Разблокировать подзадачу.
        
        Переводит статус из BLOCKED в PENDING.
        
        Example:
            >>> subtask.block()
            >>> subtask.unblock()
            >>> assert subtask.status.is_pending()
        """
        if self.status.is_blocked():
            self.status = SubtaskStatus.pending()
            self.mark_updated()
    
    def is_ready(self, completed_subtask_ids: List[SubtaskId]) -> bool:
        """
        Проверить, готова ли подзадача к выполнению.
        
        Подзадача готова если:
        - Статус PENDING
        - Все зависимости выполнены
        
        Args:
            completed_subtask_ids: Список ID завершенных подзадач
            
        Returns:
            True если все зависимости выполнены
        
        Example:
            >>> subtask = Subtask(
            ...     id=SubtaskId("st-2"),
            ...     dependencies=[SubtaskId("st-1")]
            ... )
            >>> subtask.is_ready([SubtaskId("st-1")])
            True
        """
        if not self.status.is_pending():
            return False
        
        completed_ids_set = set(completed_subtask_ids)
        return all(dep_id in completed_ids_set for dep_id in self.dependencies)
    
    def get_duration_seconds(self) -> Optional[float]:
        """
        Получить длительность выполнения в секундах.
        
        Returns:
            Длительность в секундах или None если не завершена
        
        Example:
            >>> subtask.start()
            >>> # ... выполнение ...
            >>> subtask.complete("Done")
            >>> duration = subtask.get_duration_seconds()
            >>> assert duration > 0
        """
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    def __repr__(self) -> str:
        """Строковое представление подзадачи."""
        return (
            f"<Subtask(id='{self.id}', "
            f"agent='{self.agent_id}', "
            f"status='{self.status}')>"
        )

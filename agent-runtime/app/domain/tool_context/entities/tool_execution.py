"""
Entity для выполнения инструмента.

Представляет полный цикл выполнения инструмента с результатом.
"""

from datetime import datetime
from typing import Optional

from ...shared.base_entity import BaseEntity
from ..value_objects import ToolCallId, ToolResult
from .tool_call import ToolCall


class ToolExecution(BaseEntity):
    """
    Entity для выполнения инструмента.
    
    Представляет полный цикл выполнения: запрос → выполнение → результат.
    
    Атрибуты:
        id: ID вызова инструмента
        tool_call: Вызов инструмента
        result: Результат выполнения (None до завершения)
        started_at: Время начала выполнения
        completed_at: Время завершения (None если не завершено)
        error: Сообщение об ошибке (None если успешно)
    
    Примеры:
        >>> execution = ToolExecution.start(tool_call)
        >>> execution.complete(ToolResult.success("File read successfully"))
        >>> execution.get_duration_ms()
        150
    """
    
    id: ToolCallId
    tool_call: ToolCall
    result: Optional[ToolResult] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    @staticmethod
    def start(tool_call: ToolCall) -> "ToolExecution":
        """
        Начать выполнение инструмента.
        
        Args:
            tool_call: Вызов инструмента для выполнения
            
        Returns:
            Новый ToolExecution в состоянии "выполняется"
            
        Example:
            >>> execution = ToolExecution.start(tool_call)
            >>> execution.is_running()
            True
        """
        from ..events.tool_events import ToolExecutionStarted
        
        execution = ToolExecution(
            id=tool_call.id,
            tool_call=tool_call,
            result=None,
            started_at=datetime.utcnow(),
            completed_at=None,
            error=None
        )
        
        # Генерация Domain Event
        execution.add_domain_event(ToolExecutionStarted(
            tool_call_id=str(tool_call.id),
            tool_name=str(tool_call.tool_name),
            arguments=tool_call.arguments.to_dict(),
            occurred_at=execution.started_at
        ))
        
        return execution
    
    def complete(self, result: ToolResult) -> None:
        """
        Завершить выполнение с результатом.
        
        Args:
            result: Результат выполнения
            
        Raises:
            ValueError: Если выполнение уже завершено
            
        Example:
            >>> execution.complete(ToolResult.success("Done"))
            >>> execution.is_completed()
            True
        """
        from ..events.tool_events import ToolExecutionCompleted
        
        if self.is_completed():
            raise ValueError(
                f"Tool execution '{self.id}' is already completed"
            )
        
        self.result = result
        self.completed_at = datetime.utcnow()
        
        # Если результат - ошибка, сохранить сообщение
        if result.is_error:
            self.error = result.get_content()
        
        # Генерация Domain Event
        self.add_domain_event(ToolExecutionCompleted(
            tool_call_id=str(self.id),
            tool_name=str(self.tool_call.tool_name),
            result_content=result.get_content(),
            is_error=result.is_error,
            duration_ms=self.get_duration_ms(),
            occurred_at=self.completed_at
        ))
    
    def fail(self, error: str) -> None:
        """
        Завершить выполнение с ошибкой.
        
        Args:
            error: Сообщение об ошибке
            
        Raises:
            ValueError: Если выполнение уже завершено
            
        Example:
            >>> execution.fail("Tool not found")
            >>> execution.is_failed()
            True
        """
        from ..events.tool_events import ToolExecutionFailed
        
        if self.is_completed():
            raise ValueError(
                f"Tool execution '{self.id}' is already completed"
            )
        
        self.error = error
        self.result = ToolResult.error(error)
        self.completed_at = datetime.utcnow()
        
        # Генерация Domain Event
        self.add_domain_event(ToolExecutionFailed(
            tool_call_id=str(self.id),
            tool_name=str(self.tool_call.tool_name),
            error=error,
            duration_ms=self.get_duration_ms(),
            occurred_at=self.completed_at
        ))
    
    def is_running(self) -> bool:
        """
        Проверить, выполняется ли инструмент.
        
        Returns:
            True если выполнение не завершено
            
        Example:
            >>> execution.is_running()
            False
        """
        return self.completed_at is None
    
    def is_completed(self) -> bool:
        """
        Проверить, завершено ли выполнение.
        
        Returns:
            True если выполнение завершено
            
        Example:
            >>> execution.is_completed()
            True
        """
        return self.completed_at is not None
    
    def is_successful(self) -> bool:
        """
        Проверить, успешно ли завершено выполнение.
        
        Returns:
            True если завершено успешно (без ошибок)
            
        Example:
            >>> execution.is_successful()
            True
        """
        return self.is_completed() and self.error is None
    
    def is_failed(self) -> bool:
        """
        Проверить, завершено ли выполнение с ошибкой.
        
        Returns:
            True если завершено с ошибкой
            
        Example:
            >>> execution.is_failed()
            False
        """
        return self.is_completed() and self.error is not None
    
    def get_duration_ms(self) -> Optional[int]:
        """
        Получить длительность выполнения в миллисекундах.
        
        Returns:
            Длительность в мс или None если не завершено
            
        Example:
            >>> execution.get_duration_ms()
            150
        """
        if not self.is_completed():
            return None
        
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)
    
    def get_result_content(self) -> Optional[str]:
        """
        Получить содержимое результата.
        
        Returns:
            Содержимое результата или None если не завершено
            
        Example:
            >>> execution.get_result_content()
            'File read successfully'
        """
        if self.result is None:
            return None
        return self.result.get_content()
    
    def to_dict(self) -> dict:
        """
        Преобразовать в словарь.
        
        Returns:
            Словарь с данными выполнения
            
        Example:
            >>> data = execution.to_dict()
            >>> data['tool_name']
            'read_file'
        """
        return {
            "id": str(self.id),
            "tool_name": str(self.tool_call.tool_name),
            "arguments": self.tool_call.arguments.to_dict(),
            "result": self.result.get_content() if self.result else None,
            "is_error": self.result.is_error if self.result else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.get_duration_ms(),
            "error": self.error
        }
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        status = "running" if self.is_running() else (
            "success" if self.is_successful() else "failed"
        )
        return (
            f"<ToolExecution(id='{self.id}', "
            f"tool='{self.tool_call.tool_name}', "
            f"status={status})>"
        )

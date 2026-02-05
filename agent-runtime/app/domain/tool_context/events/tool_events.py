"""
Domain Events для Tool Context.

События жизненного цикла инструментов и их выполнения.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from ...shared.domain_event import DomainEvent


# ===== ToolCall Events =====

class ToolCallCreated(DomainEvent):
    """
    Событие создания вызова инструмента.
    
    Генерируется при создании нового ToolCall.
    """
    tool_call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    requires_approval: bool


class ToolCallValidated(DomainEvent):
    """
    Событие валидации вызова инструмента.
    
    Генерируется после успешной валидации ToolCall.
    """
    tool_call_id: str
    tool_name: str
    is_valid: bool


class ToolCallApproved(DomainEvent):
    """
    Событие одобрения вызова инструмента.
    
    Генерируется когда пользователь одобряет выполнение инструмента.
    """
    tool_call_id: str
    tool_name: str


class ToolCallRejected(DomainEvent):
    """
    Событие отклонения вызова инструмента.
    
    Генерируется когда пользователь отклоняет выполнение инструмента.
    """
    tool_call_id: str
    tool_name: str
    reason: str


# ===== ToolExecution Events =====

class ToolExecutionStarted(DomainEvent):
    """
    Событие начала выполнения инструмента.
    
    Генерируется при старте выполнения ToolCall.
    """
    tool_call_id: str
    tool_name: str
    arguments: Dict[str, Any]


class ToolExecutionCompleted(DomainEvent):
    """
    Событие успешного завершения выполнения инструмента.
    
    Генерируется при успешном завершении выполнения.
    """
    tool_call_id: str
    tool_name: str
    result_content: str
    is_error: bool
    duration_ms: Optional[int]


class ToolExecutionFailed(DomainEvent):
    """
    Событие неудачного завершения выполнения инструмента.
    
    Генерируется при ошибке выполнения.
    """
    tool_call_id: str
    tool_name: str
    error: str
    duration_ms: Optional[int]


# ===== ToolSpecification Events =====

class ToolSpecificationCreated(DomainEvent):
    """
    Событие создания спецификации инструмента.
    
    Генерируется при регистрации нового инструмента.
    """
    tool_name: str
    category: str
    execution_mode: str


class ToolSpecificationUpdated(DomainEvent):
    """
    Событие обновления спецификации инструмента.
    
    Генерируется при изменении метаданных инструмента.
    """
    tool_name: str
    field: str
    old_value: Any
    new_value: Any


class ToolSpecificationRemoved(DomainEvent):
    """
    Событие удаления спецификации инструмента.
    
    Генерируется при удалении инструмента из реестра.
    """
    tool_name: str
    reason: Optional[str] = None

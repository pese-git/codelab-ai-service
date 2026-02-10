"""
ApprovalType Value Object.

Типобезопасный тип запроса на утверждение.
"""

from enum import Enum
from typing import Any, ClassVar

from pydantic import field_validator
from app.domain.shared.value_object import ValueObject


class ApprovalTypeEnum(str, Enum):
    """
    Типы запросов на утверждение.
    
    - TOOL_CALL: Вызов инструмента (write_file, execute_command, etc.)
    - PLAN_EXECUTION: Выполнение плана с подзадачами
    - AGENT_SWITCH: Переключение между агентами
    - FILE_OPERATION: Операция с файловой системой
    """
    TOOL_CALL: ClassVar = "tool_call"
    PLAN_EXECUTION: ClassVar = "plan_execution"
    AGENT_SWITCH: ClassVar = "agent_switch"
    FILE_OPERATION: ClassVar = "file_operation"


class ApprovalType(ValueObject):
    """
    
    value: ApprovalTypeEnum
    Типобезопасный тип запроса на утверждение.
    
    Обеспечивает:
    - Валидацию типа из enum
    - Иммутабельность
    - Сравнение по значению
    
    Примеры:
        >>> approval_type = ApprovalType(ApprovalTypeEnum.TOOL_CALL)
        >>> str(approval_type)
        'tool_call'
        
        >>> approval_type.is_tool_call()
        True
    """
    value: ApprovalTypeEnum
    
    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v: Any) -> ApprovalTypeEnum:
        """Валидация что value является ApprovalTypeEnum."""
        if not isinstance(v, ApprovalTypeEnum):
            raise ValueError(f"value must be ApprovalTypeEnum, got {type(v).__name__}")
        return v
    
    def is_tool_call(self) -> bool:
        """Проверить, является ли тип вызовом инструмента."""
        return self.value == ApprovalTypeEnum.TOOL_CALL
    
    def is_plan_execution(self) -> bool:
        """Проверить, является ли тип выполнением плана."""
        return self.value == ApprovalTypeEnum.PLAN_EXECUTION
    
    def is_agent_switch(self) -> bool:
        """Проверить, является ли тип переключением агента."""
        return self.value == ApprovalTypeEnum.AGENT_SWITCH
    
    def is_file_operation(self) -> bool:
        """Проверить, является ли тип операцией с файлом."""
        return self.value == ApprovalTypeEnum.FILE_OPERATION
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value.value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ApprovalType({self.value.name})"
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение по значению."""
        if not isinstance(other, ApprovalType):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash(self.value)

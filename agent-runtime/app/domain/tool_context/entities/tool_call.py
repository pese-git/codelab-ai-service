"""
Entity для вызова инструмента.

Представляет запрос на выполнение инструмента от LLM.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from ...shared.base_entity import BaseEntity
from ..value_objects import (
    ToolCallId,
    ToolName,
    ToolArguments
)

if TYPE_CHECKING:
    from .tool_specification import ToolSpecification


class ToolCall(BaseEntity):
    """
    Entity для вызова инструмента.
    
    Представляет запрос LLM на выполнение инструмента.
    
    Атрибуты:
        id: Уникальный идентификатор вызова
        tool_name: Имя инструмента
        arguments: Аргументы для инструмента
        created_at: Время создания
        requires_approval: Требуется ли одобрение пользователя
        approved: Одобрен ли вызов
    
    Примеры:
        >>> tool_call = ToolCall.create(
        ...     tool_name=ToolName.from_string("read_file"),
        ...     arguments=ToolArguments.from_dict({"path": "test.py"})
        ... )
        >>> tool_call.validate(tool_spec)
        (True, None)
    """
    
    id: ToolCallId
    tool_name: ToolName
    arguments: ToolArguments
    created_at: datetime
    requires_approval: bool = False
    approved: bool = False
    
    @staticmethod
    def create(
        tool_name: ToolName,
        arguments: ToolArguments,
        requires_approval: bool = False,
        call_id: Optional[ToolCallId] = None
    ) -> "ToolCall":
        """
        Создать новый вызов инструмента.
        
        Args:
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            requires_approval: Требуется ли одобрение
            call_id: ID вызова (генерируется если не указан)
            
        Returns:
            Новый ToolCall
            
        Example:
            >>> tool_call = ToolCall.create(
            ...     tool_name=ToolName.from_string("write_file"),
            ...     arguments=ToolArguments.from_dict({"path": "test.py", "content": "hello"})
            ... )
        """
        from ..events.tool_events import ToolCallCreated
        
        tool_call = ToolCall(
            id=call_id or ToolCallId.generate(),
            tool_name=tool_name,
            arguments=arguments,
            created_at=datetime.utcnow(),
            requires_approval=requires_approval,
            approved=False
        )
        
        # Генерация Domain Event
        tool_call.add_domain_event(ToolCallCreated(
            tool_call_id=str(tool_call.id),
            tool_name=str(tool_call.tool_name),
            arguments=tool_call.arguments.to_dict(),
            requires_approval=requires_approval,
            occurred_at=tool_call.created_at
        ))
        
        return tool_call
    
    def validate(
        self,
        tool_spec: "ToolSpecification"
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидировать вызов против спецификации инструмента.
        
        Args:
            tool_spec: Спецификация инструмента
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            
        Example:
            >>> is_valid, error = tool_call.validate(tool_spec)
            >>> if not is_valid:
            ...     print(f"Validation error: {error}")
        """
        from ..events.tool_events import ToolCallValidated
        
        # Проверка имени инструмента
        if self.tool_name != tool_spec.name:
            return False, (
                f"Tool name mismatch: expected '{tool_spec.name}', "
                f"got '{self.tool_name}'"
            )
        
        # Валидация аргументов против схемы
        is_valid, error = self.arguments.validate_against_schema(
            tool_spec.parameters
        )
        
        if not is_valid:
            return False, f"Invalid arguments: {error}"
        
        # Генерация Domain Event
        self.add_domain_event(ToolCallValidated(
            tool_call_id=str(self.id),
            tool_name=str(self.tool_name),
            is_valid=True,
            occurred_at=datetime.utcnow()
        ))
        
        return True, None
    
    def mark_approved(self) -> None:
        """
        Пометить вызов как одобренный.
        
        Example:
            >>> tool_call.mark_approved()
            >>> tool_call.approved
            True
        """
        from ..events.tool_events import ToolCallApproved
        
        if not self.requires_approval:
            raise ValueError(
                f"Tool call '{self.id}' does not require approval"
            )
        
        if self.approved:
            raise ValueError(
                f"Tool call '{self.id}' is already approved"
            )
        
        self.approved = True
        
        # Генерация Domain Event
        self.add_domain_event(ToolCallApproved(
            tool_call_id=str(self.id),
            tool_name=str(self.tool_name),
            occurred_at=datetime.utcnow()
        ))
    
    def mark_rejected(self, reason: str) -> None:
        """
        Пометить вызов как отклоненный.
        
        Args:
            reason: Причина отклонения
            
        Example:
            >>> tool_call.mark_rejected("User denied permission")
        """
        from ..events.tool_events import ToolCallRejected
        
        if not self.requires_approval:
            raise ValueError(
                f"Tool call '{self.id}' does not require approval"
            )
        
        # Генерация Domain Event
        self.add_domain_event(ToolCallRejected(
            tool_call_id=str(self.id),
            tool_name=str(self.tool_name),
            reason=reason,
            occurred_at=datetime.utcnow()
        ))
    
    def to_llm_format(self) -> Dict[str, Any]:
        """
        Преобразовать в формат для LLM API.
        
        Returns:
            Словарь в формате OpenAI tool_calls
            
        Example:
            >>> llm_format = tool_call.to_llm_format()
            >>> llm_format['type']
            'function'
        """
        return {
            "id": str(self.id),
            "type": "function",
            "function": {
                "name": str(self.tool_name),
                "arguments": self.arguments.to_json()
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь.
        
        Returns:
            Словарь с данными вызова
            
        Example:
            >>> data = tool_call.to_dict()
            >>> data['tool_name']
            'read_file'
        """
        return {
            "id": str(self.id),
            "tool_name": str(self.tool_name),
            "arguments": self.arguments.to_dict(),
            "created_at": self.created_at.isoformat(),
            "requires_approval": self.requires_approval,
            "approved": self.approved
        }
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return (
            f"<ToolCall(id='{self.id}', "
            f"tool='{self.tool_name}', "
            f"approved={self.approved})>"
        )

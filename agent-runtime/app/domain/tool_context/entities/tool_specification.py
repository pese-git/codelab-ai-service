"""
Entity для спецификации инструмента.

Представляет метаданные и схему инструмента.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from ...shared.base_entity import BaseEntity
from ..value_objects import (
    ToolName,
    ToolCategory,
    ToolExecutionMode,
    ToolPermission,
    ToolArguments
)


class ToolSpecification(BaseEntity):
    """
    Entity для спецификации инструмента.
    
    Представляет метаданные инструмента и схему его параметров.
    
    Атрибуты:
        name: Имя инструмента
        description: Описание инструмента
        parameters: JSON Schema параметров
        category: Категория инструмента
        execution_mode: Режим выполнения
        required_permission: Требуемый уровень доступа
        created_at: Время создания спецификации
    
    Примеры:
        >>> spec = ToolSpecification.create(
        ...     name=ToolName.from_string("read_file"),
        ...     description="Read file content",
        ...     parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        ...     category=ToolCategory.file_system(),
        ...     execution_mode=ToolExecutionMode.ide(),
        ...     required_permission=ToolPermission.read_only()
        ... )
    """
    
    id: ToolName  # Используем name как id для уникальности
    name: ToolName
    description: str
    parameters: Dict[str, Any]
    category: ToolCategory
    execution_mode: ToolExecutionMode
    required_permission: ToolPermission
    created_at: datetime
    
    @staticmethod
    def create(
        name: ToolName,
        description: str,
        parameters: Dict[str, Any],
        category: ToolCategory,
        execution_mode: ToolExecutionMode,
        required_permission: ToolPermission
    ) -> "ToolSpecification":
        """
        Создать новую спецификацию инструмента.
        
        Args:
            name: Имя инструмента
            description: Описание
            parameters: JSON Schema параметров
            category: Категория
            execution_mode: Режим выполнения
            required_permission: Требуемый уровень доступа
            
        Returns:
            Новая ToolSpecification
            
        Example:
            >>> spec = ToolSpecification.create(
            ...     name=ToolName.from_string("write_file"),
            ...     description="Write content to file",
            ...     parameters={"type": "object", "required": ["path", "content"]},
            ...     category=ToolCategory.file_system(),
            ...     execution_mode=ToolExecutionMode.ide(),
            ...     required_permission=ToolPermission.read_write()
            ... )
        """
        from ..events.tool_events import ToolSpecificationCreated
        
        spec = ToolSpecification(
            id=name,  # Используем name как id
            name=name,
            description=description,
            parameters=parameters,
            category=category,
            execution_mode=execution_mode,
            required_permission=required_permission,
            created_at=datetime.utcnow()
        )
        
        # Генерация Domain Event
        spec.add_domain_event(ToolSpecificationCreated(
            tool_name=str(name),
            category=str(category),
            execution_mode=str(execution_mode),
            occurred_at=spec.created_at
        ))
        
        return spec
    
    def validate_arguments(
        self,
        args: ToolArguments
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидировать аргументы против схемы.
        
        Args:
            args: Аргументы для валидации
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            
        Example:
            >>> args = ToolArguments.from_dict({"path": "test.py"})
            >>> is_valid, error = spec.validate_arguments(args)
        """
        return args.validate_against_schema(self.parameters)
    
    def to_openai_format(self) -> Dict[str, Any]:
        """
        Преобразовать в формат OpenAI tools API.
        
        Returns:
            Словарь в формате OpenAI
            
        Example:
            >>> openai_format = spec.to_openai_format()
            >>> openai_format['type']
            'function'
        """
        return {
            "type": "function",
            "function": {
                "name": str(self.name),
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def is_dangerous(self) -> bool:
        """
        Проверить, является ли инструмент опасным.
        
        Returns:
            True если инструмент опасный
            
        Example:
            >>> spec.is_dangerous()
            True
        """
        return self.category.is_dangerous()
    
    def requires_approval(self) -> bool:
        """
        Проверить, требует ли инструмент одобрения.
        
        Returns:
            True если требуется одобрение
            
        Example:
            >>> spec.requires_approval()
            True
        """
        return self.category.requires_approval()
    
    def is_local_tool(self) -> bool:
        """
        Проверить, является ли инструмент локальным.
        
        Returns:
            True если выполняется локально
            
        Example:
            >>> spec.is_local_tool()
            False
        """
        return self.execution_mode.is_local()
    
    def is_ide_tool(self) -> bool:
        """
        Проверить, является ли инструмент IDE-инструментом.
        
        Returns:
            True если выполняется в IDE
            
        Example:
            >>> spec.is_ide_tool()
            True
        """
        return self.execution_mode.is_ide()
    
    def update_description(self, new_description: str) -> None:
        """
        Обновить описание инструмента.
        
        Args:
            new_description: Новое описание
            
        Example:
            >>> spec.update_description("Updated description")
        """
        from ..events.tool_events import ToolSpecificationUpdated
        
        old_description = self.description
        self.description = new_description
        
        # Генерация Domain Event
        self.add_domain_event(ToolSpecificationUpdated(
            tool_name=str(self.name),
            field="description",
            old_value=old_description,
            new_value=new_description,
            occurred_at=datetime.utcnow()
        ))
    
    def update_parameters(self, new_parameters: Dict[str, Any]) -> None:
        """
        Обновить схему параметров.
        
        Args:
            new_parameters: Новая JSON Schema
            
        Example:
            >>> spec.update_parameters({"type": "object", "required": ["path"]})
        """
        from ..events.tool_events import ToolSpecificationUpdated
        
        old_parameters = self.parameters
        self.parameters = new_parameters
        
        # Генерация Domain Event
        self.add_domain_event(ToolSpecificationUpdated(
            tool_name=str(self.name),
            field="parameters",
            old_value=old_parameters,
            new_value=new_parameters,
            occurred_at=datetime.utcnow()
        ))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь.
        
        Returns:
            Словарь с данными спецификации
            
        Example:
            >>> data = spec.to_dict()
            >>> data['name']
            'read_file'
        """
        return {
            "name": str(self.name),
            "description": self.description,
            "parameters": self.parameters,
            "category": str(self.category),
            "execution_mode": str(self.execution_mode),
            "required_permission": str(self.required_permission),
            "created_at": self.created_at.isoformat()
        }
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return (
            f"<ToolSpecification(name='{self.name}', "
            f"category={self.category}, "
            f"mode={self.execution_mode})>"
        )

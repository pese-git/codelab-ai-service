"""
Domain Service для валидации инструментов.

Инкапсулирует бизнес-правила валидации вызовов инструментов.
"""

from typing import List, Optional, Tuple

from ..value_objects import ToolArguments, ToolPermission
from ..entities import ToolCall, ToolSpecification


class ToolValidator:
    """
    Domain Service для валидации инструментов.
    
    Валидирует:
    - Вызовы инструментов против спецификаций
    - Аргументы против JSON Schema
    - Права доступа
    
    Примеры:
        >>> validator = ToolValidator()
        >>> is_valid, error = validator.validate_tool_call(tool_call, spec)
        >>> if not is_valid:
        ...     print(f"Validation error: {error}")
    """
    
    def validate_tool_call(
        self,
        tool_call: ToolCall,
        spec: ToolSpecification
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидировать вызов инструмента против спецификации.
        
        Args:
            tool_call: Вызов инструмента
            spec: Спецификация инструмента
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            
        Example:
            >>> is_valid, error = validator.validate_tool_call(tool_call, spec)
            >>> if not is_valid:
            ...     print(f"Error: {error}")
        """
        # Проверка имени инструмента
        if tool_call.tool_name != spec.name:
            return False, (
                f"Tool name mismatch: expected '{spec.name}', "
                f"got '{tool_call.tool_name}'"
            )
        
        # Валидация аргументов
        is_valid, error = self.validate_arguments(
            tool_call.arguments,
            spec.parameters
        )
        
        if not is_valid:
            return False, f"Invalid arguments: {error}"
        
        return True, None
    
    def validate_arguments(
        self,
        args: ToolArguments,
        schema: dict
    ) -> Tuple[bool, List[str]]:
        """
        Валидировать аргументы против JSON Schema.
        
        Args:
            args: Аргументы инструмента
            schema: JSON Schema для валидации
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
            
        Example:
            >>> is_valid, errors = validator.validate_arguments(args, schema)
            >>> if not is_valid:
            ...     for error in errors:
            ...         print(f"- {error}")
        """
        # Делегируем валидацию в ToolArguments
        is_valid, error = args.validate_against_schema(schema)
        
        if not is_valid:
            return False, [error] if error else ["Unknown validation error"]
        
        return True, []
    
    def validate_permissions(
        self,
        tool: ToolSpecification,
        user_permission: ToolPermission
    ) -> bool:
        """
        Валидировать права доступа к инструменту.
        
        Args:
            tool: Спецификация инструмента
            user_permission: Уровень доступа пользователя
            
        Returns:
            True если доступ разрешен
            
        Example:
            >>> has_access = validator.validate_permissions(
            ...     tool_spec,
            ...     ToolPermission.read_write()
            ... )
            >>> if not has_access:
            ...     print("Access denied")
        """
        return user_permission.allows(tool.required_permission)
    
    def validate_required_fields(
        self,
        args: ToolArguments,
        required_fields: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Валидировать наличие обязательных полей.
        
        Args:
            args: Аргументы инструмента
            required_fields: Список обязательных полей
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_missing_fields)
            
        Example:
            >>> is_valid, missing = validator.validate_required_fields(
            ...     args,
            ...     ["path", "content"]
            ... )
            >>> if not is_valid:
            ...     print(f"Missing fields: {', '.join(missing)}")
        """
        missing_fields = []
        
        for field in required_fields:
            if not args.has(field):
                missing_fields.append(field)
        
        if missing_fields:
            return False, missing_fields
        
        return True, []
    
    def validate_field_types(
        self,
        args: ToolArguments,
        field_types: dict
    ) -> Tuple[bool, List[str]]:
        """
        Валидировать типы полей.
        
        Args:
            args: Аргументы инструмента
            field_types: Словарь {field_name: expected_type}
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_type_errors)
            
        Example:
            >>> is_valid, errors = validator.validate_field_types(
            ...     args,
            ...     {"path": str, "recursive": bool}
            ... )
        """
        type_errors = []
        
        for field, expected_type in field_types.items():
            if args.has(field):
                value = args.get(field)
                if not isinstance(value, expected_type):
                    type_errors.append(
                        f"Field '{field}': expected {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )
        
        if type_errors:
            return False, type_errors
        
        return True, []

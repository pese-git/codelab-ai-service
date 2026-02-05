"""
Value Object для аргументов инструмента.

Инкапсулирует валидацию и работу с аргументами инструментов.
"""

import json
from typing import Any, ClassVar, Dict, Optional, Tuple

from ...shared.value_object import ValueObject


class ToolArguments(ValueObject):
    """
    Value Object для аргументов инструмента.
    
    Валидация:
    - Валидный JSON
    - Соответствие схеме инструмента
    - Максимальный размер (100KB)
    
    Примеры:
        >>> args = ToolArguments.from_dict({"path": "test.py", "content": "print('hello')"})
        >>> args.get("path")
        'test.py'
        >>> args.has("content")
        True
    """
    
    arguments: Dict[str, Any]
    
    # Максимальный размер аргументов в байтах (100KB)
    MAX_SIZE_BYTES: ClassVar[int] = 100 * 1024
    
    def model_post_init(self, __context) -> None:
        """Валидация после инициализации."""
        super().model_post_init(__context)
        self._validate()
    
    def _validate(self) -> None:
        """
        Валидировать аргументы.
        
        Raises:
            ValueError: Если аргументы невалидны
        """
        # Проверка размера
        try:
            json_str = json.dumps(self.arguments)
            size_bytes = len(json_str.encode('utf-8'))
            
            if size_bytes > self.MAX_SIZE_BYTES:
                raise ValueError(
                    f"Arguments too large: {size_bytes} bytes "
                    f"(max {self.MAX_SIZE_BYTES} bytes)"
                )
        except (TypeError, ValueError) as e:
            raise ValueError(f"Arguments must be JSON-serializable: {e}")
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ToolArguments":
        """
        Создать ToolArguments из словаря.
        
        Args:
            data: Словарь с аргументами
            
        Returns:
            ToolArguments instance
            
        Example:
            >>> args = ToolArguments.from_dict({"path": "test.py"})
            >>> args.get("path")
            'test.py'
        """
        return ToolArguments(arguments=data)
    
    @staticmethod
    def from_json(json_str: str) -> "ToolArguments":
        """
        Создать ToolArguments из JSON строки.
        
        Args:
            json_str: JSON строка с аргументами
            
        Returns:
            ToolArguments instance
            
        Raises:
            ValueError: Если JSON невалиден
            
        Example:
            >>> args = ToolArguments.from_json('{"path": "test.py"}')
            >>> args.get("path")
            'test.py'
        """
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise ValueError("JSON must be an object (dict)")
            return ToolArguments(arguments=data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    @staticmethod
    def empty() -> "ToolArguments":
        """
        Создать пустые аргументы.
        
        Returns:
            ToolArguments с пустым словарем
            
        Example:
            >>> args = ToolArguments.empty()
            >>> len(args.to_dict())
            0
        """
        return ToolArguments(arguments={})
    
    def validate_against_schema(
        self,
        schema: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидировать аргументы против JSON Schema.
        
        Args:
            schema: JSON Schema для валидации
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            
        Example:
            >>> args = ToolArguments.from_dict({"path": "test.py"})
            >>> schema = {"required": ["path"], "properties": {"path": {"type": "string"}}}
            >>> is_valid, error = args.validate_against_schema(schema)
            >>> is_valid
            True
        """
        # Проверка обязательных полей
        required = schema.get("required", [])
        for field in required:
            if field not in self.arguments:
                return False, f"Missing required field: '{field}'"
        
        # Проверка типов (упрощенная)
        properties = schema.get("properties", {})
        for key, value in self.arguments.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type:
                    actual_type = self._get_json_type(value)
                    if actual_type != expected_type:
                        return False, (
                            f"Invalid type for '{key}': "
                            f"expected {expected_type}, got {actual_type}"
                        )
        
        return True, None
    
    def _get_json_type(self, value: Any) -> str:
        """Получить JSON тип значения."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        elif value is None:
            return "null"
        else:
            return "unknown"
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить значение аргумента.
        
        Args:
            key: Ключ аргумента
            default: Значение по умолчанию
            
        Returns:
            Значение аргумента или default
            
        Example:
            >>> args = ToolArguments.from_dict({"path": "test.py"})
            >>> args.get("path")
            'test.py'
            >>> args.get("missing", "default")
            'default'
        """
        return self.arguments.get(key, default)
    
    def has(self, key: str) -> bool:
        """
        Проверить наличие аргумента.
        
        Args:
            key: Ключ аргумента
            
        Returns:
            True если аргумент присутствует
            
        Example:
            >>> args = ToolArguments.from_dict({"path": "test.py"})
            >>> args.has("path")
            True
            >>> args.has("missing")
            False
        """
        return key in self.arguments
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь.
        
        Returns:
            Словарь с аргументами
            
        Example:
            >>> args = ToolArguments.from_dict({"path": "test.py"})
            >>> args.to_dict()
            {'path': 'test.py'}
        """
        return self.arguments.copy()
    
    def to_json(self) -> str:
        """
        Преобразовать в JSON строку.
        
        Returns:
            JSON строка
            
        Example:
            >>> args = ToolArguments.from_dict({"path": "test.py"})
            >>> args.to_json()
            '{"path": "test.py"}'
        """
        return json.dumps(self.arguments)
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolArguments({self.arguments})"

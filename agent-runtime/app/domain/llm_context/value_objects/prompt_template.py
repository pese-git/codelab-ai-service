"""
Value Object для шаблона промпта.

Инкапсулирует валидацию и рендеринг шаблонов промптов.
"""

import re
from typing import Dict, Any, List, Set, ClassVar, Pattern
from pydantic import Field, field_validator

from ...shared.value_object import ValueObject


class PromptTemplate(ValueObject):
    """
    Value Object для шаблона промпта.
    
    Поддерживает простые плейсхолдеры в формате {variable}.
    
    Валидация:
    - Не пустой
    - Максимальная длина: 50000 символов
    - Валидные плейсхолдеры {variable}
    - Все плейсхолдеры должны быть заполнены при рендеринге
    
    Examples:
        >>> template = PromptTemplate(
        ...     template="Hello, {name}! You are a {role}."
        ... )
        >>> template.render({"name": "Alice", "role": "developer"})
        'Hello, Alice! You are a developer.'
        
        >>> template.get_variables()
        ['name', 'role']
        
        >>> template.validate_variables({"name": "Alice", "role": "dev"})
        True
    """
    
    template: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Шаблон промпта с плейсхолдерами {variable}"
    )
    
    # Регулярное выражение для поиска плейсхолдеров
    PLACEHOLDER_PATTERN: ClassVar[Pattern] = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    
    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        """Валидация шаблона."""
        if not v or not v.strip():
            raise ValueError("Prompt template cannot be empty")
        
        # Проверка на валидность плейсхолдеров
        # Находим все {something}
        all_braces = re.findall(r'\{[^}]*\}', v)
        for brace in all_braces:
            # Проверяем что это валидный плейсхолдер
            if not cls.PLACEHOLDER_PATTERN.match(brace):
                raise ValueError(
                    f"Invalid placeholder '{brace}'. "
                    f"Placeholders must be in format {{variable_name}}"
                )
        
        return v
    
    @staticmethod
    def from_string(template: str) -> "PromptTemplate":
        """
        Создать PromptTemplate из строки.
        
        Args:
            template: Строка шаблона
            
        Returns:
            PromptTemplate instance
            
        Example:
            >>> template = PromptTemplate.from_string("Hello, {name}!")
        """
        return PromptTemplate(template=template)
    
    def get_variables(self) -> List[str]:
        """
        Получить список переменных в шаблоне.
        
        Returns:
            Список имен переменных (без дубликатов, в порядке появления)
            
        Example:
            >>> template = PromptTemplate(template="Hello, {name}! {name} is {role}.")
            >>> template.get_variables()
            ['name', 'role']
        """
        matches = self.PLACEHOLDER_PATTERN.findall(self.template)
        # Убираем дубликаты, сохраняя порядок
        seen: Set[str] = set()
        result = []
        for var in matches:
            if var not in seen:
                seen.add(var)
                result.append(var)
        return result
    
    def validate_variables(self, variables: Dict[str, Any]) -> bool:
        """
        Проверить, что все переменные шаблона присутствуют.
        
        Args:
            variables: Словарь переменных для проверки
            
        Returns:
            True если все переменные присутствуют
            
        Example:
            >>> template = PromptTemplate(template="Hello, {name}!")
            >>> template.validate_variables({"name": "Alice"})
            True
            >>> template.validate_variables({"other": "value"})
            False
        """
        required_vars = set(self.get_variables())
        provided_vars = set(variables.keys())
        return required_vars.issubset(provided_vars)
    
    def get_missing_variables(self, variables: Dict[str, Any]) -> List[str]:
        """
        Получить список отсутствующих переменных.
        
        Args:
            variables: Словарь переменных для проверки
            
        Returns:
            Список отсутствующих переменных
            
        Example:
            >>> template = PromptTemplate(template="Hello, {name}! You are {role}.")
            >>> template.get_missing_variables({"name": "Alice"})
            ['role']
        """
        required_vars = set(self.get_variables())
        provided_vars = set(variables.keys())
        missing = required_vars - provided_vars
        return sorted(list(missing))
    
    def render(self, variables: Dict[str, Any]) -> str:
        """
        Отрендерить шаблон с переменными.
        
        Args:
            variables: Словарь переменных для подстановки
            
        Returns:
            Отрендеренная строка
            
        Raises:
            ValueError: Если отсутствуют обязательные переменные
            
        Example:
            >>> template = PromptTemplate(template="Hello, {name}!")
            >>> template.render({"name": "Alice"})
            'Hello, Alice!'
        """
        # Проверка наличия всех переменных
        missing = self.get_missing_variables(variables)
        if missing:
            raise ValueError(
                f"Missing required variables: {', '.join(missing)}"
            )
        
        # Рендеринг
        result = self.template
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            # Преобразуем значение в строку
            str_value = str(var_value) if var_value is not None else ""
            result = result.replace(placeholder, str_value)
        
        return result
    
    def has_variables(self) -> bool:
        """
        Проверить, содержит ли шаблон переменные.
        
        Returns:
            True если есть хотя бы одна переменная
            
        Example:
            >>> PromptTemplate(template="Hello, {name}!").has_variables()
            True
            >>> PromptTemplate(template="Hello, world!").has_variables()
            False
        """
        return len(self.get_variables()) > 0
    
    def preview(self, max_length: int = 100) -> str:
        """
        Получить превью шаблона.
        
        Args:
            max_length: Максимальная длина превью
            
        Returns:
            Превью шаблона (обрезанное если необходимо)
            
        Example:
            >>> template = PromptTemplate(template="A" * 200)
            >>> len(template.preview(50))
            53  # 50 + '...'
        """
        if len(self.template) <= max_length:
            return self.template
        return self.template[:max_length] + "..."
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.template
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        preview = self.preview(50)
        variables = self.get_variables()
        return f"<PromptTemplate(variables={variables}, preview='{preview}')>"

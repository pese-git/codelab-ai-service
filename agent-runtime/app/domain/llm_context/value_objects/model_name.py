"""
Value Object для имени LLM модели.

Инкапсулирует валидацию и работу с именами моделей.
"""

from typing import Optional, Dict, List, ClassVar
from pydantic import Field, field_validator

from ...shared.value_object import ValueObject


class ModelName(ValueObject):
    """
    Value Object для имени LLM модели.
    
    Валидация:
    - Не пустое
    - Длина: 1-100 символов
    - Формат: provider/model или просто model
    - Известные провайдеры: openai, anthropic, google, cohere, etc.
    
    Примеры:
        >>> model = ModelName(value="gpt-4")
        >>> model.get_provider()
        'openai'
        
        >>> model = ModelName(value="claude-3-opus-20240229")
        >>> model.is_anthropic()
        True
        
        >>> model = ModelName(value="openai/gpt-4-turbo")
        >>> model.get_model()
        'gpt-4-turbo'
    """
    
    value: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Имя модели"
    )
    
    # Известные провайдеры и их модели
    PROVIDER_PATTERNS: ClassVar[Dict[str, List[str]]] = {
        "openai": ["gpt-3.5", "gpt-4", "gpt-4-turbo", "gpt-4o"],
        "anthropic": ["claude-3", "claude-2", "claude-instant"],
        "google": ["gemini", "palm"],
        "cohere": ["command", "coral"],
        "meta": ["llama"],
        "mistral": ["mistral", "mixtral"],
    }
    
    @field_validator("value")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        """Валидация имени модели."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        
        # Проверка на недопустимые символы
        if any(char in v for char in ["\n", "\r", "\t"]):
            raise ValueError("Model name cannot contain whitespace characters")
        
        return v.strip()
    
    @staticmethod
    def from_string(value: str) -> "ModelName":
        """
        Создать ModelName из строки.
        
        Args:
            value: Строковое представление модели
            
        Returns:
            ModelName instance
            
        Example:
            >>> model = ModelName.from_string("gpt-4")
        """
        return ModelName(value=value)
    
    def get_provider(self) -> Optional[str]:
        """
        Определить провайдера модели.
        
        Returns:
            Имя провайдера или None если не определен
            
        Example:
            >>> ModelName(value="gpt-4").get_provider()
            'openai'
            >>> ModelName(value="claude-3-opus-20240229").get_provider()
            'anthropic'
        """
        # Если формат provider/model
        if "/" in self.value:
            return self.value.split("/")[0].lower()
        
        # Определение по паттернам
        model_lower = self.value.lower()
        for provider, patterns in self.PROVIDER_PATTERNS.items():
            if any(pattern in model_lower for pattern in patterns):
                return provider
        
        return None
    
    def get_model(self) -> str:
        """
        Получить имя модели без провайдера.
        
        Returns:
            Имя модели
            
        Example:
            >>> ModelName(value="openai/gpt-4-turbo").get_model()
            'gpt-4-turbo'
            >>> ModelName(value="gpt-4").get_model()
            'gpt-4'
        """
        if "/" in self.value:
            return self.value.split("/", 1)[1]
        return self.value
    
    def is_openai(self) -> bool:
        """
        Проверить, является ли модель OpenAI.
        
        Returns:
            True если модель от OpenAI
            
        Example:
            >>> ModelName(value="gpt-4").is_openai()
            True
        """
        return self.get_provider() == "openai"
    
    def is_anthropic(self) -> bool:
        """
        Проверить, является ли модель Anthropic.
        
        Returns:
            True если модель от Anthropic
            
        Example:
            >>> ModelName(value="claude-3-opus-20240229").is_anthropic()
            True
        """
        return self.get_provider() == "anthropic"
    
    def is_google(self) -> bool:
        """
        Проверить, является ли модель Google.
        
        Returns:
            True если модель от Google
        """
        return self.get_provider() == "google"
    
    def supports_tools(self) -> bool:
        """
        Проверить, поддерживает ли модель function calling.
        
        Returns:
            True если модель поддерживает инструменты
            
        Example:
            >>> ModelName(value="gpt-4").supports_tools()
            True
            >>> ModelName(value="gpt-3.5-turbo-instruct").supports_tools()
            False
        """
        model_lower = self.value.lower()
        
        # OpenAI models with tool support
        if self.is_openai():
            return any(pattern in model_lower for pattern in ["gpt-4", "gpt-3.5-turbo"])
        
        # Anthropic models with tool support
        if self.is_anthropic():
            return "claude-3" in model_lower or "claude-2.1" in model_lower
        
        # Google models with tool support
        if self.is_google():
            return "gemini" in model_lower
        
        # По умолчанию считаем что поддерживает
        return True
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self.value
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        provider = self.get_provider()
        return f"<ModelName(value='{self.value}', provider='{provider}')>"

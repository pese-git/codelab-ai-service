"""
Value Object для лимита токенов LLM.

Инкапсулирует валидацию и работу с лимитами токенов.
"""

from typing import TYPE_CHECKING, ClassVar
from pydantic import Field, field_validator

from ...shared.value_object import ValueObject

if TYPE_CHECKING:
    from .model_name import ModelName
    from ...entities.llm_response import TokenUsage


class TokenLimit(ValueObject):
    """
    Value Object для лимита токенов.
    
    Валидация:
    - Положительное число
    - Разумные значения (100-200000)
    - Не превышает максимум модели
    
    Examples:
        >>> limit = TokenLimit(value=4096)
        >>> limit.value
        4096
        
        >>> limit = TokenLimit.for_gpt4()
        >>> limit.value
        8192
        
        >>> usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        >>> limit.is_within_limit(usage)
        True
        >>> limit.remaining(usage)
        3946
    """
    
    value: int = Field(
        ...,
        ge=100,
        le=200000,
        description="Лимит токенов"
    )
    
    # Предустановленные лимиты для популярных моделей
    GPT_3_5_TURBO: ClassVar[int] = 4096
    GPT_4: ClassVar[int] = 8192
    GPT_4_TURBO: ClassVar[int] = 128000
    GPT_4O: ClassVar[int] = 128000
    CLAUDE_3_OPUS: ClassVar[int] = 200000
    CLAUDE_3_SONNET: ClassVar[int] = 200000
    CLAUDE_3_HAIKU: ClassVar[int] = 200000
    GEMINI_PRO: ClassVar[int] = 32768
    
    @field_validator("value")
    @classmethod
    def validate_token_limit(cls, v: int) -> int:
        """Валидация лимита токенов."""
        if not isinstance(v, int):
            raise ValueError("Token limit must be an integer")
        
        if v < 100:
            raise ValueError("Token limit must be at least 100")
        
        if v > 200000:
            raise ValueError("Token limit cannot exceed 200000")
        
        return v
    
    @staticmethod
    def for_model(model: "ModelName") -> "TokenLimit":
        """
        Создать TokenLimit для конкретной модели.
        
        Args:
            model: ModelName для определения лимита
            
        Returns:
            TokenLimit с соответствующим значением
            
        Example:
            >>> from .model_name import ModelName
            >>> model = ModelName(value="gpt-4")
            >>> limit = TokenLimit.for_model(model)
            >>> limit.value
            8192
        """
        model_str = model.value.lower()
        
        # GPT-4o
        if "gpt-4o" in model_str:
            return TokenLimit(value=TokenLimit.GPT_4O)
        
        # GPT-4 Turbo
        if "gpt-4-turbo" in model_str or "gpt-4-1106" in model_str or "gpt-4-0125" in model_str:
            return TokenLimit(value=TokenLimit.GPT_4_TURBO)
        
        # GPT-4
        if "gpt-4" in model_str:
            return TokenLimit(value=TokenLimit.GPT_4)
        
        # GPT-3.5 Turbo
        if "gpt-3.5" in model_str:
            return TokenLimit(value=TokenLimit.GPT_3_5_TURBO)
        
        # Claude 3
        if "claude-3" in model_str:
            if "opus" in model_str:
                return TokenLimit(value=TokenLimit.CLAUDE_3_OPUS)
            elif "sonnet" in model_str:
                return TokenLimit(value=TokenLimit.CLAUDE_3_SONNET)
            elif "haiku" in model_str:
                return TokenLimit(value=TokenLimit.CLAUDE_3_HAIKU)
            return TokenLimit(value=TokenLimit.CLAUDE_3_SONNET)
        
        # Gemini
        if "gemini" in model_str:
            return TokenLimit(value=TokenLimit.GEMINI_PRO)
        
        # По умолчанию
        return TokenLimit(value=4096)
    
    @staticmethod
    def for_gpt35() -> "TokenLimit":
        """
        Создать лимит для GPT-3.5 Turbo (4096).
        
        Returns:
            TokenLimit с value=4096
        """
        return TokenLimit(value=TokenLimit.GPT_3_5_TURBO)
    
    @staticmethod
    def for_gpt4() -> "TokenLimit":
        """
        Создать лимит для GPT-4 (8192).
        
        Returns:
            TokenLimit с value=8192
        """
        return TokenLimit(value=TokenLimit.GPT_4)
    
    @staticmethod
    def for_gpt4_turbo() -> "TokenLimit":
        """
        Создать лимит для GPT-4 Turbo (128000).
        
        Returns:
            TokenLimit с value=128000
        """
        return TokenLimit(value=TokenLimit.GPT_4_TURBO)
    
    @staticmethod
    def for_claude3() -> "TokenLimit":
        """
        Создать лимит для Claude 3 (200000).
        
        Returns:
            TokenLimit с value=200000
        """
        return TokenLimit(value=TokenLimit.CLAUDE_3_SONNET)
    
    def is_within_limit(self, usage: "TokenUsage") -> bool:
        """
        Проверить, не превышен ли лимит.
        
        Args:
            usage: TokenUsage для проверки
            
        Returns:
            True если использование в пределах лимита
            
        Example:
            >>> from ...entities.llm_response import TokenUsage
            >>> limit = TokenLimit(value=4096)
            >>> usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
            >>> limit.is_within_limit(usage)
            True
        """
        return usage.total_tokens <= self.value
    
    def remaining(self, usage: "TokenUsage") -> int:
        """
        Получить количество оставшихся токенов.
        
        Args:
            usage: TokenUsage для расчета
            
        Returns:
            Количество оставшихся токенов (может быть отрицательным)
            
        Example:
            >>> from ...entities.llm_response import TokenUsage
            >>> limit = TokenLimit(value=4096)
            >>> usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
            >>> limit.remaining(usage)
            3946
        """
        return self.value - usage.total_tokens
    
    def percentage_used(self, usage: "TokenUsage") -> float:
        """
        Получить процент использования лимита.
        
        Args:
            usage: TokenUsage для расчета
            
        Returns:
            Процент использования (0.0-100.0+)
            
        Example:
            >>> from ...entities.llm_response import TokenUsage
            >>> limit = TokenLimit(value=1000)
            >>> usage = TokenUsage(prompt_tokens=200, completion_tokens=50)
            >>> limit.percentage_used(usage)
            25.0
        """
        if self.value == 0:
            return 100.0
        return (usage.total_tokens / self.value) * 100.0
    
    def is_nearly_exhausted(self, usage: "TokenUsage", threshold: float = 0.9) -> bool:
        """
        Проверить, близок ли лимит к исчерпанию.
        
        Args:
            usage: TokenUsage для проверки
            threshold: Порог (0.0-1.0), по умолчанию 0.9 (90%)
            
        Returns:
            True если использовано >= threshold от лимита
            
        Example:
            >>> from ...entities.llm_response import TokenUsage
            >>> limit = TokenLimit(value=1000)
            >>> usage = TokenUsage(prompt_tokens=900, completion_tokens=50)
            >>> limit.is_nearly_exhausted(usage)
            True
        """
        return usage.total_tokens >= (self.value * threshold)
    
    def __str__(self) -> str:
        """Строковое представление."""
        return f"{self.value}"
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        return f"<TokenLimit(value={self.value})>"
    
    def __int__(self) -> int:
        """Преобразование в int."""
        return self.value

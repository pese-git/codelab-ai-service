"""
AgentId Value Object.

Инкапсулирует идентификатор агента с валидацией и типобезопасностью.
"""

import uuid
from typing import Optional, Any
from pydantic import field_validator

from ...shared.value_object import ValueObject


class AgentId(ValueObject):
    """
    Value Object для идентификатора агента.
    
    Обеспечивает:
    - Валидацию формата ID
    - Типобезопасность (нельзя перепутать с другими ID)
    - Иммутабельность
    - Генерацию новых ID
    
    Атрибуты:
        value: Строковое значение ID (UUID без префикса)
    
    Пример:
        >>> agent_id = AgentId.generate()
        >>> agent_id.value
        '123e4567-e89b-12d3-a456-426614174000'
        
        >>> agent_id = AgentId(value="123e4567-e89b-12d3-a456-426614174000")
        >>> str(agent_id)
        '123e4567-e89b-12d3-a456-426614174000'
    """
    
    value: str
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        """
        Валидация значения ID.
        
        Args:
            v: Значение для валидации
            
        Returns:
            Валидированное значение
            
        Raises:
            ValueError: Если ID невалиден
        """
        if not v:
            raise ValueError("Agent ID не может быть пустым")
        
        if not isinstance(v, str):
            raise ValueError(f"Agent ID должен быть строкой, получен {type(v).__name__}")
        
        v = v.strip()
        
        if not v:
            raise ValueError("Agent ID не может состоять только из пробелов")
        
        if len(v) > 255:
            raise ValueError(f"Agent ID слишком длинный: {len(v)} символов (максимум 255)")
        
        # Проверка на недопустимые символы
        if any(char in v for char in ['\n', '\r', '\t', '\0']):
            raise ValueError("Agent ID содержит недопустимые символы")
        
        return v
    
    @staticmethod
    def generate() -> "AgentId":
        """
        Сгенерировать новый уникальный AgentId.
        
        Генерирует чистый UUID без префикса для совместимости с БД VARCHAR(36).
        
        Returns:
            Новый AgentId с уникальным UUID
            
        Пример:
            >>> agent_id = AgentId.generate()
            >>> len(agent_id.value)
            36
        """
        unique_id = str(uuid.uuid4())
        return AgentId(value=unique_id)
    
    @staticmethod
    def from_session_id(session_id: str) -> "AgentId":
        """
        Создать AgentId из session ID (генерирует новый UUID).
        
        ВАЖНО: Теперь генерирует новый UUID вместо использования session_id,
        чтобы соответствовать ограничению БД VARCHAR(36).
        
        Args:
            session_id: ID сессии (используется только для валидации)
            
        Returns:
            AgentId с новым UUID
            
        Пример:
            >>> agent_id = AgentId.from_session_id("session-123")
            >>> len(agent_id.value)
            36
        """
        if not session_id:
            raise ValueError("Session ID не может быть пустым")
        
        # Генерируем новый UUID вместо использования session_id
        return AgentId.generate()
    
    def __str__(self) -> str:
        """Строковое представление."""
        return self._value
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"AgentId('{self._value}')"
    
    def __eq__(self, other: object) -> bool:
        """
        Сравнение на равенство.
        
        Args:
            other: Объект для сравнения
            
        Returns:
            True если ID равны
        """
        if not isinstance(other, AgentId):
            return False
        return self._value == other._value
    
    def __hash__(self) -> int:
        """
        Хеш для использования в множествах и словарях.
        
        Returns:
            Хеш значения ID
        """
        return hash(self._value)
    
    def __lt__(self, other: "AgentId") -> bool:
        """
        Сравнение для сортировки.
        
        Args:
            other: Другой AgentId
            
        Returns:
            True если self < other
        """
        if not isinstance(other, AgentId):
            return NotImplemented
        return self._value < other._value

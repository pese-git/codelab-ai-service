"""
AgentId Value Object.

Инкапсулирует идентификатор агента с валидацией и типобезопасностью.
"""

import uuid
from typing import Optional

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
        value: Строковое значение ID
    
    Пример:
        >>> agent_id = AgentId.generate()
        >>> agent_id.value
        'agent-123e4567-e89b-12d3-a456-426614174000'
        
        >>> agent_id = AgentId("agent-123")
        >>> str(agent_id)
        'agent-123'
    """
    
    def __init__(self, value: str) -> None:
        """
        Создать AgentId с валидацией.
        
        Args:
            value: Строковое значение ID
            
        Raises:
            ValueError: Если ID невалиден
            
        Пример:
            >>> agent_id = AgentId("agent-123")
            >>> agent_id.value
            'agent-123'
        """
        if not value:
            raise ValueError("Agent ID не может быть пустым")
        
        if not isinstance(value, str):
            raise ValueError(f"Agent ID должен быть строкой, получен {type(value).__name__}")
        
        if len(value) > 255:
            raise ValueError(f"Agent ID слишком длинный: {len(value)} символов (максимум 255)")
        
        # Проверка на недопустимые символы
        if any(char in value for char in ['\n', '\r', '\t', '\0']):
            raise ValueError("Agent ID содержит недопустимые символы")
        
        self._value = value.strip()
        
        if not self._value:
            raise ValueError("Agent ID не может состоять только из пробелов")
    
    @property
    def value(self) -> str:
        """Получить строковое значение ID."""
        return self._value
    
    @staticmethod
    def generate(prefix: str = "agent") -> "AgentId":
        """
        Сгенерировать новый уникальный AgentId.
        
        Args:
            prefix: Префикс для ID (по умолчанию "agent")
            
        Returns:
            Новый AgentId с уникальным значением
            
        Пример:
            >>> agent_id = AgentId.generate()
            >>> agent_id.value.startswith("agent-")
            True
            
            >>> custom_id = AgentId.generate(prefix="ctx")
            >>> custom_id.value.startswith("ctx-")
            True
        """
        unique_id = str(uuid.uuid4())
        return AgentId(f"{prefix}-{unique_id}")
    
    @staticmethod
    def from_session_id(session_id: str) -> "AgentId":
        """
        Создать AgentId из session ID.
        
        Полезно для создания связанного контекста агента.
        
        Args:
            session_id: ID сессии
            
        Returns:
            AgentId связанный с сессией
            
        Пример:
            >>> agent_id = AgentId.from_session_id("session-123")
            >>> agent_id.value
            'agent-session-123'
        """
        if not session_id:
            raise ValueError("Session ID не может быть пустым")
        
        # Убираем префикс "session-" если есть
        clean_id = session_id.replace("session-", "")
        return AgentId(f"agent-{clean_id}")
    
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

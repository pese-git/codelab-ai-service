"""
PolicyRule Value Object.

Правило политики HITL для определения действия на основе условий.
"""

import re
from typing import Any, Dict, Optional

from app.domain.shared.value_object import ValueObject
from ..value_objects.approval_type import ApprovalType
from ..value_objects.policy_action import PolicyAction


class PolicyRule(ValueObject):
    """
    Правило политики HITL.
    
    Определяет условие (pattern matching) и действие для запросов на утверждение.
    
    Обеспечивает:
    - Сопоставление по типу запроса
    - Сопоставление по паттерну subject (regex)
    - Дополнительные условия (опционально)
    - Приоритет для разрешения конфликтов
    
    Attributes:
        approval_type: Тип запроса (tool_call, plan_execution, etc.)
        subject_pattern: Regex паттерн для subject (имя инструмента, название плана)
        action: Действие при совпадении правила
        priority: Приоритет (выше = важнее), по умолчанию 0
        conditions: Дополнительные условия (опционально)
    
    Примеры:
        >>> # Правило: все write_file требуют решения пользователя
        >>> rule = PolicyRule(
        ...     approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
        ...     subject_pattern="write_file",
        ...     action=PolicyAction(PolicyActionEnum.ASK_USER),
        ...     priority=10
        ... )
        >>> 
        >>> # Проверка совпадения
        >>> rule.matches("write_file", {})
        True
    """
    
    def __init__(
        self,
        approval_type: ApprovalType,
        subject_pattern: str,
        action: PolicyAction,
        priority: int = 0,
        conditions: Optional[Dict[str, Any]] = None,
    ):
        """
        Создать PolicyRule.
        
        Args:
            approval_type: Тип запроса
            subject_pattern: Regex паттерн для subject
            action: Действие при совпадении
            priority: Приоритет (выше = важнее)
            conditions: Дополнительные условия
            
        Raises:
            ValueError: Если subject_pattern невалидный regex
        """
        # Валидация regex паттерна
        try:
            re.compile(subject_pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{subject_pattern}': {e}")
        
        self._approval_type = approval_type
        self._subject_pattern = subject_pattern
        self._action = action
        self._priority = priority
        self._conditions = conditions or {}
    
    @property
    def approval_type(self) -> ApprovalType:
        """Получить тип запроса."""
        return self._approval_type
    
    @property
    def subject_pattern(self) -> str:
        """Получить regex паттерн."""
        return self._subject_pattern
    
    @property
    def action(self) -> PolicyAction:
        """Получить действие."""
        return self._action
    
    @property
    def priority(self) -> int:
        """Получить приоритет."""
        return self._priority
    
    @property
    def conditions(self) -> Dict[str, Any]:
        """Получить дополнительные условия."""
        return self._conditions.copy()
    
    def matches(
        self,
        subject: str,
        request_data: Dict[str, Any],
    ) -> bool:
        """
        Проверить, соответствует ли запрос этому правилу.
        
        Args:
            subject: Subject запроса (имя инструмента, название плана)
            request_data: Данные запроса для проверки условий
            
        Returns:
            True если правило соответствует запросу
            
        Примеры:
            >>> rule = PolicyRule(
            ...     approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            ...     subject_pattern="write_.*",
            ...     action=PolicyAction(PolicyActionEnum.ASK_USER)
            ... )
            >>> rule.matches("write_file", {})
            True
            >>> rule.matches("read_file", {})
            False
        """
        # Проверка subject паттерна
        if not re.match(self._subject_pattern, subject):
            return False
        
        # Проверка дополнительных условий
        if self._conditions:
            return self._check_conditions(request_data)
        
        return True
    
    def _check_conditions(self, request_data: Dict[str, Any]) -> bool:
        """
        Проверить дополнительные условия.
        
        Поддерживаемые операторы:
        - key_gt: больше чем
        - key_lt: меньше чем
        - key_eq: равно
        - key_contains: содержит (для строк/списков)
        
        Args:
            request_data: Данные запроса
            
        Returns:
            True если все условия выполнены
        """
        for key, expected_value in self._conditions.items():
            # Операторы сравнения
            if key.endswith("_gt"):
                field_key = key[:-3]
                if field_key not in request_data:
                    return False
                if not (request_data[field_key] > expected_value):
                    return False
            
            elif key.endswith("_lt"):
                field_key = key[:-3]
                if field_key not in request_data:
                    return False
                if not (request_data[field_key] < expected_value):
                    return False
            
            elif key.endswith("_eq"):
                field_key = key[:-3]
                if field_key not in request_data:
                    return False
                if request_data[field_key] != expected_value:
                    return False
            
            elif key.endswith("_contains"):
                field_key = key[:-9]
                if field_key not in request_data:
                    return False
                if expected_value not in request_data[field_key]:
                    return False
            
            else:
                # Прямое сравнение
                if key not in request_data:
                    return False
                if request_data[key] != expected_value:
                    return False
        
        return True
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение по значению."""
        if not isinstance(other, PolicyRule):
            return False
        return (
            self._approval_type == other._approval_type
            and self._subject_pattern == other._subject_pattern
            and self._action == other._action
            and self._priority == other._priority
            and self._conditions == other._conditions
        )
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах и словарях."""
        return hash((
            self._approval_type,
            self._subject_pattern,
            self._action,
            self._priority,
            frozenset(self._conditions.items()) if self._conditions else frozenset(),
        ))
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return (
            f"PolicyRule(type={self._approval_type}, "
            f"pattern='{self._subject_pattern}', "
            f"action={self._action}, "
            f"priority={self._priority})"
        )

"""
Доменные исключения.

Исключения для ошибок бизнес-логики и нарушения бизнес-правил.
"""

from typing import Optional, Dict, Any
from .base import DomainError


class SessionNotFoundError(DomainError):
    """
    Исключение: сессия не найдена.
    
    Выбрасывается когда запрашиваемая сессия не существует в системе.
    
    Пример:
        >>> raise SessionNotFoundError("session-123")
    """
    
    def __init__(self, session_id: str, details: Optional[Dict[str, Any]] = None):
        """
        Args:
            session_id: ID несуществующей сессии
            details: Дополнительные детали
        """
        message = f"Сессия '{session_id}' не найдена"
        super().__init__(
            message=message,
            details={"session_id": session_id, **(details or {})},
            error_code="SESSION_NOT_FOUND"
        )


class SessionAlreadyExistsError(DomainError):
    """
    Исключение: сессия уже существует.
    
    Выбрасывается при попытке создать сессию с ID,
    который уже используется.
    
    Пример:
        >>> raise SessionAlreadyExistsError("session-123")
    """
    
    def __init__(self, session_id: str, details: Optional[Dict[str, Any]] = None):
        """
        Args:
            session_id: ID существующей сессии
            details: Дополнительные детали
        """
        message = f"Сессия '{session_id}' уже существует"
        super().__init__(
            message=message,
            details={"session_id": session_id, **(details or {})},
            error_code="SESSION_ALREADY_EXISTS"
        )


class AgentSwitchError(DomainError):
    """
    Исключение: ошибка переключения агента.
    
    Выбрасывается когда переключение агента невозможно
    или нарушает бизнес-правила.
    
    Пример:
        >>> raise AgentSwitchError(
        ...     from_agent="coder",
        ...     to_agent="architect",
        ...     reason="Too many switches"
        ... )
    """
    
    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            from_agent: Текущий агент
            to_agent: Целевой агент
            reason: Причина ошибки
            details: Дополнительные детали
        """
        message = (
            f"Невозможно переключиться с агента '{from_agent}' "
            f"на агента '{to_agent}': {reason}"
        )
        super().__init__(
            message=message,
            details={
                "from_agent": from_agent,
                "to_agent": to_agent,
                "reason": reason,
                **(details or {})
            },
            error_code="AGENT_SWITCH_ERROR"
        )


class MessageValidationError(DomainError):
    """
    Исключение: ошибка валидации сообщения.
    
    Выбрасывается когда сообщение не соответствует
    требованиям бизнес-логики.
    
    Пример:
        >>> raise MessageValidationError(
        ...     field="content",
        ...     reason="Message is too long"
        ... )
    """
    
    def __init__(
        self,
        field: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            field: Поле с ошибкой
            reason: Причина ошибки
            details: Дополнительные детали
        """
        message = f"Ошибка валидации поля '{field}': {reason}"
        super().__init__(
            message=message,
            details={
                "field": field,
                "reason": reason,
                **(details or {})
            },
            error_code="MESSAGE_VALIDATION_ERROR"
        )


class ConcurrencyError(DomainError):
    """
    Исключение: ошибка конкурентного доступа.
    
    Выбрасывается когда обнаружен конфликт при
    одновременном изменении одной сущности.
    
    Пример:
        >>> raise ConcurrencyError(
        ...     entity_id="session-123",
        ...     entity_type="Session"
        ... )
    """
    
    def __init__(
        self,
        entity_id: str,
        entity_type: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            entity_id: ID сущности
            entity_type: Тип сущности
            details: Дополнительные детали
        """
        message = (
            f"Конфликт конкурентного доступа к {entity_type} "
            f"с ID '{entity_id}'"
        )
        super().__init__(
            message=message,
            details={
                "entity_id": entity_id,
                "entity_type": entity_type,
                **(details or {})
            },
            error_code="CONCURRENCY_ERROR"
        )

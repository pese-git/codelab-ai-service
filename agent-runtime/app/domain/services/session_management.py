"""
Доменный сервис управления сессиями.

Инкапсулирует бизнес-логику работы с сессиями,
которая не принадлежит конкретной сущности.
"""

import uuid
import logging
from typing import Optional, List
from datetime import datetime, timezone

from ..entities.session import Session
from ..entities.message import Message
from ..repositories.session_repository import SessionRepository
from ..events.session_events import (
    SessionCreated,
    MessageReceived,
    ConversationCompleted,
    SessionDeactivated
)
from ...core.errors import SessionNotFoundError, SessionAlreadyExistsError

logger = logging.getLogger("agent-runtime.domain.session_management")


class SessionManagementService:
    """
    Доменный сервис для управления сессиями.
    
    Координирует операции с сессиями и публикует доменные события.
    Инкапсулирует бизнес-правила и валидацию.
    
    Атрибуты:
        _repository: Репозиторий сессий
        _event_publisher: Функция для публикации событий (опционально)
    
    Пример:
        >>> service = SessionManagementService(repository)
        >>> session = await service.create_session("session-1")
    """
    
    def __init__(
        self,
        repository: SessionRepository,
        event_publisher=None
    ):
        """
        Инициализация сервиса.
        
        Args:
            repository: Репозиторий для работы с сессиями
            event_publisher: Функция для публикации событий (опционально)
        """
        self._repository = repository
        self._event_publisher = event_publisher
    
    async def create_session(
        self,
        session_id: Optional[str] = None
    ) -> Session:
        """
        Создать новую сессию.
        
        Args:
            session_id: ID сессии (если None, генерируется автоматически)
            
        Returns:
            Созданная сессия
            
        Raises:
            SessionAlreadyExistsError: Если сессия с таким ID уже существует
            
        Пример:
            >>> session = await service.create_session()
            >>> session.is_active
            True
        """
        # Генерировать ID если не указан
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Проверить, что сессия не существует
        existing = await self._repository.find_by_id(session_id)
        if existing:
            raise SessionAlreadyExistsError(session_id)
        
        # Создать новую сессию
        session = Session(
            id=session_id,
            last_activity=datetime.now(timezone.utc)
        )
        
        # Сохранить в репозитории
        await self._repository.save(session)
        
        logger.info(f"Создана новая сессия: {session_id}")
        
        # Опубликовать событие
        if self._event_publisher:
            await self._event_publisher(
                SessionCreated(
                    aggregate_id=session_id,
                    session_id=session_id,
                    created_by="system"
                )
            )
        
        return session
    
    async def get_session(self, session_id: str) -> Session:
        """
        Получить сессию по ID.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Сессия
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            
        Пример:
            >>> session = await service.get_session("session-123")
        """
        session = await self._repository.find_by_id(session_id)
        
        if not session:
            raise SessionNotFoundError(session_id)
        
        return session
    
    async def get_or_create_session(
        self,
        session_id: str
    ) -> Session:
        """
        Получить существующую сессию или создать новую.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Существующая или новая сессия
            
        Пример:
            >>> session = await service.get_or_create_session("session-123")
        """
        try:
            return await self.get_session(session_id)
        except SessionNotFoundError:
            return await self.create_session(session_id)
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_calls: Optional[list] = None
    ) -> Message:
        """
        Добавить сообщение в сессию.
        
        Args:
            session_id: ID сессии
            role: Роль отправителя
            content: Содержимое сообщения
            name: Имя отправителя (опционально)
            tool_call_id: ID вызова инструмента (опционально)
            tool_calls: Вызовы инструментов (опционально)
            
        Returns:
            Созданное сообщение
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            
        Пример:
            >>> message = await service.add_message(
            ...     session_id="session-123",
            ...     role="user",
            ...     content="Привет!"
            ... )
        """
        # Получить сессию
        session = await self.get_session(session_id)
        
        # Создать сообщение
        message = Message(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls
        )
        
        # Добавить в сессию (валидация внутри)
        session.add_message(message)
        
        # Сохранить сессию
        await self._repository.save(session)
        
        logger.debug(
            f"Добавлено сообщение {message.id} в сессию {session_id} "
            f"(роль: {role}, длина: {len(content)})"
        )
        
        # Опубликовать событие
        if self._event_publisher:
            await self._event_publisher(
                MessageReceived(
                    aggregate_id=session_id,
                    session_id=session_id,
                    message_id=message.id,
                    role=role,
                    content_length=len(content)
                )
            )
        
        return message
    
    async def add_tool_result(
        self,
        session_id: str,
        call_id: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> Message:
        """
        Добавить результат выполнения инструмента в сессию.
        
        Args:
            session_id: ID сессии
            call_id: ID вызова инструмента
            result: Результат выполнения (если успешно) - строка или объект
            error: Сообщение об ошибке (если неуспешно)
            
        Returns:
            Созданное сообщение с результатом
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            
        Пример:
            >>> message = await service.add_tool_result(
            ...     session_id="session-123",
            ...     call_id="call-456",
            ...     result="File created successfully"
            ... )
        """
        import json
        
        # Формировать содержимое сообщения
        if error:
            content = f"Error: {error}"
        elif result:
            # Если result - это dict или list, сериализовать в JSON
            if isinstance(result, (dict, list)):
                content = json.dumps(result, ensure_ascii=False)
            else:
                content = str(result)
        else:
            content = "Tool executed successfully"
        
        # Добавить как сообщение с ролью "tool"
        return await self.add_message(
            session_id=session_id,
            role="tool",
            content=content,
            tool_call_id=call_id
        )
    
    async def deactivate_session(
        self,
        session_id: str,
        reason: Optional[str] = None
    ) -> Session:
        """
        Деактивировать сессию.
        
        Args:
            session_id: ID сессии
            reason: Причина деактивации
            
        Returns:
            Деактивированная сессия
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            
        Пример:
            >>> session = await service.deactivate_session(
            ...     session_id="session-123",
            ...     reason="User logged out"
            ... )
        """
        session = await self.get_session(session_id)
        
        # Деактивировать
        session.deactivate(reason=reason)
        
        # Сохранить
        await self._repository.save(session)
        
        logger.info(f"Сессия {session_id} деактивирована: {reason}")
        
        # Опубликовать событие
        if self._event_publisher:
            await self._event_publisher(
                SessionDeactivated(
                    aggregate_id=session_id,
                    session_id=session_id,
                    reason=reason or "Unknown",
                    message_count=session.get_message_count()
                )
            )
        
        return session
    
    async def list_active_sessions(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """
        Получить список активных сессий.
        
        Args:
            limit: Максимальное количество сессий
            offset: Смещение от начала списка
            
        Returns:
            Список активных сессий
            
        Пример:
            >>> sessions = await service.list_active_sessions(limit=10)
        """
        return await self._repository.find_active(limit=limit, offset=offset)
    
    async def cleanup_old_sessions(
        self,
        max_age_hours: int = 24
    ) -> int:
        """
        Очистить старые неактивные сессии.
        
        Args:
            max_age_hours: Максимальный возраст сессии в часах
            
        Returns:
            Количество очищенных сессий
            
        Пример:
            >>> count = await service.cleanup_old_sessions(max_age_hours=24)
            >>> print(f"Очищено {count} старых сессий")
        """
        count = await self._repository.cleanup_old(max_age_hours=max_age_hours)
        
        logger.info(f"Очищено {count} старых сессий (старше {max_age_hours} часов)")
        
        return count

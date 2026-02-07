"""
Доменный сервис управления сессиями.

Инкапсулирует бизнес-логику работы с сессиями,
которая не принадлежит конкретной сущности.
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from ..session_context.entities.conversation import Conversation as Session
from ..session_context.value_objects import ConversationId
from ..entities.message import Message
from ..session_context.repositories.conversation_repository import ConversationRepository as SessionRepository
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
        
        # Преобразовать в ConversationId для нового репозитория
        conv_id = ConversationId(session_id)
        
        # Проверить, что сессия не существует
        existing = await self._repository.find_by_id(conv_id)
        if existing:
            raise SessionAlreadyExistsError(session_id)
        
        # Создать новую сессию с ConversationId
        session = Session(
            id=session_id,
            conversation_id=conv_id,
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
        # Преобразовать в ConversationId
        conv_id = ConversationId(session_id)
        session = await self._repository.find_by_id(conv_id)

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
    
    async def create_subtask_context(
        self,
        session_id: str,
        subtask_id: str,
        dependency_results: Dict[str, Any]
    ) -> str:
        """
        Создать изолированный контекст для выполнения subtask.
        
        Процесс:
        1. Сохранить snapshot текущей истории сессии
        2. Очистить tool-related messages (tool_call и tool_result)
        3. Добавить результаты зависимостей как system message
        
        Это обеспечивает изоляцию между subtasks и предотвращает
        дублирование tool_call_id, которое вызывает LiteLLM 403 ошибки.
        
        Args:
            session_id: ID основной сессии
            subtask_id: ID subtask для изоляции
            dependency_results: Результаты зависимостей subtask
            
        Returns:
            snapshot_id для восстановления после subtask
            
        Пример:
            >>> snapshot_id = await service.create_subtask_context(
            ...     session_id="session-123",
            ...     subtask_id="subtask-1",
            ...     dependency_results={"subtask-0": {"result": "..."}}
            ... )
        """
        session = await self.get_session(session_id)
        
        # 1. Создать snapshot текущего состояния
        snapshot_id = f"{session_id}_snapshot_{subtask_id}"
        snapshot = session.create_snapshot()
        await self._repository.save_snapshot(snapshot_id, snapshot)
        
        logger.info(
            f"Created snapshot {snapshot_id} "
            f"(messages: {snapshot.get('message_count', 0)})"
        )
        
        # 2. Очистить tool-related messages
        cleared_count = session.clear_tool_messages()
        
        logger.info(
            f"Cleared {cleared_count} tool messages from session {session_id} "
            f"for subtask {subtask_id}"
        )
        
        # 3. Добавить dependency results как system context
        if dependency_results:
            context_message = self._format_dependency_context(dependency_results)
            await self.add_message(
                session_id=session_id,
                role="system",
                content=context_message
            )
            
            logger.debug(
                f"Added dependency context for subtask {subtask_id} "
                f"({len(dependency_results)} dependencies)"
            )
        
        # Сохранить изменения
        await self._repository.save(session)
        
        logger.info(
            f"Subtask context created for {subtask_id} "
            f"(snapshot: {snapshot_id}, remaining messages: {len(session.messages)})"
        )
        
        return snapshot_id
    
    async def restore_from_snapshot(
        self,
        session_id: str,
        snapshot_id: str,
        preserve_last_result: bool = True
    ) -> None:
        """
        Восстановить сессию из snapshot после выполнения subtask.
        
        Процесс:
        1. Получить snapshot
        2. Опционально сохранить последний assistant message (результат subtask)
        3. Восстановить базовую историю из snapshot
        4. Добавить сохраненный результат обратно
        5. Удалить snapshot
        
        Args:
            session_id: ID сессии
            snapshot_id: ID snapshot для восстановления
            preserve_last_result: Сохранить последний assistant message
            
        Пример:
            >>> await service.restore_from_snapshot(
            ...     session_id="session-123",
            ...     snapshot_id="session-123_snapshot_subtask-1",
            ...     preserve_last_result=True
            ... )
        """
        session = await self.get_session(session_id)
        snapshot = await self._repository.get_snapshot(snapshot_id)
        
        if not snapshot:
            logger.warning(
                f"Snapshot {snapshot_id} not found, skipping restore "
                f"for session {session_id}"
            )
            return
        
        # 1. Сохранить последний результат если нужно
        last_result = None
        if preserve_last_result:
            last_result = session.get_last_assistant_message()
            if last_result:
                logger.debug(
                    f"Preserved last assistant message "
                    f"(length: {len(last_result.content)})"
                )
        
        # 2. Восстановить из snapshot
        session.restore_from_snapshot(snapshot)
        
        logger.info(
            f"Restored session {session_id} from snapshot {snapshot_id} "
            f"(messages: {len(session.messages)})"
        )
        
        # 3. Добавить последний результат обратно
        if last_result:
            session.add_message(last_result)
            logger.debug(
                f"Re-added last assistant message to session {session_id}"
            )
        
        # 4. Сохранить изменения
        await self._repository.save(session)
        
        # 5. Удалить snapshot
        await self._repository.delete_snapshot(snapshot_id)
        
        logger.info(
            f"Session {session_id} restored and snapshot {snapshot_id} deleted "
            f"(final messages: {len(session.messages)})"
        )
    
    async def prepare_agent_switch_context(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str
    ) -> Dict[str, Any]:
        """
        Подготовить контекст сессии для переключения агента.
        
        Выполняет селективную очистку tool messages при переключении
        агентов вне плана, чтобы:
        1. Очистить tool_calls и tool_results от предыдущего агента
        2. Предотвратить дублирование tool_call_id
        3. Сохранить результаты работы предыдущего агента
        4. Добавить system message о переключении
        
        Это обеспечивает изоляцию контекста между агентами и
        предотвращает LiteLLM 403 ошибки дублирования.
        
        Args:
            session_id: ID сессии
            from_agent: Исходный агент
            to_agent: Целевой агент
            
        Returns:
            Информация об очистке контекста
            
        Пример:
            >>> info = await service.prepare_agent_switch_context(
            ...     session_id="session-123",
            ...     from_agent="orchestrator",
            ...     to_agent="coder"
            ... )
            >>> print(f"Cleared {info['removed_count']} tool messages")
        """
        session = await self.get_session(session_id)
        
        logger.info(
            f"Preparing agent switch context for session {session_id}: "
            f"{from_agent} -> {to_agent}"
        )
        
        # Выполнить селективную очистку
        cleanup_info = session.clear_tool_messages_with_context(
            from_agent=from_agent,
            to_agent=to_agent
        )
        
        # Сохранить изменения
        await self._repository.save(session)
        
        logger.info(
            f"Agent switch context prepared for session {session_id}: "
            f"removed {cleanup_info['removed_count']} tool messages, "
            f"preserved result: {bool(cleanup_info['preserved_result'])}, "
            f"final messages: {cleanup_info['final_message_count']}"
        )
        
        return cleanup_info
    
    def _format_dependency_context(
        self,
        dependency_results: Dict[str, Any]
    ) -> str:
        """
        Форматировать результаты зависимостей в system message.
        
        Преобразует результаты предыдущих subtasks в читаемый
        контекст для текущей subtask.
        
        Args:
            dependency_results: Словарь с результатами зависимостей
            
        Returns:
            Отформатированный текст для system message
            
        Пример:
            >>> context = service._format_dependency_context({
            ...     "subtask-1": {
            ...         "description": "Create file",
            ...         "result": "File created successfully"
            ...     }
            ... })
        """
        lines = ["Previous subtask results:"]
        
        for dep_id, result in dependency_results.items():
            lines.append(f"\n## Subtask: {result.get('description', dep_id)}")
            lines.append(f"Agent: {result.get('agent', 'unknown')}")
            lines.append(f"Result: {result.get('result', 'No result')}")
        
        return "\n".join(lines)

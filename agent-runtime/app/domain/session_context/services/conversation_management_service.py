"""
Conversation Management Service.

Доменный сервис для управления conversations - рефакторинг SessionManagementService.
Использует новую архитектуру с Conversation entity и Value Objects.
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from ..entities import Conversation
from ..value_objects import ConversationId, MessageCollection
from ..repositories import ConversationRepository
from ..events import (
    ConversationStarted,
    MessageAdded,
    ConversationDeactivated,
    ConversationActivated,
)
from .conversation_snapshot_service import ConversationSnapshotService
from .tool_message_cleanup_service import ToolMessageCleanupService
from ...entities.message import Message
from ....core.errors import SessionNotFoundError, SessionAlreadyExistsError

logger = logging.getLogger("agent-runtime.domain.conversation_management")


class ConversationManagementService:
    """
    Доменный сервис для управления conversations.
    
    Рефакторинг SessionManagementService с использованием новой архитектуры:
    - Использует Conversation вместо Session
    - Использует ConversationId вместо str
    - Делегирует snapshot логику в ConversationSnapshotService
    - Делегирует cleanup логику в ToolMessageCleanupService
    
    Размер: ~400 строк (вместо 609 в SessionManagementService)
    Сложность: Средняя (координация операций)
    Зависимости: 5 (Repository, 2 Services, Events, Errors)
    
    Атрибуты:
        _repository: Repository для conversations
        _snapshot_service: Service для snapshots
        _cleanup_service: Service для очистки tool messages
        _event_publisher: Функция для публикации событий (опционально)
    
    Пример:
        >>> service = ConversationManagementService(repository)
        >>> conversation = await service.create_conversation("conv-1")
    """
    
    def __init__(
        self,
        repository: ConversationRepository = None,
        snapshot_service: Optional[ConversationSnapshotService] = None,
        cleanup_service: Optional[ToolMessageCleanupService] = None,
        event_publisher=None,
        uow=None  # Optional[SSEUnitOfWork]
    ):
        """
        Инициализация сервиса.
        
        Args:
            repository: Repository для работы с conversations (deprecated, используйте uow)
            snapshot_service: Service для snapshots (создается если None)
            cleanup_service: Service для cleanup (создается если None)
            event_publisher: Функция для публикации событий (опционально)
            uow: Unit of Work для доступа к репозиториям (рекомендуется)
        """
        self._repository = repository  # Для обратной совместимости
        self._uow = uow
        self._snapshot_service = snapshot_service or ConversationSnapshotService()
        self._cleanup_service = cleanup_service or ToolMessageCleanupService()
        self._event_publisher = event_publisher
    
    def _get_repository(self) -> ConversationRepository:
        """Получить repository из UoW или использовать переданный."""
        if self._uow:
            return self._uow.conversations
        if self._repository:
            return self._repository
        raise RuntimeError(
            "ConversationManagementService requires either uow or repository"
        )
    
    async def create_conversation(
        self,
        conversation_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        uow=None  # Optional[SSEUnitOfWork]
    ) -> Conversation:
        """
        Создать новую conversation.
        
        Args:
            conversation_id: ID conversation (если None, генерируется автоматически)
            title: Заголовок conversation
            description: Описание conversation
            uow: Unit of Work для доступа к репозиториям (опционально)
            
        Returns:
            Созданная conversation
            
        Raises:
            SessionAlreadyExistsError: Если conversation с таким ID уже существует
            
        Пример:
            >>> conversation = await service.create_conversation(uow=uow)
            >>> conversation.is_active
            True
        """
        # Получить repository (из UoW если передан, иначе из self)
        repo = uow.conversations if uow else self._get_repository()
        
        # Генерировать ID если не указан
        if not conversation_id:
            conv_id = ConversationId.generate()
        else:
            conv_id = ConversationId(conversation_id)
        
        # Проверить, что conversation не существует
        existing = await repo.find_by_id(conv_id)
        if existing:
            raise SessionAlreadyExistsError(conv_id.value)
        
        # Создать новую conversation
        conversation = Conversation.create(
            conversation_id=conv_id,
            title=title,
            description=description
        )
        
        # Сохранить в репозитории
        await repo.save(conversation)
        
        logger.info(f"Создана новая conversation: {conv_id.value}")
        
        # Опубликовать событие
        if self._event_publisher:
            event = ConversationStarted(
                aggregate_id=conv_id.value,
                conversation_id=conv_id.value,
                title=title,
                description=description
            )
            await self._event_publisher(event)
        
        return conversation
    
    async def get_conversation(self, conversation_id: str) -> Conversation:
        """
        Получить conversation по ID.
        
        Args:
            conversation_id: ID conversation
            
        Returns:
            Conversation
            
        Raises:
            SessionNotFoundError: Если conversation не найдена
            
        Пример:
            >>> conversation = await service.get_conversation("conv-123")
        """
        conv_id = ConversationId(conversation_id)
        conversation = await self._get_repository().find_by_id(conv_id)
        
        if not conversation:
            raise SessionNotFoundError(conversation_id)
        
        return conversation
    
    async def get_or_create_conversation(
        self,
        conversation_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        uow=None  # Optional[SSEUnitOfWork]
    ) -> Conversation:
        """
        Получить существующую conversation или создать новую.
        
        Args:
            conversation_id: ID conversation (если None, создается новая)
            title: Заголовок (для новой conversation)
            description: Описание (для новой conversation)
            uow: Unit of Work для доступа к репозиториям (опционально)
            
        Returns:
            Существующая или новая conversation
            
        Пример:
            >>> # Создать новую conversation
            >>> conversation = await service.get_or_create_conversation(uow=uow)
            >>> # Получить существующую или создать
            >>> conversation = await service.get_or_create_conversation("conv-123", uow=uow)
        """
        # Если conversation_id не указан, создать новую
        if not conversation_id:
            logger.info("🆔 conversation_id не указан, создаем новую conversation")
            return await self.create_conversation(
                conversation_id=None,
                title=title,
                description=description,
                uow=uow
            )
        
        # Получить repository (из UoW если передан, иначе из self)
        repo = uow.conversations if uow else self._get_repository()
        
        # Попытаться найти существующую
        conv_id = ConversationId(conversation_id)
        existing = await repo.find_by_id(conv_id)
        
        if existing:
            logger.debug(f"Найдена существующая conversation: {conversation_id}")
            return existing
        
        # Создать новую с указанным ID
        logger.info(f"Conversation {conversation_id} не найдена, создаем новую")
        return await self.create_conversation(
            conversation_id=conversation_id,
            title=title,
            description=description,
            uow=uow
        )
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_calls: Optional[list] = None,
        uow=None  # Optional[SSEUnitOfWork]
    ) -> Message:
        """
        Добавить сообщение в conversation.
        
        Args:
            conversation_id: ID conversation
            role: Роль отправителя
            content: Содержимое сообщения
            name: Имя отправителя (опционально)
            tool_call_id: ID вызова инструмента (опционально)
            tool_calls: Вызовы инструментов (опционально)
            uow: Unit of Work для доступа к репозиториям (опционально)
            
        Returns:
            Созданное сообщение
            
        Raises:
            SessionNotFoundError: Если conversation не найдена
            
        Пример:
            >>> message = await service.add_message(
            ...     conversation_id="conv-123",
            ...     role="user",
            ...     content="Привет!",
            ...     uow=uow
            ... )
        """
        # Получить repository (из UoW если передан, иначе из self)
        repo = uow.conversations if uow else self._get_repository()
        
        # Получить conversation
        conversation = await repo.find_by_id(ConversationId(conversation_id))
        if not conversation:
            raise SessionNotFoundError(f"Conversation {conversation_id} not found")
        
        # Создать сообщение
        message = Message(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls
        )
        
        # Добавить в conversation (валидация внутри)
        conversation.add_message(message)
        
        # Сохранить conversation
        await repo.save(conversation)
        
        logger.debug(
            f"Добавлено сообщение {message.id} в conversation {conversation_id} "
            f"(роль: {role}, длина: {len(content)})"
        )
        
        # Опубликовать событие
        if self._event_publisher:
            event = MessageAdded(
                aggregate_id=conversation_id,
                conversation_id=conversation_id,
                message_id=message.id,
                role=role,
                content_length=len(content)
            )
            await self._event_publisher(event)
        
        return message
    
    async def add_tool_result(
        self,
        conversation_id: str,
        call_id: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> Message:
        """
        Добавить результат выполнения инструмента в conversation.
        
        Args:
            conversation_id: ID conversation
            call_id: ID вызова инструмента
            result: Результат выполнения (если успешно)
            error: Сообщение об ошибке (если неуспешно)
            
        Returns:
            Созданное сообщение с результатом
            
        Raises:
            SessionNotFoundError: Если conversation не найдена
            
        Пример:
            >>> message = await service.add_tool_result(
            ...     conversation_id="conv-123",
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
            conversation_id=conversation_id,
            role="tool",
            content=content,
            tool_call_id=call_id
        )
    
    async def deactivate_conversation(
        self,
        conversation_id: str,
        reason: Optional[str] = None
    ) -> Conversation:
        """
        Деактивировать conversation.
        
        Args:
            conversation_id: ID conversation
            reason: Причина деактивации
            
        Returns:
            Деактивированная conversation
            
        Raises:
            SessionNotFoundError: Если conversation не найдена
            
        Пример:
            >>> conversation = await service.deactivate_conversation(
            ...     conversation_id="conv-123",
            ...     reason="User logged out"
            ... )
        """
        conversation = await self.get_conversation(conversation_id)
        
        # Деактивировать
        conversation.deactivate(reason=reason)
        
        # Сохранить
        await self._get_repository().save(conversation)
        
        logger.info(f"Conversation {conversation_id} деактивирована: {reason}")
        
        # Опубликовать событие
        if self._event_publisher:
            event = ConversationDeactivated(
                aggregate_id=conversation_id,
                conversation_id=conversation_id,
                reason=reason or "Unknown",
                message_count=conversation.messages.count()
            )
            await self._event_publisher(event)
        
        return conversation
    
    async def list_active_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Conversation]:
        """
        Получить список активных conversations.
        
        Args:
            user_id: ID пользователя (опционально)
            limit: Максимальное количество conversations
            offset: Смещение от начала списка
            
        Returns:
            Список активных conversations
            
        Пример:
            >>> conversations = await service.list_active_conversations(limit=10)
        """
        if user_id:
            return await self._get_repository().find_active_by_user_id(
                user_id=user_id,
                limit=limit
            )
        else:
            return await self._get_repository().find_active(limit=limit, offset=offset)
    
    async def cleanup_old_conversations(
        self,
        max_age_hours: int = 24
    ) -> int:
        """
        Очистить старые неактивные conversations.
        
        Args:
            max_age_hours: Максимальный возраст conversation в часах
            
        Returns:
            Количество очищенных conversations
            
        Пример:
            >>> count = await service.cleanup_old_conversations(max_age_hours=24)
            >>> print(f"Очищено {count} старых conversations")
        """
        count = await self._get_repository().cleanup_old(max_age_hours=max_age_hours)
        
        logger.info(
            f"Очищено {count} старых conversations (старше {max_age_hours} часов)"
        )
        
        return count
    
    async def create_subtask_context(
        self,
        conversation_id: str,
        subtask_id: str,
        dependency_results: Dict[str, Any]
    ) -> str:
        """
        Создать изолированный контекст для выполнения subtask.
        
        Процесс:
        1. Сохранить snapshot текущей истории conversation
        2. Очистить tool-related messages (tool_call и tool_result)
        3. Добавить результаты зависимостей как system message
        
        Это обеспечивает изоляцию между subtasks и предотвращает
        дублирование tool_call_id, которое вызывает LiteLLM 403 ошибки.
        
        Args:
            conversation_id: ID основной conversation
            subtask_id: ID subtask для изоляции
            dependency_results: Результаты зависимостей subtask
            
        Returns:
            snapshot_id для восстановления после subtask
            
        Пример:
            >>> snapshot_id = await service.create_subtask_context(
            ...     conversation_id="conv-123",
            ...     subtask_id="subtask-1",
            ...     dependency_results={"subtask-0": {"result": "..."}}
            ... )
        """
        conversation = await self.get_conversation(conversation_id)
        
        # 1. Создать snapshot текущего состояния
        snapshot_id = f"{conversation_id}_snapshot_{subtask_id}"
        snapshot = self._snapshot_service.create_snapshot(conversation)
        await self._get_repository().save_snapshot(snapshot_id, snapshot)
        
        logger.info(
            f"Created snapshot {snapshot_id} "
            f"(messages: {snapshot.get('message_count', 0)})"
        )
        
        # 2. Очистить tool-related messages
        cleared_count = self._cleanup_service.clear_tool_messages(conversation)
        
        logger.info(
            f"Cleared {cleared_count} tool messages from conversation {conversation_id} "
            f"for subtask {subtask_id}"
        )
        
        # 3. Добавить dependency results как system context
        if dependency_results:
            context_message = self._format_dependency_context(dependency_results)
            await self.add_message(
                conversation_id=conversation_id,
                role="system",
                content=context_message
            )
            
            logger.debug(
                f"Added dependency context for subtask {subtask_id} "
                f"({len(dependency_results)} dependencies)"
            )
        
        # Сохранить изменения
        await self._get_repository().save(conversation)
        
        logger.info(
            f"Subtask context created for {subtask_id} "
            f"(snapshot: {snapshot_id}, remaining messages: {conversation.messages.count()})"
        )
        
        return snapshot_id
    
    async def restore_from_snapshot(
        self,
        conversation_id: str,
        snapshot_id: str,
        preserve_last_result: bool = True
    ) -> None:
        """
        Восстановить conversation из snapshot после выполнения subtask.
        
        Процесс:
        1. Получить snapshot
        2. Опционально сохранить последний assistant message (результат subtask)
        3. Восстановить базовую историю из snapshot
        4. Добавить сохраненный результат обратно
        5. Удалить snapshot
        
        Args:
            conversation_id: ID conversation
            snapshot_id: ID snapshot для восстановления
            preserve_last_result: Сохранить последний assistant message
            
        Пример:
            >>> await service.restore_from_snapshot(
            ...     conversation_id="conv-123",
            ...     snapshot_id="conv-123_snapshot_subtask-1",
            ...     preserve_last_result=True
            ... )
        """
        conversation = await self.get_conversation(conversation_id)
        snapshot = await self._get_repository().get_snapshot(snapshot_id)
        
        if not snapshot:
            logger.warning(
                f"Snapshot {snapshot_id} not found, skipping restore "
                f"for conversation {conversation_id}"
            )
            return
        
        # 1. Сохранить последний результат если нужно
        last_result = None
        if preserve_last_result:
            last_result = conversation.messages.get_last_by_role("assistant")
            if last_result:
                logger.debug(
                    f"Preserved last assistant message "
                    f"(length: {len(last_result.content)})"
                )
        
        # 2. Восстановить из snapshot
        self._snapshot_service.restore_from_snapshot(conversation, snapshot)
        
        logger.info(
            f"Restored conversation {conversation_id} from snapshot {snapshot_id} "
            f"(messages: {conversation.messages.count()})"
        )
        
        # 3. Добавить последний результат обратно
        if last_result:
            conversation.add_message(last_result)
            logger.debug(
                f"Re-added last assistant message to conversation {conversation_id}"
            )
        
        # 4. Сохранить изменения
        await self._get_repository().save(conversation)
        
        # 5. Удалить snapshot
        await self._get_repository().delete_snapshot(snapshot_id)
        
        logger.info(
            f"Conversation {conversation_id} restored and snapshot {snapshot_id} deleted "
            f"(final messages: {conversation.messages.count()})"
        )
    
    async def prepare_agent_switch_context(
        self,
        conversation_id: str,
        from_agent: str,
        to_agent: str
    ) -> Dict[str, Any]:
        """
        Подготовить контекст conversation для переключения агента.
        
        Выполняет селективную очистку tool messages при переключении
        агентов вне плана, чтобы:
        1. Очистить tool_calls и tool_results от предыдущего агента
        2. Предотвратить дублирование tool_call_id
        3. Сохранить результаты работы предыдущего агента
        4. Добавить system message о переключении
        
        Это обеспечивает изоляцию контекста между агентами и
        предотвращает LiteLLM 403 ошибки дублирования.
        
        Args:
            conversation_id: ID conversation
            from_agent: Исходный агент
            to_agent: Целевой агент
            
        Returns:
            Информация об очистке контекста
            
        Пример:
            >>> info = await service.prepare_agent_switch_context(
            ...     conversation_id="conv-123",
            ...     from_agent="orchestrator",
            ...     to_agent="coder"
            ... )
            >>> print(f"Cleared {info['removed_count']} tool messages")
        """
        conversation = await self.get_conversation(conversation_id)
        
        logger.info(
            f"Preparing agent switch context for conversation {conversation_id}: "
            f"{from_agent} -> {to_agent}"
        )
        
        # Выполнить селективную очистку
        cleanup_info = self._cleanup_service.clear_tool_messages_with_context(
            conversation=conversation,
            from_agent=from_agent,
            to_agent=to_agent
        )
        
        # Сохранить изменения
        await self._get_repository().save(conversation)
        
        logger.info(
            f"Agent switch context prepared for conversation {conversation_id}: "
            f"removed {cleanup_info['removed_count']} tool messages, "
            f"preserved result: {bool(cleanup_info.get('preserved_result'))}, "
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

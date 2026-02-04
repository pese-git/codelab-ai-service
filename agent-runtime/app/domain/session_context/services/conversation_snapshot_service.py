"""
Conversation Snapshot Service.

Domain Service для создания и восстановления snapshots conversation.
Вынесена логика из Session entity для упрощения.
"""

from typing import Dict, Any
from datetime import datetime, timezone

from ..entities import Conversation
from ..value_objects import MessageCollection
from ...entities.message import Message


class ConversationSnapshotService:
    """
    Domain Service для работы со snapshots.
    
    Отвечает за:
    - Создание snapshot текущего состояния
    - Восстановление состояния из snapshot
    - Валидацию snapshot данных
    
    Используется для изоляции контекста между subtasks:
    - Сохраняет базовую историю перед subtask
    - Позволяет восстановить чистое состояние после subtask
    
    Пример:
        >>> service = ConversationSnapshotService()
        >>> snapshot = service.create_snapshot(conversation)
        >>> # ... изменения в conversation ...
        >>> service.restore_from_snapshot(conversation, snapshot)
    """
    
    def create_snapshot(self, conversation: Conversation) -> Dict[str, Any]:
        """
        Создать snapshot текущего состояния conversation.
        
        Snapshot содержит:
        - Все сообщения в сериализованном виде
        - Метаданные conversation
        - Title и description
        - Timestamp создания snapshot
        - Количество сообщений (для быстрой проверки)
        
        Args:
            conversation: Conversation для snapshot
            
        Returns:
            Словарь с snapshot данными
            
        Пример:
            >>> snapshot = service.create_snapshot(conversation)
            >>> snapshot['message_count']
            5
        """
        return {
            "conversation_id": conversation.conversation_id.value,
            "messages": conversation.messages.to_dict_list(),
            "metadata": conversation.metadata.copy(),
            "title": conversation.title,
            "description": conversation.description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_count": conversation.messages.count(),
            "snapshot_version": "1.0"  # Для будущей совместимости
        }
    
    def restore_from_snapshot(
        self,
        conversation: Conversation,
        snapshot: Dict[str, Any]
    ) -> None:
        """
        Восстановить состояние conversation из snapshot.
        
        Заменяет:
        - Все сообщения
        - Метаданные
        - Title и description (если есть)
        
        Сохраняет:
        - ID conversation
        - Статус активности
        - Timestamps (created_at, updated_at)
        
        Args:
            conversation: Conversation для восстановления
            snapshot: Snapshot данные
            
        Raises:
            ValueError: Если snapshot невалиден или для другого conversation
            
        Пример:
            >>> service.restore_from_snapshot(conversation, snapshot)
            >>> # Состояние восстановлено
        """
        # Валидация snapshot
        self._validate_snapshot(snapshot, conversation)
        
        # Восстановить сообщения
        messages_data = snapshot.get("messages", [])
        conversation.messages = MessageCollection.from_dict_list(
            messages_data,
            max_size=conversation.messages.max_size
        )
        
        # Восстановить метаданные
        conversation.metadata = snapshot.get("metadata", {}).copy()
        
        # Восстановить title и description
        if "title" in snapshot:
            conversation.title = snapshot["title"]
        if "description" in snapshot:
            conversation.description = snapshot["description"]
        
        # Отметить как обновленный
        conversation.mark_updated()
    
    def _validate_snapshot(
        self,
        snapshot: Dict[str, Any],
        conversation: Conversation
    ) -> None:
        """
        Валидировать snapshot данные.
        
        Проверяет:
        - Наличие обязательных полей
        - Соответствие conversation_id
        - Формат данных
        
        Args:
            snapshot: Snapshot для валидации
            conversation: Целевой conversation
            
        Raises:
            ValueError: Если snapshot невалиден
        """
        # Проверка обязательных полей
        required_fields = ["conversation_id", "messages"]
        for field in required_fields:
            if field not in snapshot:
                raise ValueError(f"Snapshot не содержит обязательное поле: {field}")
        
        # Проверка соответствия conversation_id
        snapshot_conv_id = snapshot.get("conversation_id")
        if snapshot_conv_id != conversation.conversation_id.value:
            raise ValueError(
                f"Snapshot для другого conversation: "
                f"expected={conversation.conversation_id.value}, "
                f"got={snapshot_conv_id}"
            )
        
        # Проверка формата messages
        messages = snapshot.get("messages")
        if not isinstance(messages, list):
            raise ValueError(
                f"Поле 'messages' должно быть списком, получено: {type(messages)}"
            )
    
    def get_snapshot_info(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Получить информацию о snapshot.
        
        Args:
            snapshot: Snapshot для анализа
            
        Returns:
            Словарь с информацией о snapshot
            
        Пример:
            >>> info = service.get_snapshot_info(snapshot)
            >>> print(f"Messages: {info['message_count']}")
        """
        return {
            "conversation_id": snapshot.get("conversation_id"),
            "message_count": snapshot.get("message_count", 0),
            "created_at": snapshot.get("created_at"),
            "has_title": snapshot.get("title") is not None,
            "metadata_keys": list(snapshot.get("metadata", {}).keys()),
            "snapshot_version": snapshot.get("snapshot_version", "unknown")
        }

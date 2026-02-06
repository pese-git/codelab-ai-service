"""
Доменная сущность Session (Сессия).

Представляет сессию диалога между пользователем и AI агентом.
Содержит историю сообщений и метаданные сессии.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import Field, field_validator

from .base import Entity
from .message import Message
from ...core.errors import MessageValidationError


class Session(Entity):
    """
    Доменная сущность сессии.
    
    Сессия представляет собой диалог между пользователем и AI агентом.
    Содержит историю всех сообщений и отслеживает активность.
    
    Атрибуты:
        messages: Список сообщений в сессии
        title: Заголовок сессии (генерируется из первого сообщения)
        description: Описание сессии (опционально)
        last_activity: Время последней активности
        is_active: Флаг активности сессии
        max_messages: Максимальное количество сообщений (для предотвращения переполнения)
    
    Бизнес-правила:
        - Сессия не может содержать более max_messages сообщений
        - При добавлении сообщения обновляется last_activity
        - Заголовок автоматически генерируется из первого пользовательского сообщения
        - Неактивные сессии не могут принимать новые сообщения
    
    Пример:
        >>> session = Session(id="session-1")
        >>> msg = Message(id="msg-1", role="user", content="Привет")
        >>> session.add_message(msg)
        >>> session.get_message_count()
        1
    """
    
    messages: List[Message] = Field(
        default_factory=list,
        description="Список сообщений в сессии"
    )
    
    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Заголовок сессии"
    )
    
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Описание сессии"
    )
    
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Время последней активности в сессии"
    )
    
    is_active: bool = Field(
        default=True,
        description="Флаг активности сессии"
    )
    
    max_messages: int = Field(
        default=1000,
        description="Максимальное количество сообщений в сессии"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные сессии"
    )
    
    def add_message(self, message: Message) -> None:
        """
        Добавить сообщение в сессию.
        
        Обновляет last_activity и автоматически генерирует title
        из первого пользовательского сообщения.
        
        Args:
            message: Сообщение для добавления
            
        Raises:
            ValueError: Если сессия неактивна
            MessageValidationError: Если превышен лимит сообщений
            
        Пример:
            >>> session = Session(id="session-1")
            >>> msg = Message(id="msg-1", role="user", content="Привет")
            >>> session.add_message(msg)
        """
        # Проверка активности сессии
        if not self.is_active:
            raise ValueError(
                f"Невозможно добавить сообщение в неактивную сессию '{self.id}'"
            )
        
        # Проверка лимита сообщений
        if len(self.messages) >= self.max_messages:
            raise MessageValidationError(
                field="messages",
                reason=f"Превышен лимит сообщений ({self.max_messages})",
                details={"session_id": self.id, "current_count": len(self.messages)}
            )
        
        # Добавить сообщение
        self.messages.append(message)
        
        # Обновить время активности
        self.last_activity = datetime.now(timezone.utc)
        self.mark_updated()
        
        # Автоматически установить title из первого пользовательского сообщения
        if not self.title and message.is_user_message():
            self._set_title_from_message(message)
    
    def _set_title_from_message(self, message: Message) -> None:
        """
        Установить заголовок сессии из сообщения.
        
        Берет первые 500 символов содержимого сообщения.
        
        Args:
            message: Сообщение для извлечения заголовка
        """
        content = message.content.strip()
        if content:
            self.title = content[:500] if len(content) > 500 else content
    
    def get_message_count(self) -> int:
        """
        Получить количество сообщений в сессии.
        
        Если сообщения не загружены (например, при получении списка сессий),
        использует кэшированное значение из метаданных.
        
        Returns:
            Количество сообщений
        """
        # Если есть кэшированное значение в метаданных, используем его
        if '_message_count' in self.metadata:
            return self.metadata['_message_count']
        
        # Иначе считаем из загруженных сообщений
        return len(self.messages)
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """
        Получить последние N сообщений.
        
        Полезно для контекста LLM с ограниченным окном.
        
        Args:
            limit: Максимальное количество сообщений
            
        Returns:
            Список последних сообщений
            
        Пример:
            >>> recent = session.get_recent_messages(limit=5)
            >>> len(recent) <= 5
            True
        """
        return self.messages[-limit:] if self.messages else []
    
    def get_messages_by_role(self, role: str) -> List[Message]:
        """
        Получить все сообщения определенной роли.
        
        Args:
            role: Роль сообщений (user, assistant, system, tool)
            
        Returns:
            Список сообщений с указанной ролью
            
        Пример:
            >>> user_messages = session.get_messages_by_role("user")
        """
        return [msg for msg in self.messages if msg.role == role]
    
    def get_history_for_llm(self, max_messages: Optional[int] = None) -> List[Dict]:
        """
        Получить историю сообщений в формате для LLM.
        
        Args:
            max_messages: Максимальное количество сообщений (None = все)
            
        Returns:
            Список сообщений в формате LLM API
            
        Пример:
            >>> history = session.get_history_for_llm(max_messages=10)
            >>> history[0]['role']
            'user'
        """
        messages = self.messages
        if max_messages:
            messages = self.get_recent_messages(max_messages)
        
        return [msg.to_llm_format() for msg in messages]
    
    def deactivate(self, reason: Optional[str] = None) -> None:
        """
        Деактивировать сессию.
        
        Деактивированная сессия не может принимать новые сообщения.
        
        Args:
            reason: Причина деактивации (опционально)
            
        Пример:
            >>> session.deactivate(reason="User logged out")
            >>> session.is_active
            False
        """
        self.is_active = False
        self.mark_updated()
        
        if reason:
            self.metadata["deactivation_reason"] = reason
            self.metadata["deactivated_at"] = datetime.now(timezone.utc).isoformat()
    
    def activate(self) -> None:
        """
        Активировать сессию.
        
        Позволяет снова добавлять сообщения в сессию.
        
        Пример:
            >>> session.activate()
            >>> session.is_active
            True
        """
        self.is_active = True
        self.mark_updated()
    
    def clear_messages(self) -> int:
        """
        Очистить все сообщения из сессии.
        
        Полезно для сброса контекста при сохранении сессии.
        
        Returns:
            Количество удаленных сообщений
            
        Пример:
            >>> count = session.clear_messages()
            >>> session.get_message_count()
            0
        """
        count = len(self.messages)
        self.messages.clear()
        self.mark_updated()
        return count
    
    def is_empty(self) -> bool:
        """
        Проверить, пуста ли сессия (нет сообщений).
        
        Returns:
            True если сессия не содержит сообщений
        """
        return len(self.messages) == 0
    
    def get_duration_seconds(self) -> float:
        """
        Получить длительность сессии в секундах.
        
        Вычисляется как разница между last_activity и created_at.
        
        Returns:
            Длительность сессии в секундах
            
        Пример:
            >>> duration = session.get_duration_seconds()
            >>> duration > 0
            True
        """
        return (self.last_activity - self.created_at).total_seconds()
    
    def create_snapshot(self) -> Dict[str, Any]:
        """
        Создать snapshot текущего состояния сессии.
        
        Snapshot содержит полную копию сообщений и метаданных.
        Используется для изоляции контекста между subtasks:
        - Сохраняет базовую историю перед subtask
        - Позволяет восстановить чистое состояние после subtask
        
        Returns:
            Словарь с snapshot данными
            
        Пример:
            >>> snapshot = session.create_snapshot()
            >>> len(snapshot['messages']) == len(session.messages)
            True
        """
        return {
            "messages": [msg.model_dump() for msg in self.messages],
            "metadata": self.metadata.copy(),
            "title": self.title,
            "description": self.description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_count": len(self.messages)
        }
    
    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Восстановить состояние сессии из snapshot.
        
        Заменяет текущие сообщения и метаданные данными из snapshot.
        Используется после выполнения subtask для восстановления
        базовой истории без tool_call/tool_result.
        
        Args:
            snapshot: Snapshot данные из create_snapshot()
            
        Пример:
            >>> snapshot = session.create_snapshot()
            >>> session.add_message(Message(...))  # изменения
            >>> session.restore_from_snapshot(snapshot)
            >>> # Состояние восстановлено
        """
        # Восстановить сообщения
        self.messages = [
            Message(**msg_dict)
            for msg_dict in snapshot["messages"]
        ]
        
        # Восстановить метаданные
        self.metadata = snapshot.get("metadata", {}).copy()
        
        # Восстановить title и description если есть
        if "title" in snapshot:
            self.title = snapshot["title"]
        if "description" in snapshot:
            self.description = snapshot["description"]
        
        self.mark_updated()
    
    def clear_tool_messages(self) -> int:
        """
        Очистить tool-related messages из сессии.
        
        Удаляет assistant messages с tool_calls и tool result messages.
        Сохраняет user, system и обычные assistant messages.
        
        Используется для изоляции контекста между subtasks:
        - Убирает tool_call_id от предыдущих subtasks
        - Предотвращает LiteLLM 403 ошибки дублирования
        
        Returns:
            Количество удаленных сообщений
            
        Пример:
            >>> count = session.clear_tool_messages()
            >>> # Все tool_call и tool_result удалены
        """
        original_count = len(self.messages)
        
        self.messages = [
            msg for msg in self.messages
            if not (
                (msg.role == "assistant" and msg.tool_calls) or
                msg.role == "tool"
            )
        ]
        
        removed_count = original_count - len(self.messages)
        
        if removed_count > 0:
            self.mark_updated()
        
        return removed_count
    
    def get_last_assistant_message(self) -> Optional[Message]:
        """
        Получить последнее assistant message без tool_calls.
        
        Полезно для сохранения результата subtask после
        очистки tool messages.
        
        Returns:
            Последнее assistant message или None
            
        Пример:
            >>> last_msg = session.get_last_assistant_message()
            >>> if last_msg and not last_msg.tool_calls:
            ...     print(last_msg.content)
        """
        for msg in reversed(self.messages):
            if msg.role == "assistant" and not msg.tool_calls:
                return msg
        return None
    
    def clear_tool_messages_with_context(
        self,
        from_agent: str,
        to_agent: str
    ) -> Dict[str, Any]:
        """
        Селективная очистка tool messages при переключении агентов.
        
        Выполняет:
        1. Сохраняет последний assistant message с результатом (если есть)
        2. Очищает tool_calls и tool_result messages
        3. Добавляет system message о переключении агента
        
        Это предотвращает дублирование tool_call_id между агентами
        и сохраняет контекст выполненной работы.
        
        Args:
            from_agent: Исходный агент (для контекста)
            to_agent: Целевой агент (для контекста)
            
        Returns:
            Словарь с информацией об очистке:
            - removed_count: количество удаленных сообщений
            - preserved_result: последний результат (если есть)
            - context_message: добавленное system сообщение
            
        Пример:
            >>> info = session.clear_tool_messages_with_context(
            ...     from_agent="orchestrator",
            ...     to_agent="coder"
            ... )
            >>> print(f"Removed {info['removed_count']} tool messages")
        """
        # 1. Сохранить последний assistant message без tool_calls
        last_result = self.get_last_assistant_message()
        preserved_content = last_result.content if last_result else None
        
        # 2. Очистить tool messages (включая assistant messages с tool_calls)
        removed_count = self.clear_tool_messages()
        
        # 3. Создать system message о переключении
        context_message = (
            f"Agent switched: {from_agent} → {to_agent}\n"
            f"Previous context preserved. Tool history cleared to prevent conflicts."
        )
        
        # 4. Добавить context message как system message
        from datetime import datetime, timezone
        context_msg = Message(
            id=str(__import__('uuid').uuid4()),
            role="system",
            content=context_message,
            created_at=datetime.now(timezone.utc)
        )
        self.messages.append(context_msg)
        
        # 5. Восстановить последний результат если был и он не уже в истории
        # (clear_tool_messages сохраняет assistant messages без tool_calls)
        if preserved_content:
            # Проверить, есть ли уже этот результат в истории
            has_result = any(
                msg.role == "assistant" and
                msg.content == preserved_content and
                not msg.tool_calls
                for msg in self.messages
            )
            
            if not has_result:
                # Создать новый message без tool_calls
                result_msg = Message(
                    id=str(__import__('uuid').uuid4()),
                    role="assistant",
                    content=preserved_content,
                    created_at=datetime.now(timezone.utc)
                )
                self.messages.append(result_msg)
        
        self.mark_updated()
        
        return {
            "removed_count": removed_count,
            "preserved_result": preserved_content,
            "context_message": context_message,
            "final_message_count": len(self.messages)
        }
    
    def __repr__(self) -> str:
        """Строковое представление сессии"""
        title_preview = self.title[:30] + "..." if self.title and len(self.title) > 30 else self.title
        return (
            f"<Session(id='{self.id}', "
            f"title='{title_preview}', "
            f"messages={len(self.messages)}, "
            f"active={self.is_active})>"
        )

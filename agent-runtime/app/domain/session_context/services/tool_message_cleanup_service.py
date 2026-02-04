"""
Tool Message Cleanup Service.

Domain Service для очистки tool-related messages из conversation.
Вынесена сложная логика из Session entity.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from ..entities import Conversation
from ..events import ToolMessagesCleared
from ...entities.message import Message


class ToolMessageCleanupService:
    """
    Domain Service для очистки tool messages.
    
    Отвечает за:
    - Удаление tool_call и tool_result messages
    - Сохранение последнего результата
    - Добавление context messages при переключении агентов
    
    Используется для изоляции контекста между subtasks:
    - Убирает tool_call_id от предыдущих subtasks
    - Предотвращает LiteLLM 403 ошибки дублирования
    - Сохраняет контекст выполненной работы
    
    Пример:
        >>> service = ToolMessageCleanupService()
        >>> removed = service.clear_tool_messages(conversation)
        >>> print(f"Removed {removed} tool messages")
    """
    
    def clear_tool_messages(self, conversation: Conversation) -> int:
        """
        Очистить tool-related messages из conversation.
        
        Удаляет:
        - Assistant messages с tool_calls
        - Tool result messages
        
        Сохраняет:
        - User messages
        - System messages
        - Assistant messages без tool_calls
        
        Args:
            conversation: Conversation для очистки
            
        Returns:
            Количество удаленных сообщений
            
        Пример:
            >>> removed = service.clear_tool_messages(conversation)
            >>> removed
            3
        """
        # Используем MessageCollection для очистки
        new_collection, removed_count = conversation.messages.clear_tool_messages()
        
        # Обновляем conversation
        conversation.messages = new_collection
        
        if removed_count > 0:
            conversation.mark_updated()
            
            # Генерируем domain event
            conversation.record_event(
                ToolMessagesCleared(
                    conversation_id=conversation.conversation_id.value,
                    cleared_count=removed_count
                )
            )
        
        return removed_count
    
    def clear_tool_messages_with_context(
        self,
        conversation: Conversation,
        from_agent: str,
        to_agent: str
    ) -> Dict[str, Any]:
        """
        Селективная очистка tool messages при переключении агентов.
        
        Выполняет:
        1. Сохраняет последний assistant message с результатом (если есть)
        2. Очищает tool_calls и tool_result messages
        3. Добавляет system message о переключении агента
        4. Восстанавливает последний результат (если нужно)
        
        Это предотвращает дублирование tool_call_id между агентами
        и сохраняет контекст выполненной работы.
        
        Args:
            conversation: Conversation для очистки
            from_agent: Исходный агент
            to_agent: Целевой агент
            
        Returns:
            Словарь с информацией об очистке:
            - removed_count: количество удаленных сообщений
            - preserved_result: последний результат (если есть)
            - context_message: добавленное system сообщение
            - final_message_count: итоговое количество сообщений
            
        Пример:
            >>> info = service.clear_tool_messages_with_context(
            ...     conversation,
            ...     from_agent="orchestrator",
            ...     to_agent="coder"
            ... )
            >>> print(f"Removed {info['removed_count']} messages")
        """
        # 1. Сохранить последний assistant message без tool_calls
        last_result = conversation.messages.get_last_assistant_message()
        preserved_content = last_result.content if last_result else None
        
        # 2. Очистить tool messages
        removed_count = self.clear_tool_messages(conversation)
        
        # 3. Создать system message о переключении
        context_message_text = (
            f"Agent switched: {from_agent} → {to_agent}\n"
            f"Previous context preserved. Tool history cleared to prevent conflicts."
        )
        
        context_msg = Message(
            id=str(uuid.uuid4()),
            role="system",
            content=context_message_text,
            created_at=datetime.now(timezone.utc)
        )
        conversation.add_message(context_msg)
        
        # 4. Восстановить последний результат если был и его нет в истории
        if preserved_content:
            has_result = self._has_assistant_message_with_content(
                conversation,
                preserved_content
            )
            
            if not has_result:
                result_msg = Message(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=preserved_content,
                    created_at=datetime.now(timezone.utc)
                )
                conversation.add_message(result_msg)
        
        # Генерируем domain event
        conversation.record_event(
            ToolMessagesCleared(
                conversation_id=conversation.conversation_id.value,
                cleared_count=removed_count,
                preserved_result=preserved_content
            )
        )
        
        return {
            "removed_count": removed_count,
            "preserved_result": preserved_content,
            "context_message": context_message_text,
            "final_message_count": conversation.messages.count()
        }
    
    def _has_assistant_message_with_content(
        self,
        conversation: Conversation,
        content: str
    ) -> bool:
        """
        Проверить, есть ли assistant message с указанным content.
        
        Args:
            conversation: Conversation для проверки
            content: Content для поиска
            
        Returns:
            True если найдено совпадение
        """
        for msg in conversation.messages:
            if (msg.role == "assistant" and
                msg.content == content and
                not msg.tool_calls):
                return True
        return False
    
    def get_tool_message_count(self, conversation: Conversation) -> int:
        """
        Получить количество tool-related messages.
        
        Args:
            conversation: Conversation для анализа
            
        Returns:
            Количество tool messages
            
        Пример:
            >>> count = service.get_tool_message_count(conversation)
            >>> count
            5
        """
        count = 0
        for msg in conversation.messages:
            if (msg.role == "assistant" and msg.tool_calls) or msg.role == "tool":
                count += 1
        return count

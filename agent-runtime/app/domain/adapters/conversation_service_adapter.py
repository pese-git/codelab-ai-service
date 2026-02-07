"""
Conversation Service Adapter.

Адаптер для обратной совместимости между новым ConversationManagementService
и старым SessionManagementService API.

Позволяет постепенно мигрировать код, сохраняя работоспособность.
"""

import logging
from typing import Optional, List, Dict, Any

from ..session_context.services.conversation_management_service import (
    ConversationManagementService
)
from ..session_context.entities import Conversation
from ..session_context.entities.conversation import Conversation as Session
from ..entities.message import Message

logger = logging.getLogger("agent-runtime.adapters.conversation_service")


class ConversationServiceAdapter:
    """
    Адаптер между ConversationManagementService и SessionManagementService API.
    
    Предоставляет старый API SessionManagementService, но использует
    новый ConversationManagementService внутри.
    
    Это позволяет:
    1. Постепенно мигрировать код
    2. Сохранить работоспособность существующего кода
    3. Тестировать новую архитектуру без breaking changes
    
    Атрибуты:
        _conversation_service: Новый сервис для conversations
    
    Пример:
        >>> adapter = ConversationServiceAdapter(conversation_service)
        >>> session = await adapter.create_session("session-1")
        >>> # Внутри использует ConversationManagementService
    """
    
    def __init__(self, conversation_service: ConversationManagementService):
        """
        Инициализация адаптера.
        
        Args:
            conversation_service: Новый сервис для conversations
        """
        self._conversation_service = conversation_service
    
    async def create_session(
        self,
        session_id: Optional[str] = None
    ) -> Session:
        """
        Создать новую сессию (адаптирует create_conversation).
        
        Args:
            session_id: ID сессии
            
        Returns:
            Session (адаптированная из Conversation)
        """
        conversation = await self._conversation_service.create_conversation(
            conversation_id=session_id
        )
        return self._conversation_to_session(conversation)
    
    async def get_session(self, session_id: str) -> Session:
        """
        Получить сессию по ID (адаптирует get_conversation).
        
        Args:
            session_id: ID сессии
            
        Returns:
            Session (адаптированная из Conversation)
        """
        conversation = await self._conversation_service.get_conversation(session_id)
        return self._conversation_to_session(conversation)
    
    async def get_or_create_session(self, session_id: str) -> Session:
        """
        Получить или создать сессию (адаптирует get_or_create_conversation).
        
        Args:
            session_id: ID сессии
            
        Returns:
            Session (адаптированная из Conversation)
        """
        conversation = await self._conversation_service.get_or_create_conversation(
            conversation_id=session_id
        )
        return self._conversation_to_session(conversation)
    
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
        Добавить сообщение в сессию (делегирует в conversation_service).
        
        Args:
            session_id: ID сессии
            role: Роль отправителя
            content: Содержимое сообщения
            name: Имя отправителя
            tool_call_id: ID вызова инструмента
            tool_calls: Вызовы инструментов
            
        Returns:
            Созданное сообщение
        """
        return await self._conversation_service.add_message(
            conversation_id=session_id,
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls
        )
    
    async def add_tool_result(
        self,
        session_id: str,
        call_id: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> Message:
        """
        Добавить результат инструмента (делегирует в conversation_service).
        
        Args:
            session_id: ID сессии
            call_id: ID вызова инструмента
            result: Результат выполнения
            error: Сообщение об ошибке
            
        Returns:
            Созданное сообщение
        """
        return await self._conversation_service.add_tool_result(
            conversation_id=session_id,
            call_id=call_id,
            result=result,
            error=error
        )
    
    async def deactivate_session(
        self,
        session_id: str,
        reason: Optional[str] = None
    ) -> Session:
        """
        Деактивировать сессию (адаптирует deactivate_conversation).
        
        Args:
            session_id: ID сессии
            reason: Причина деактивации
            
        Returns:
            Session (адаптированная из Conversation)
        """
        conversation = await self._conversation_service.deactivate_conversation(
            conversation_id=session_id,
            reason=reason
        )
        return self._conversation_to_session(conversation)
    
    async def list_active_sessions(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """
        Получить список активных сессий (адаптирует list_active_conversations).
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список Session (адаптированных из Conversation)
        """
        conversations = await self._conversation_service.list_active_conversations(
            limit=limit,
            offset=offset
        )
        return [self._conversation_to_session(conv) for conv in conversations]
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Очистить старые сессии (делегирует в conversation_service).
        
        Args:
            max_age_hours: Максимальный возраст в часах
            
        Returns:
            Количество очищенных сессий
        """
        return await self._conversation_service.cleanup_old_conversations(
            max_age_hours=max_age_hours
        )
    
    async def create_subtask_context(
        self,
        session_id: str,
        subtask_id: str,
        dependency_results: Dict[str, Any]
    ) -> str:
        """
        Создать контекст для subtask (делегирует в conversation_service).
        
        Args:
            session_id: ID сессии
            subtask_id: ID subtask
            dependency_results: Результаты зависимостей
            
        Returns:
            ID snapshot
        """
        return await self._conversation_service.create_subtask_context(
            conversation_id=session_id,
            subtask_id=subtask_id,
            dependency_results=dependency_results
        )
    
    async def restore_from_snapshot(
        self,
        session_id: str,
        snapshot_id: str,
        preserve_last_result: bool = True
    ) -> None:
        """
        Восстановить из snapshot (делегирует в conversation_service).
        
        Args:
            session_id: ID сессии
            snapshot_id: ID snapshot
            preserve_last_result: Сохранить последний результат
        """
        await self._conversation_service.restore_from_snapshot(
            conversation_id=session_id,
            snapshot_id=snapshot_id,
            preserve_last_result=preserve_last_result
        )
    
    async def prepare_agent_switch_context(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str
    ) -> Dict[str, Any]:
        """
        Подготовить контекст для переключения агента (делегирует).
        
        Args:
            session_id: ID сессии
            from_agent: Исходный агент
            to_agent: Целевой агент
            
        Returns:
            Информация об очистке
        """
        return await self._conversation_service.prepare_agent_switch_context(
            conversation_id=session_id,
            from_agent=from_agent,
            to_agent=to_agent
        )
    
    def _conversation_to_session(self, conversation: Conversation) -> Session:
        """
        Конвертировать Conversation в Session для обратной совместимости.
        
        Args:
            conversation: Conversation entity
            
        Returns:
            Session entity (legacy)
        """
        # Conversation уже является Session через alias
        # Просто возвращаем conversation
        return conversation

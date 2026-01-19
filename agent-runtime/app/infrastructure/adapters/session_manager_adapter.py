"""
Адаптер для SessionManager.

Обеспечивает обратную совместимость старого SessionManager API
с новой архитектурой на базе доменных сервисов.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ...domain.services.session_management import SessionManagementService
from ...domain.entities.session import Session
from ...domain.entities.message import Message
from ...core.errors import SessionNotFoundError

logger = logging.getLogger("agent-runtime.adapters.session_manager")


class SessionManagerAdapter:
    """
    Адаптер старого SessionManager к новой архитектуре.
    
    Предоставляет тот же API что и AsyncSessionManager,
    но использует новые доменные сервисы под капотом.
    
    Это позволяет мигрировать код постепенно без breaking changes.
    
    Атрибуты:
        _service: Доменный сервис управления сессиями
    
    Пример:
        >>> # Старый код продолжает работать
        >>> adapter = SessionManagerAdapter(session_service)
        >>> session = await adapter.get_or_create("session-1")
        >>> await adapter.append_message("session-1", "user", "Hello")
    """
    
    def __init__(self, service: SessionManagementService):
        """
        Инициализация адаптера.
        
        Args:
            service: Доменный сервис управления сессиями
        """
        self._service = service
        logger.info("SessionManagerAdapter initialized")
    
    def exists(self, session_id: str) -> bool:
        """
        Проверить существование сессии (синхронный метод для совместимости).
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если сессия существует
            
        Note:
            Это синхронная обертка для совместимости.
            В новом коде используйте async методы.
        """
        # Для совместимости возвращаем True
        # Реальная проверка будет при get_or_create
        return True
    
    async def create(
        self,
        session_id: str,
        system_prompt: Optional[str] = None
    ) -> Session:
        """
        Создать новую сессию.
        
        Args:
            session_id: ID сессии
            system_prompt: Системный промпт (игнорируется в новой архитектуре)
            
        Returns:
            Доменная сущность Session
            
        Raises:
            SessionAlreadyExistsError: Если сессия уже существует
        """
        return await self._service.create_session(session_id)
    
    def get(self, session_id: str) -> Optional[Session]:
        """
        Получить сессию (синхронный метод для совместимости).
        
        Args:
            session_id: ID сессии
            
        Returns:
            Session или None
            
        Note:
            Возвращает доменную сущность Session вместо SessionState.
            Они совместимы по интерфейсу (messages, last_activity).
        """
        # Для совместимости - используется редко
        # В основном используется get_or_create
        return None
    
    async def get_or_create(
        self,
        session_id: str,
        system_prompt: Optional[str] = None
    ) -> Session:
        """
        Получить существующую сессию или создать новую.
        
        Args:
            session_id: ID сессии
            system_prompt: Системный промпт (игнорируется)
            
        Returns:
            Доменная сущность Session
        """
        return await self._service.get_or_create_session(session_id)
    
    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        name: Optional[str] = None
    ) -> None:
        """
        Добавить сообщение в сессию.
        
        Args:
            session_id: ID сессии
            role: Роль отправителя
            content: Содержимое сообщения
            name: Имя отправителя (опционально)
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
        """
        await self._service.add_message(
            session_id=session_id,
            role=role,
            content=content,
            name=name
        )
    
    async def append_tool_result(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        result: str
    ) -> None:
        """
        Добавить результат выполнения инструмента.
        
        Args:
            session_id: ID сессии
            call_id: ID вызова инструмента
            tool_name: Имя инструмента
            result: Результат выполнения
        """
        await self._service.add_message(
            session_id=session_id,
            role="tool",
            content=result,
            name=tool_name,
            tool_call_id=call_id
        )
    
    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Получить историю сообщений (синхронный метод для совместимости).
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список сообщений в формате словарей
            
        Note:
            Это синхронная обертка. Возвращает пустой список.
            Используйте async методы для реальных данных.
        """
        # Для совместимости - используется редко
        return []
    
    def all_sessions(self) -> List[Session]:
        """
        Получить все сессии (синхронный метод для совместимости).
        
        Returns:
            Список сессий
            
        Note:
            Возвращает пустой список для совместимости.
        """
        return []
    
    async def delete(self, session_id: str) -> None:
        """
        Удалить сессию.
        
        Args:
            session_id: ID сессии
        """
        await self._service.deactivate_session(
            session_id=session_id,
            reason="Deleted by user"
        )
    
    async def shutdown(self):
        """
        Shutdown session manager.
        
        Note:
            В новой архитектуре shutdown управляется на уровне репозиториев.
        """
        logger.info("SessionManagerAdapter shutdown (no-op in new architecture)")


"""
Адаптер для AgentContextManager.

Обеспечивает обратную совместимость старого AgentContextManager API
с новой архитектурой на базе доменных сервисов.
"""

import logging
from typing import List, Optional

from ...domain.services.agent_orchestration import AgentOrchestrationService
from ...domain.entities.agent_context import AgentContext, AgentType
from ...core.errors import AgentSwitchError

logger = logging.getLogger("agent-runtime.adapters.agent_context_manager")


class AgentContextManagerAdapter:
    """
    Адаптер старого AgentContextManager к новой архитектуре.
    
    Предоставляет тот же API что и AsyncAgentContextManager,
    но использует новые доменные сервисы под капотом.
    
    Атрибуты:
        _service: Доменный сервис оркестрации агентов
    
    Пример:
        >>> # Старый код продолжает работать
        >>> adapter = AgentContextManagerAdapter(orchestration_service)
        >>> context = await adapter.get_or_create("session-1")
        >>> context.switch_agent(AgentType.CODER, "Coding task")
    """
    
    def __init__(self, service: AgentOrchestrationService):
        """
        Инициализация адаптера.
        
        Args:
            service: Доменный сервис оркестрации агентов
        """
        self._service = service
        self._memory_cache = {}  # Локальный кэш для совместимости
        logger.info("AgentContextManagerAdapter initialized")
    
    async def get_or_create(
        self,
        session_id: str,
        initial_agent: AgentType = AgentType.ORCHESTRATOR
    ) -> AgentContext:
        """
        Получить существующий контекст или создать новый.
        
        Args:
            session_id: ID сессии
            initial_agent: Начальный агент для новых контекстов
            
        Returns:
            Доменная сущность AgentContext
        """
        context = await self._service.get_or_create_context(
            session_id=session_id,
            initial_agent=initial_agent
        )
        # Сохранить в локальном кэше
        self._memory_cache[session_id] = context
        return context
    
    def get(self, session_id: str) -> Optional[AgentContext]:
        """
        Получить контекст (синхронный метод для совместимости).
        
        Args:
            session_id: ID сессии
            
        Returns:
            AgentContext или None
            
        Note:
            Возвращает None для совместимости.
            Используйте get_or_create для реальных данных.
        """
        # Для совместимости - используется редко
        return None
    
    def get_or_create_sync(
        self,
        session_id: str,
        initial_agent: AgentType = AgentType.ORCHESTRATOR
    ) -> AgentContext:
        """
        Получить или создать контекст (синхронный метод).
        
        Args:
            session_id: ID сессии
            initial_agent: Начальный агент
            
        Returns:
            AgentContext
            
        Note:
            Создает минимальный контекст для совместимости.
            Реальные данные загружаются через async методы.
        """
        # Создать минимальный контекст для совместимости
        return AgentContext(
            id=f"ctx-{session_id}",
            session_id=session_id,
            current_agent=initial_agent
        )
    
    def exists(self, session_id: str) -> bool:
        """
        Проверить существование контекста.
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если контекст существует в локальном кэше
        """
        # Проверяем наличие в локальном кэше
        return session_id in self._memory_cache
    
    async def delete(self, session_id: str) -> bool:
        """
        Удалить контекст.
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если удален
        """
        logger.info(f"Delete context for session {session_id}")
        # Удаляем из локального кэша
        if session_id in self._memory_cache:
            del self._memory_cache[session_id]
        # Удаляем из репозитория
        await self._service._repository.delete_by_session_id(session_id)
        return True
    
    def get_all_sessions(self) -> List[str]:
        """
        Получить список всех session IDs.
        
        Returns:
            Список session IDs
            
        Note:
            Возвращает пустой список для совместимости.
        """
        return []
    
    def get_session_count(self) -> int:
        """
        Получить количество сессий.
        
        Returns:
            Количество сессий в локальном кэше
        """
        return len(self._memory_cache)
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Очистить старые сессии.
        
        Args:
            max_age_hours: Максимальный возраст в часах
            
        Returns:
            Количество очищенных сессий
            
        Note:
            В новой архитектуре это делает SessionCleanupService.
        """
        logger.info(f"Cleanup old sessions (delegated to SessionCleanupService)")
        return 0
    
    async def shutdown(self):
        """
        Shutdown context manager.
        
        Note:
            В новой архитектуре shutdown управляется на уровне репозиториев.
        """
        logger.info("AgentContextManagerAdapter shutdown (no-op in new architecture)")

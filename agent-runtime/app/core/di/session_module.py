"""
DI Module для Session Context.

Предоставляет зависимости для работы с conversations (sessions).
"""

import logging
from typing import Optional, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.session_context.services import (
    ConversationManagementService,
    ConversationSnapshotService,
    ToolMessageCleanupService
)
from app.domain.session_context.repositories import ConversationRepository
from app.infrastructure.persistence.repositories import ConversationRepositoryImpl

if TYPE_CHECKING:
    from app.infrastructure.adapters.event_publisher_adapter import EventPublisher

logger = logging.getLogger("agent-runtime.di.session_module")


class SessionModule:
    """
    DI модуль для Session Context.
    
    Предоставляет:
    - ConversationRepository
    - ConversationManagementService (новая архитектура)
    - ConversationSnapshotService
    - ToolMessageCleanupService
    
    Обратная совместимость:
    - provide_session_service() возвращает ConversationManagementService
      (замена для SessionManagementService)
    """
    
    def __init__(self):
        """Инициализация модуля."""
        self._conversation_repository: Optional[ConversationRepository] = None
        self._conversation_service: Optional[ConversationManagementService] = None
        self._snapshot_service: Optional[ConversationSnapshotService] = None
        self._cleanup_service: Optional[ToolMessageCleanupService] = None
        
        logger.debug("SessionModule инициализирован")
    
    def provide_conversation_repository(
        self,
        db: AsyncSession
    ) -> ConversationRepository:
        """
        Предоставить репозиторий conversations.
        
        Args:
            db: Сессия БД
            
        Returns:
            ConversationRepository: Реализация репозитория
        """
        return ConversationRepositoryImpl(db)
    
    def provide_conversation_service(
        self,
        conversation_repository: ConversationRepository
    ) -> ConversationManagementService:
        """
        Предоставить сервис управления conversations.
        
        Args:
            conversation_repository: Репозиторий conversations
            
        Returns:
            ConversationManagementService: Сервис управления
        """
        if self._conversation_service is None:
            self._conversation_service = ConversationManagementService(
                repository=conversation_repository
            )
        return self._conversation_service
    
    def provide_snapshot_service(self) -> ConversationSnapshotService:
        """
        Предоставить сервис snapshot'ов.
        
        Returns:
            ConversationSnapshotService: Сервис snapshot'ов
        """
        if self._snapshot_service is None:
            self._snapshot_service = ConversationSnapshotService()
        return self._snapshot_service
    
    def provide_cleanup_service(self) -> ToolMessageCleanupService:
        """
        Предоставить сервис очистки tool messages.
        
        Returns:
            ToolMessageCleanupService: Сервис очистки
        """
        if self._cleanup_service is None:
            self._cleanup_service = ToolMessageCleanupService()
        return self._cleanup_service
    
    def provide_session_service(
        self,
        db: AsyncSession,
        event_publisher: Optional["EventPublisher"] = None,
        uow=None
    ) -> ConversationManagementService:
        """
        Предоставить сервис управления сессиями.
        
        Это метод обратной совместимости, который возвращает ConversationManagementService
        вместо устаревшего SessionManagementService.
        
        Args:
            db: Сессия БД (deprecated, используйте uow)
            event_publisher: Event publisher (опционально, для совместимости)
            uow: Unit of Work (рекомендуется для использования единой сессии)
            
        Returns:
            ConversationManagementService: Сервис управления conversations
        """
        # ✅ Если передан uow, используем его repository напрямую
        if uow:
            # ИСПРАВЛЕНИЕ: НЕ передаем event_publisher, так как он не callable
            # ConversationManagementService создаст новый экземпляр без кэширования
            return ConversationManagementService(
                repository=uow.conversations,
                event_publisher=None,  # Отключаем events для UoW-based сервисов
                uow=uow
            )
        else:
            # Fallback для обратной совместимости
            conversation_repository = self.provide_conversation_repository(db)
            return self.provide_conversation_service(conversation_repository)
    
    def provide_conversation_management_service(
        self,
        conversation_repository: ConversationRepository
    ) -> ConversationManagementService:
        """
        Предоставить сервис управления conversations.
        
        Alias для provide_conversation_service для совместимости.
        
        Args:
            conversation_repository: Репозиторий conversations
            
        Returns:
            ConversationManagementService: Сервис управления
        """
        return self.provide_conversation_service(conversation_repository)

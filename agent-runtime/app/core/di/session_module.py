"""
DI Module для Session Context.

Предоставляет зависимости для работы с conversations (sessions).
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.session_context.services import (
    ConversationManagementService,
    ConversationSnapshotService,
    ToolMessageCleanupService
)
from app.domain.session_context.repositories import ConversationRepository
from app.infrastructure.persistence.repositories import ConversationRepositoryImpl
from app.domain.services import SessionManagementService

logger = logging.getLogger("agent-runtime.di.session_module")


class SessionModule:
    """
    DI модуль для Session Context.
    
    Предоставляет:
    - ConversationRepository
    - ConversationManagementService
    - ConversationSnapshotService
    - ToolMessageCleanupService
    - SessionManagementService (legacy, для обратной совместимости)
    """
    
    def __init__(self):
        """Инициализация модуля."""
        self._conversation_repository: Optional[ConversationRepository] = None
        self._conversation_service: Optional[ConversationManagementService] = None
        self._snapshot_service: Optional[ConversationSnapshotService] = None
        self._cleanup_service: Optional[ToolMessageCleanupService] = None
        self._session_service: Optional[SessionManagementService] = None
        
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
        event_publisher=None
    ) -> SessionManagementService:
        """
        Предоставить legacy SessionManagementService.
        
        Для обратной совместимости со старым кодом.
        
        Args:
            db: Сессия БД
            event_publisher: Publisher событий (опционально)
            
        Returns:
            SessionManagementService: Legacy сервис
        """
        if self._session_service is None:
            from app.infrastructure.persistence.repositories import (
                SessionRepositoryImpl,
                AgentContextRepositoryImpl
            )
            
            session_repo = SessionRepositoryImpl(db)
            
            self._session_service = SessionManagementService(
                repository=session_repo,
                event_publisher=event_publisher
            )
        
        return self._session_service

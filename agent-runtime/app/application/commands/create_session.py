"""
Команда создания сессии.

Создает новую сессию диалога с AI агентом.
"""

from typing import Optional
from pydantic import Field

from .base import Command, CommandHandler
from ...domain.session_context.services import ConversationManagementService
from ...domain.session_context.value_objects import ConversationId
from ...domain.session_context.entities.conversation import Conversation as Session
from ..dto.session_dto import SessionDTO


class CreateSessionCommand(Command):
    """
    Команда создания новой сессии.
    
    Атрибуты:
        session_id: ID сессии (опционально, генерируется автоматически)
    
    Пример:
        >>> command = CreateSessionCommand(session_id="session-123")
        >>> # Или с автогенерацией ID
        >>> command = CreateSessionCommand()
    """
    
    session_id: Optional[str] = Field(
        default=None,
        description="ID сессии (если None, генерируется автоматически)"
    )


class CreateSessionHandler(CommandHandler[SessionDTO]):
    """
    Обработчик команды создания сессии.
    
    Создает новую сессию через доменный сервис и
    возвращает DTO с информацией о созданной сессии.
    
    Атрибуты:
        _session_service: Доменный сервис управления сессиями
    
    Пример:
        >>> handler = CreateSessionHandler(session_service)
        >>> command = CreateSessionCommand(session_id="session-1")
        >>> dto = await handler.handle(command)
        >>> dto.id
        'session-1'
    """
    
    def __init__(self, conversation_service: ConversationManagementService):
        """
        Инициализация обработчика.
        
        Args:
            conversation_service: Доменный сервис управления conversations
        """
        self._conversation_service = conversation_service
    
    async def handle(self, command: CreateSessionCommand) -> SessionDTO:
        """
        Обработать команду создания сессии.
        
        Args:
            command: Команда создания сессии
            
        Returns:
            DTO созданной сессии
            
        Raises:
            SessionAlreadyExistsError: Если сессия с таким ID уже существует
            
        Пример:
            >>> command = CreateSessionCommand(session_id="session-1")
            >>> dto = await handler.handle(command)
        """
        # Создать conversation через доменный сервис
        # ConversationManagementService сам создаст ConversationId из строки
        session = await self._conversation_service.create_conversation(
            conversation_id=command.session_id
        )
        
        # Преобразовать в DTO
        return SessionDTO.from_entity(session, include_messages=False)

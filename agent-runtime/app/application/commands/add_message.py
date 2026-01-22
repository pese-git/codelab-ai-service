"""
Команда добавления сообщения.

Добавляет новое сообщение в сессию диалога.
"""

from typing import Optional, Dict, Any, List
from pydantic import Field

from .base import Command, CommandHandler
from ...domain.services.session_management import SessionManagementService
from ..dto.message_dto import MessageDTO


class AddMessageCommand(Command):
    """
    Команда добавления сообщения в сессию.
    
    Атрибуты:
        session_id: ID сессии
        role: Роль отправителя (user, assistant, system, tool)
        content: Содержимое сообщения
        name: Имя отправителя (опционально)
        tool_call_id: ID вызова инструмента (опционально)
        tool_calls: Вызовы инструментов (опционально)
    
    Пример:
        >>> # Пользовательское сообщение
        >>> command = AddMessageCommand(
        ...     session_id="session-1",
        ...     role="user",
        ...     content="Создай новый файл"
        ... )
        >>> 
        >>> # Сообщение с вызовом инструмента
        >>> command = AddMessageCommand(
        ...     session_id="session-1",
        ...     role="assistant",
        ...     content="",
        ...     tool_calls=[{
        ...         "id": "call-1",
        ...         "tool_name": "write_file",
        ...         "arguments": {"path": "test.py", "content": "..."}
        ...     }]
        ... )
    """
    
    session_id: str = Field(description="ID сессии")
    role: str = Field(description="Роль отправителя")
    content: str = Field(default="", description="Содержимое сообщения")
    name: Optional[str] = Field(default=None, description="Имя отправителя")
    tool_call_id: Optional[str] = Field(
        default=None,
        description="ID вызова инструмента"
    )
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Вызовы инструментов"
    )


class AddMessageHandler(CommandHandler[MessageDTO]):
    """
    Обработчик команды добавления сообщения.
    
    Добавляет сообщение в сессию через доменный сервис и
    возвращает DTO созданного сообщения.
    
    Атрибуты:
        _session_service: Доменный сервис управления сессиями
    
    Пример:
        >>> handler = AddMessageHandler(session_service)
        >>> command = AddMessageCommand(
        ...     session_id="session-1",
        ...     role="user",
        ...     content="Привет!"
        ... )
        >>> dto = await handler.handle(command)
    """
    
    def __init__(self, session_service: SessionManagementService):
        """
        Инициализация обработчика.
        
        Args:
            session_service: Доменный сервис управления сессиями
        """
        self._session_service = session_service
    
    async def handle(self, command: AddMessageCommand) -> MessageDTO:
        """
        Обработать команду добавления сообщения.
        
        Args:
            command: Команда добавления сообщения
            
        Returns:
            DTO созданного сообщения
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            MessageValidationError: Если сообщение не прошло валидацию
            
        Пример:
            >>> command = AddMessageCommand(
            ...     session_id="session-1",
            ...     role="user",
            ...     content="Привет!"
            ... )
            >>> dto = await handler.handle(command)
        """
        # Добавить сообщение через доменный сервис
        message = await self._session_service.add_message(
            session_id=command.session_id,
            role=command.role,
            content=command.content,
            name=command.name,
            tool_call_id=command.tool_call_id,
            tool_calls=command.tool_calls
        )
        
        # Преобразовать в DTO
        return MessageDTO.from_entity(message)

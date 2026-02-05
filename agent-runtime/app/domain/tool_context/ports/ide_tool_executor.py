"""
Port для выполнения инструментов на стороне IDE.

Абстракция для выполнения инструментов через WebSocket.
"""

from abc import ABC, abstractmethod

from ..value_objects import ToolName, ToolResult
from ..entities import ToolCall


class IIDEToolExecutor(ABC):
    """
    Port для выполнения инструментов на стороне IDE.
    
    IDE инструменты выполняются через WebSocket:
    - read_file: Чтение файла
    - write_file: Запись файла
    - execute_command: Выполнение команды
    - search_in_code: Поиск в коде
    - list_files: Список файлов
    - create_directory: Создание директории
    
    Примеры:
        >>> executor = IDEToolExecutorImpl(websocket_client)
        >>> tool_call = ToolCall.create(...)
        >>> result = await executor.execute(tool_call)
        >>> result.is_success()
        True
    """
    
    @abstractmethod
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Выполнить IDE инструмент через WebSocket.
        
        Args:
            tool_call: Вызов инструмента для выполнения
            
        Returns:
            ToolResult с результатом выполнения
            
        Raises:
            ConnectionError: Если IDE недоступен
            TimeoutError: Если превышен таймаут
            
        Example:
            >>> result = await executor.execute(tool_call)
            >>> if result.is_success():
            ...     print(result.get_content())
        """
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """
        Проверить доступность IDE.
        
        Returns:
            True если IDE подключен и доступен
            
        Example:
            >>> if await executor.is_available():
            ...     result = await executor.execute(tool_call)
        """
        pass
    
    @abstractmethod
    def supports(self, tool_name: ToolName) -> bool:
        """
        Проверить поддержку инструмента.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            True если инструмент поддерживается
            
        Example:
            >>> executor.supports(ToolName.from_string("read_file"))
            True
            >>> executor.supports(ToolName.from_string("echo"))
            False
        """
        pass
    
    @abstractmethod
    def get_supported_tools(self) -> list[ToolName]:
        """
        Получить список поддерживаемых инструментов.
        
        Returns:
            Список имен поддерживаемых инструментов
            
        Example:
            >>> tools = executor.get_supported_tools()
            >>> len(tools)
            6
        """
        pass

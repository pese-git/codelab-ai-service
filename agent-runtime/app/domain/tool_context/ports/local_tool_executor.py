"""
Port для выполнения локальных инструментов.

Абстракция для выполнения инструментов в agent-runtime.
"""

from abc import ABC, abstractmethod

from ..value_objects import ToolName, ToolResult
from ..entities import ToolCall


class ILocalToolExecutor(ABC):
    """
    Port для выполнения локальных инструментов.
    
    Локальные инструменты выполняются в agent-runtime:
    - echo: Эхо текста
    - calculator: Вычисление математических выражений
    - switch_mode: Переключение режима агента
    
    Примеры:
        >>> executor = LocalToolExecutorImpl()
        >>> tool_call = ToolCall.create(...)
        >>> result = await executor.execute(tool_call)
        >>> result.is_success()
        True
    """
    
    @abstractmethod
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Выполнить локальный инструмент.
        
        Args:
            tool_call: Вызов инструмента для выполнения
            
        Returns:
            ToolResult с результатом выполнения
            
        Raises:
            ValueError: Если инструмент не поддерживается
            
        Example:
            >>> result = await executor.execute(tool_call)
            >>> if result.is_success():
            ...     print(result.get_content())
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
            >>> executor.supports(ToolName.from_string("echo"))
            True
            >>> executor.supports(ToolName.from_string("read_file"))
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
            3
        """
        pass

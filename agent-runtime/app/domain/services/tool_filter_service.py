"""
Доменный сервис фильтрации инструментов.

Применяет бизнес-правила доступа к инструментам для разных агентов.
"""

import logging
from typing import List, Optional, Dict, Any

from .tool_registry import ToolRegistry

logger = logging.getLogger("agent-runtime.domain.tool_filter_service")


class ToolFilterService:
    """
    Доменный сервис фильтрации инструментов.
    
    Инкапсулирует бизнес-правила доступа к инструментам:
    1. Фильтрация по разрешенным инструментам для агента
    2. Применение ограничений доступа
    3. Валидация доступности инструментов
    
    Атрибуты:
        _tool_registry: Реестр всех доступных инструментов
    
    Пример:
        >>> filter_service = ToolFilterService(tool_registry)
        >>> # Получить все инструменты
        >>> all_tools = filter_service.filter_tools(allowed_tools=None)
        >>> # Получить только разрешенные
        >>> filtered = filter_service.filter_tools(allowed_tools=["read_file", "write_file"])
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        """
        Инициализация сервиса фильтрации.
        
        Args:
            tool_registry: Реестр инструментов
        """
        self._tool_registry = tool_registry
    
    def filter_tools(
        self,
        allowed_tools: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Фильтровать инструменты по разрешенным.
        
        Бизнес-правило:
        - Если allowed_tools = None, возвращаем все инструменты
        - Если allowed_tools указан, возвращаем только разрешенные
        - Неизвестные инструменты игнорируются с предупреждением
        
        Args:
            allowed_tools: Список имен разрешенных инструментов (None = все)
            
        Returns:
            Список спецификаций инструментов в формате OpenAI tools
            
        Пример:
            >>> # Все инструменты
            >>> all_tools = filter_service.filter_tools(None)
            >>> len(all_tools)
            15
            >>> 
            >>> # Только для чтения
            >>> read_only = filter_service.filter_tools(["read_file", "list_files"])
            >>> len(read_only)
            2
        """
        # Получить все инструменты из реестра
        all_tools = self._tool_registry.get_all_tools()
        
        # Если фильтр не указан, вернуть все
        if allowed_tools is None:
            logger.debug(f"No filter specified, returning all {len(all_tools)} tools")
            return all_tools
        
        # Фильтрация по разрешенным
        filtered_tools = []
        unknown_tools = []
        
        for tool in all_tools:
            tool_name = tool["function"]["name"]
            if tool_name in allowed_tools:
                filtered_tools.append(tool)
        
        # Проверка на неизвестные инструменты
        known_tool_names = {tool["function"]["name"] for tool in all_tools}
        for requested_tool in allowed_tools:
            if requested_tool not in known_tool_names:
                unknown_tools.append(requested_tool)
        
        if unknown_tools:
            logger.warning(
                f"Requested unknown tools: {unknown_tools}. "
                f"Available tools: {sorted(known_tool_names)}"
            )
        
        logger.debug(
            f"Filtered tools: {len(filtered_tools)}/{len(all_tools)} "
            f"(allowed: {allowed_tools})"
        )
        
        return filtered_tools
    
    def get_tool_names(self, allowed_tools: Optional[List[str]] = None) -> List[str]:
        """
        Получить список имен инструментов после фильтрации.
        
        Args:
            allowed_tools: Список разрешенных инструментов
            
        Returns:
            Список имен инструментов
            
        Пример:
            >>> names = filter_service.get_tool_names(["read_file", "write_file"])
            >>> names
            ['read_file', 'write_file']
        """
        tools = self.filter_tools(allowed_tools)
        return [tool["function"]["name"] for tool in tools]
    
    def is_tool_allowed(
        self,
        tool_name: str,
        allowed_tools: Optional[List[str]] = None
    ) -> bool:
        """
        Проверить, разрешен ли инструмент.
        
        Args:
            tool_name: Имя инструмента
            allowed_tools: Список разрешенных инструментов (None = все разрешены)
            
        Returns:
            True если инструмент разрешен
            
        Пример:
            >>> is_allowed = filter_service.is_tool_allowed(
            ...     "write_file",
            ...     allowed_tools=["read_file", "write_file"]
            ... )
            >>> is_allowed
            True
        """
        # Если фильтр не указан, все разрешены
        if allowed_tools is None:
            return True
        
        return tool_name in allowed_tools
    
    def validate_tool_access(
        self,
        tool_name: str,
        allowed_tools: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Валидировать доступ к инструменту.
        
        Проверяет:
        1. Существует ли инструмент в реестре
        2. Разрешен ли инструмент для использования
        
        Args:
            tool_name: Имя инструмента
            allowed_tools: Список разрешенных инструментов
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            
        Пример:
            >>> is_valid, error = filter_service.validate_tool_access(
            ...     "unknown_tool",
            ...     allowed_tools=["read_file"]
            ... )
            >>> is_valid
            False
            >>> error
            "Tool 'unknown_tool' does not exist in registry"
        """
        # Проверка существования в реестре
        all_tool_names = {
            tool["function"]["name"]
            for tool in self._tool_registry.get_all_tools()
        }
        
        if tool_name not in all_tool_names:
            return False, f"Tool '{tool_name}' does not exist in registry"
        
        # Проверка разрешения
        if not self.is_tool_allowed(tool_name, allowed_tools):
            return False, f"Tool '{tool_name}' is not allowed for this agent"
        
        return True, None

"""
AgentCapabilities Value Object.

Инкапсулирует возможности и ограничения агента.
"""

from typing import List, Set, Optional
from enum import Enum

from ...shared.value_object import ValueObject


class AgentType(str, Enum):
    """
    Типы агентов в системе.
    
    Каждый агент имеет свою специализацию и набор инструментов.
    """
    ORCHESTRATOR = "orchestrator"  # Маршрутизация задач
    CODER = "coder"                # Написание кода
    ARCHITECT = "architect"        # Проектирование архитектуры
    DEBUG = "debug"                # Отладка и исследование
    ASK = "ask"                    # Ответы на вопросы
    UNIVERSAL = "universal"        # Универсальный агент


class AgentCapabilities(ValueObject):
    """
    Value Object для возможностей агента.
    
    Определяет что агент может делать:
    - Тип агента
    - Поддерживаемые инструменты
    - Максимальное количество переключений
    - Специальные возможности
    
    Атрибуты:
        agent_type: Тип агента
        supported_tools: Набор поддерживаемых инструментов
        max_switches: Максимальное количество переключений
        can_delegate: Может ли агент делегировать задачи
        requires_approval: Требуется ли одобрение для действий
    
    Пример:
        >>> caps = AgentCapabilities.for_coder()
        >>> caps.agent_type
        <AgentType.CODER: 'coder'>
        >>> "write_file" in caps.supported_tools
        True
    """
    
    def __init__(
        self,
        agent_type: AgentType,
        supported_tools: Optional[Set[str]] = None,
        max_switches: int = 50,
        can_delegate: bool = False,
        requires_approval: bool = False
    ) -> None:
        """
        Создать AgentCapabilities с валидацией.
        
        Args:
            agent_type: Тип агента
            supported_tools: Набор поддерживаемых инструментов
            max_switches: Максимальное количество переключений
            can_delegate: Может ли агент делегировать задачи
            requires_approval: Требуется ли одобрение для действий
            
        Raises:
            ValueError: Если параметры невалидны
            
        Пример:
            >>> caps = AgentCapabilities(
            ...     agent_type=AgentType.CODER,
            ...     supported_tools={"write_file", "read_file"},
            ...     max_switches=50
            ... )
        """
        if not isinstance(agent_type, AgentType):
            raise ValueError(f"agent_type должен быть AgentType, получен {type(agent_type).__name__}")
        
        if max_switches < 1:
            raise ValueError(f"max_switches должен быть >= 1, получен {max_switches}")
        
        if max_switches > 1000:
            raise ValueError(f"max_switches слишком большой: {max_switches} (максимум 1000)")
        
        self._agent_type = agent_type
        self._supported_tools = frozenset(supported_tools or set())
        self._max_switches = max_switches
        self._can_delegate = can_delegate
        self._requires_approval = requires_approval
    
    @property
    def agent_type(self) -> AgentType:
        """Получить тип агента."""
        return self._agent_type
    
    @property
    def supported_tools(self) -> frozenset:
        """Получить набор поддерживаемых инструментов."""
        return self._supported_tools
    
    @property
    def max_switches(self) -> int:
        """Получить максимальное количество переключений."""
        return self._max_switches
    
    @property
    def can_delegate(self) -> bool:
        """Может ли агент делегировать задачи."""
        return self._can_delegate
    
    @property
    def requires_approval(self) -> bool:
        """Требуется ли одобрение для действий."""
        return self._requires_approval
    
    def supports_tool(self, tool_name: str) -> bool:
        """
        Проверить поддержку инструмента.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            True если инструмент поддерживается
            
        Пример:
            >>> caps = AgentCapabilities.for_coder()
            >>> caps.supports_tool("write_file")
            True
            >>> caps.supports_tool("unknown_tool")
            False
        """
        return tool_name in self._supported_tools
    
    def get_tool_list(self) -> List[str]:
        """
        Получить список поддерживаемых инструментов.
        
        Returns:
            Отсортированный список инструментов
            
        Пример:
            >>> caps = AgentCapabilities.for_coder()
            >>> tools = caps.get_tool_list()
            >>> "write_file" in tools
            True
        """
        return sorted(self._supported_tools)
    
    @staticmethod
    def for_orchestrator() -> "AgentCapabilities":
        """
        Создать capabilities для Orchestrator агента.
        
        Orchestrator может:
        - Делегировать задачи другим агентам
        - Создавать планы выполнения
        - Маршрутизировать запросы
        
        Returns:
            AgentCapabilities для Orchestrator
            
        Пример:
            >>> caps = AgentCapabilities.for_orchestrator()
            >>> caps.can_delegate
            True
        """
        return AgentCapabilities(
            agent_type=AgentType.ORCHESTRATOR,
            supported_tools={
                "create_plan",
                "delegate_task",
                "route_request"
            },
            max_switches=50,
            can_delegate=True,
            requires_approval=False
        )
    
    @staticmethod
    def for_coder() -> "AgentCapabilities":
        """
        Создать capabilities для Coder агента.
        
        Coder может:
        - Писать и редактировать код
        - Читать файлы
        - Выполнять команды
        
        Returns:
            AgentCapabilities для Coder
            
        Пример:
            >>> caps = AgentCapabilities.for_coder()
            >>> caps.supports_tool("write_file")
            True
        """
        return AgentCapabilities(
            agent_type=AgentType.CODER,
            supported_tools={
                "write_file",
                "read_file",
                "apply_diff",
                "execute_command",
                "list_files",
                "search_files"
            },
            max_switches=50,
            can_delegate=False,
            requires_approval=True  # Требует одобрения для изменений
        )
    
    @staticmethod
    def for_architect() -> "AgentCapabilities":
        """
        Создать capabilities для Architect агента.
        
        Architect может:
        - Проектировать архитектуру
        - Создавать документацию
        - Анализировать код
        
        Returns:
            AgentCapabilities для Architect
            
        Пример:
            >>> caps = AgentCapabilities.for_architect()
            >>> caps.agent_type
            <AgentType.ARCHITECT: 'architect'>
        """
        return AgentCapabilities(
            agent_type=AgentType.ARCHITECT,
            supported_tools={
                "write_file",
                "read_file",
                "list_files",
                "search_files",
                "create_diagram"
            },
            max_switches=50,
            can_delegate=False,
            requires_approval=False
        )
    
    @staticmethod
    def for_debug() -> "AgentCapabilities":
        """
        Создать capabilities для Debug агента.
        
        Debug может:
        - Анализировать ошибки
        - Читать логи
        - Выполнять диагностические команды
        
        Returns:
            AgentCapabilities для Debug
            
        Пример:
            >>> caps = AgentCapabilities.for_debug()
            >>> caps.supports_tool("read_file")
            True
        """
        return AgentCapabilities(
            agent_type=AgentType.DEBUG,
            supported_tools={
                "read_file",
                "list_files",
                "search_files",
                "execute_command",
                "analyze_logs"
            },
            max_switches=50,
            can_delegate=False,
            requires_approval=False
        )
    
    @staticmethod
    def for_ask() -> "AgentCapabilities":
        """
        Создать capabilities для Ask агента.
        
        Ask может:
        - Отвечать на вопросы
        - Читать документацию
        - Искать информацию
        
        Returns:
            AgentCapabilities для Ask
            
        Пример:
            >>> caps = AgentCapabilities.for_ask()
            >>> caps.requires_approval
            False
        """
        return AgentCapabilities(
            agent_type=AgentType.ASK,
            supported_tools={
                "read_file",
                "search_files",
                "list_files"
            },
            max_switches=50,
            can_delegate=False,
            requires_approval=False
        )
    
    @staticmethod
    def for_universal() -> "AgentCapabilities":
        """
        Создать capabilities для Universal агента.
        
        Universal имеет все возможности.
        
        Returns:
            AgentCapabilities для Universal
            
        Пример:
            >>> caps = AgentCapabilities.for_universal()
            >>> caps.can_delegate
            True
        """
        return AgentCapabilities(
            agent_type=AgentType.UNIVERSAL,
            supported_tools={
                "write_file",
                "read_file",
                "apply_diff",
                "execute_command",
                "list_files",
                "search_files",
                "create_plan",
                "delegate_task",
                "route_request",
                "analyze_logs",
                "create_diagram"
            },
            max_switches=100,
            can_delegate=True,
            requires_approval=True
        )
    
    @staticmethod
    def for_agent_type(agent_type: AgentType) -> "AgentCapabilities":
        """
        Создать capabilities для указанного типа агента.
        
        Args:
            agent_type: Тип агента
            
        Returns:
            AgentCapabilities для указанного типа
            
        Raises:
            ValueError: Если тип агента неизвестен
            
        Пример:
            >>> caps = AgentCapabilities.for_agent_type(AgentType.CODER)
            >>> caps.agent_type
            <AgentType.CODER: 'coder'>
        """
        factory_map = {
            AgentType.ORCHESTRATOR: AgentCapabilities.for_orchestrator,
            AgentType.CODER: AgentCapabilities.for_coder,
            AgentType.ARCHITECT: AgentCapabilities.for_architect,
            AgentType.DEBUG: AgentCapabilities.for_debug,
            AgentType.ASK: AgentCapabilities.for_ask,
            AgentType.UNIVERSAL: AgentCapabilities.for_universal
        }
        
        factory = factory_map.get(agent_type)
        if not factory:
            raise ValueError(f"Неизвестный тип агента: {agent_type}")
        
        return factory()
    
    def __str__(self) -> str:
        """Строковое представление."""
        return f"{self._agent_type.value} ({len(self._supported_tools)} tools)"
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return (
            f"AgentCapabilities("
            f"agent_type={self._agent_type.value}, "
            f"tools={len(self._supported_tools)}, "
            f"max_switches={self._max_switches})"
        )
    
    def __eq__(self, other: object) -> bool:
        """
        Сравнение на равенство.
        
        Args:
            other: Объект для сравнения
            
        Returns:
            True если capabilities равны
        """
        if not isinstance(other, AgentCapabilities):
            return False
        return (
            self._agent_type == other._agent_type and
            self._supported_tools == other._supported_tools and
            self._max_switches == other._max_switches and
            self._can_delegate == other._can_delegate and
            self._requires_approval == other._requires_approval
        )
    
    def __hash__(self) -> int:
        """
        Хеш для использования в множествах и словарях.
        
        Returns:
            Хеш capabilities
        """
        return hash((
            self._agent_type,
            self._supported_tools,
            self._max_switches,
            self._can_delegate,
            self._requires_approval
        ))

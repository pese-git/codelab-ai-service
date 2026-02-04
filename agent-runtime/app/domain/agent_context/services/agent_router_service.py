"""
AgentRouter Domain Service.

Сервис для маршрутизации и выбора подходящего агента.
"""

from typing import Optional, Dict, Any
import re

from ..value_objects.agent_capabilities import AgentType
from ..entities.agent import Agent


class AgentRouterService:
    """
    Domain Service для маршрутизации агентов.
    
    Определяет какой агент должен обрабатывать запрос
    на основе содержимого сообщения и контекста.
    
    Бизнес-правила:
        - Orchestrator по умолчанию для новых сессий
        - Coder для задач с кодом
        - Architect для проектирования
        - Debug для отладки
        - Ask для вопросов
    
    Пример:
        >>> router = AgentRouterService()
        >>> agent_type = router.route_by_message("Write a function")
        >>> agent_type
        <AgentType.CODER: 'coder'>
    """
    
    # Паттерны для определения типа задачи
    CODE_PATTERNS = [
        r'\b(write|create|implement|code|function|class|method)\b',
        r'\b(fix|bug|error|debug)\b',
        r'\b(refactor|optimize|improve)\b',
        r'\b(test|unittest)\b',
    ]
    
    ARCHITECTURE_PATTERNS = [
        r'\b(design|architect|structure|organize)\b',
        r'\b(plan|strategy|approach)\b',
        r'\b(diagram|schema|model)\b',
        r'\b(pattern|principle)\b',
    ]
    
    DEBUG_PATTERNS = [
        r'\b(debug|investigate|analyze|diagnose)\b',
        r'\b(error|exception|crash|fail)\b',
        r'\b(log|trace|stack)\b',
        r'\b(why|what.*wrong|not.*work)\b',
    ]
    
    ASK_PATTERNS = [
        r'\b(what|how|why|when|where|who)\b',
        r'\b(explain|describe|tell|show)\b',
        r'\b(question|ask|help|understand)\b',
        r'\b(documentation|docs|readme)\b',
    ]
    
    def route_by_message(
        self,
        message: str,
        current_agent: Optional[Agent] = None
    ) -> AgentType:
        """
        Определить тип агента на основе сообщения.
        
        Args:
            message: Текст сообщения пользователя
            current_agent: Текущий агент (опционально)
            
        Returns:
            Рекомендуемый тип агента
            
        Пример:
            >>> router = AgentRouterService()
            >>> router.route_by_message("Create a new class")
            <AgentType.CODER: 'coder'>
            >>> router.route_by_message("Why is this not working?")
            <AgentType.DEBUG: 'debug'>
        """
        message_lower = message.lower()
        
        # Подсчет совпадений для каждого типа
        scores = {
            AgentType.CODER: self._count_pattern_matches(message_lower, self.CODE_PATTERNS),
            AgentType.ARCHITECT: self._count_pattern_matches(message_lower, self.ARCHITECTURE_PATTERNS),
            AgentType.DEBUG: self._count_pattern_matches(message_lower, self.DEBUG_PATTERNS),
            AgentType.ASK: self._count_pattern_matches(message_lower, self.ASK_PATTERNS),
        }
        
        # Найти тип с максимальным score
        max_score = max(scores.values())
        
        # Если нет явных паттернов, использовать Orchestrator
        if max_score == 0:
            return AgentType.ORCHESTRATOR
        
        # Вернуть тип с максимальным score
        for agent_type, score in scores.items():
            if score == max_score:
                return agent_type
        
        return AgentType.ORCHESTRATOR
    
    def should_switch_agent(
        self,
        current_agent: Agent,
        message: str
    ) -> tuple[bool, Optional[AgentType], str]:
        """
        Определить нужно ли переключить агента.
        
        Args:
            current_agent: Текущий агент
            message: Текст сообщения
            
        Returns:
            Кортеж (нужно_переключить, новый_тип, причина)
            
        Пример:
            >>> agent = Agent.create(
            ...     session_id="session-123",
            ...     capabilities=AgentCapabilities.for_orchestrator()
            ... )
            >>> router = AgentRouterService()
            >>> should_switch, new_type, reason = router.should_switch_agent(
            ...     agent, "Write a function"
            ... )
            >>> should_switch
            True
            >>> new_type
            <AgentType.CODER: 'coder'>
        """
        # Определить рекомендуемый тип
        recommended_type = self.route_by_message(message, current_agent)
        
        # Если рекомендуемый тип совпадает с текущим
        if recommended_type == current_agent.current_type:
            return False, None, ""
        
        # Проверить возможность переключения
        if not current_agent.can_switch_to(recommended_type):
            return False, None, "Cannot switch: limit reached or same type"
        
        # Сформировать причину переключения
        reason = self._get_switch_reason(
            current_agent.current_type,
            recommended_type,
            message
        )
        
        return True, recommended_type, reason
    
    def get_confidence(
        self,
        message: str,
        agent_type: AgentType
    ) -> str:
        """
        Определить уверенность в выборе агента.
        
        Args:
            message: Текст сообщения
            agent_type: Тип агента
            
        Returns:
            Уровень уверенности: "low", "medium", "high"
            
        Пример:
            >>> router = AgentRouterService()
            >>> router.get_confidence("Write a function", AgentType.CODER)
            'high'
        """
        message_lower = message.lower()
        
        # Определить паттерны для типа
        patterns = self._get_patterns_for_type(agent_type)
        if not patterns:
            return "low"
        
        # Подсчитать совпадения
        matches = self._count_pattern_matches(message_lower, patterns)
        
        # Определить уверенность
        if matches >= 3:
            return "high"
        elif matches >= 2:
            return "medium"
        elif matches >= 1:
            return "low"
        else:
            return "low"
    
    def _count_pattern_matches(self, text: str, patterns: list) -> int:
        """
        Подсчитать количество совпадений паттернов.
        
        Args:
            text: Текст для проверки
            patterns: Список регулярных выражений
            
        Returns:
            Количество совпадений
        """
        count = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                count += 1
        return count
    
    def _get_patterns_for_type(self, agent_type: AgentType) -> list:
        """
        Получить паттерны для типа агента.
        
        Args:
            agent_type: Тип агента
            
        Returns:
            Список паттернов
        """
        pattern_map = {
            AgentType.CODER: self.CODE_PATTERNS,
            AgentType.ARCHITECT: self.ARCHITECTURE_PATTERNS,
            AgentType.DEBUG: self.DEBUG_PATTERNS,
            AgentType.ASK: self.ASK_PATTERNS,
        }
        return pattern_map.get(agent_type, [])
    
    def _get_switch_reason(
        self,
        from_type: AgentType,
        to_type: AgentType,
        message: str
    ) -> str:
        """
        Сформировать причину переключения агента.
        
        Args:
            from_type: Текущий тип
            to_type: Новый тип
            message: Сообщение пользователя
            
        Returns:
            Описание причины переключения
        """
        reason_templates = {
            AgentType.CODER: "Detected coding task in user message",
            AgentType.ARCHITECT: "Detected architecture/design task",
            AgentType.DEBUG: "Detected debugging/investigation task",
            AgentType.ASK: "Detected question/explanation request",
            AgentType.ORCHESTRATOR: "Routing to orchestrator for task coordination",
        }
        
        template = reason_templates.get(to_type, "Task type changed")
        
        # Добавить краткую выдержку из сообщения
        message_preview = message[:50] + "..." if len(message) > 50 else message
        
        return f"{template}: '{message_preview}'"
    
    def get_routing_metadata(
        self,
        message: str,
        current_agent: Optional[Agent] = None
    ) -> Dict[str, Any]:
        """
        Получить метаданные маршрутизации.
        
        Полезно для аналитики и отладки.
        
        Args:
            message: Текст сообщения
            current_agent: Текущий агент
            
        Returns:
            Словарь с метаданными маршрутизации
            
        Пример:
            >>> router = AgentRouterService()
            >>> metadata = router.get_routing_metadata("Write a function")
            >>> metadata['recommended_type']
            'coder'
        """
        recommended_type = self.route_by_message(message, current_agent)
        confidence = self.get_confidence(message, recommended_type)
        
        metadata = {
            "recommended_type": recommended_type.value,
            "confidence": confidence,
            "message_length": len(message),
        }
        
        if current_agent:
            metadata["current_type"] = current_agent.current_type.value
            metadata["switch_count"] = current_agent.switch_count
            
            should_switch, new_type, reason = self.should_switch_agent(
                current_agent, message
            )
            metadata["should_switch"] = should_switch
            if new_type:
                metadata["new_type"] = new_type.value
                metadata["switch_reason"] = reason
        
        return metadata

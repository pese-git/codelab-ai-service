"""
FSM Orchestrator для управления состоянием задачи.

Координирует переходы между состояниями и управляет жизненным циклом.
"""

import logging
from typing import Dict, Optional, Any

from app.domain.entities.fsm_state import (
    FSMState,
    FSMEvent,
    FSMContext,
    FSMTransitionRules
)

logger = logging.getLogger("agent-runtime.fsm_orchestrator")


class FSMOrchestrator:
    """
    Orchestrator для управления FSM состоянием задачи.
    
    Управляет переходами между состояниями, валидирует их,
    и логирует все изменения для отладки и мониторинга.
    
    Атрибуты:
        _contexts: Словарь контекстов FSM по session_id
    
    Пример:
        >>> orchestrator = FSMOrchestrator()
        >>> context = orchestrator.get_or_create_context("session-123")
        >>> await orchestrator.transition("session-123", FSMEvent.RECEIVE_MESSAGE)
    """
    
    def __init__(self):
        """Инициализация FSM Orchestrator"""
        self._contexts: Dict[str, FSMContext] = {}
        logger.info("FSM Orchestrator initialized")
    
    def get_or_create_context(self, session_id: str) -> FSMContext:
        """
        Получить или создать контекст FSM для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            FSMContext для сессии
        """
        if session_id not in self._contexts:
            self._contexts[session_id] = FSMContext(session_id=session_id)
            logger.debug(f"Created new FSM context for session {session_id}")
        
        return self._contexts[session_id]
    
    def get_current_state(self, session_id: str) -> FSMState:
        """
        Получить текущее состояние FSM для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Текущее состояние (IDLE если контекст не существует)
        """
        context = self._contexts.get(session_id)
        if not context:
            return FSMState.IDLE
        
        return context.current_state
    
    async def transition(
        self,
        session_id: str,
        event: FSMEvent,
        metadata: Optional[Dict] = None
    ) -> FSMState:
        """
        Выполнить переход FSM по событию.
        
        Args:
            session_id: ID сессии
            event: Событие для перехода
            metadata: Дополнительные данные для контекста
            
        Returns:
            Новое состояние после перехода
            
        Raises:
            ValueError: Если переход недопустим
            
        Example:
            >>> new_state = await orchestrator.transition(
            ...     "session-123",
            ...     FSMEvent.RECEIVE_MESSAGE
            ... )
            >>> print(new_state)  # FSMState.CLASSIFY
        """
        # Получить или создать контекст
        context = self.get_or_create_context(session_id)
        
        # Запомнить старое состояние для логирования
        old_state = context.current_state
        
        # Валидировать переход
        if not context.can_transition(event):
            allowed_events = FSMTransitionRules.get_allowed_events(old_state)
            error_msg = (
                f"Invalid FSM transition for session {session_id}: "
                f"{old_state.value} -> {event.value}. "
                f"Allowed events: {[e.value for e in allowed_events]}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Выполнить переход
        context.transition(event)
        new_state = context.current_state
        
        # Обновить metadata если предоставлен
        if metadata:
            context.metadata.update(metadata)
        
        # Логирование перехода
        logger.info(
            f"FSM transition for session {session_id}: "
            f"{old_state.value} -> {new_state.value} "
            f"(event: {event.value})"
        )
        
        return new_state
    
    def validate_transition(
        self,
        session_id: str,
        event: FSMEvent
    ) -> bool:
        """
        Валидировать переход без его выполнения.
        
        Args:
            session_id: ID сессии
            event: Событие для проверки
            
        Returns:
            True если переход допустим
        """
        context = self.get_or_create_context(session_id)
        return context.can_transition(event)
    
    def reset(self, session_id: str) -> None:
        """
        Сбросить FSM в начальное состояние.
        
        Args:
            session_id: ID сессии
        """
        context = self._contexts.get(session_id)
        if context:
            old_state = context.current_state
            context.reset()
            logger.info(
                f"FSM reset for session {session_id}: "
                f"{old_state.value} -> {FSMState.IDLE.value}"
            )
        else:
            logger.debug(f"No FSM context to reset for session {session_id}")
    
    def remove_context(self, session_id: str) -> None:
        """
        Удалить контекст FSM для сессии.
        
        Используется при завершении сессии для освобождения памяти.
        
        Args:
            session_id: ID сессии
        """
        if session_id in self._contexts:
            del self._contexts[session_id]
            logger.debug(f"Removed FSM context for session {session_id}")
    
    def get_context_metadata(self, session_id: str) -> Dict:
        """
        Получить metadata контекста.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Словарь с metadata (пустой если контекст не существует)
        """
        context = self._contexts.get(session_id)
        if not context:
            return {}
        
        return context.metadata.copy()
    
    def set_context_metadata(
        self,
        session_id: str,
        key: str,
        value: Any
    ) -> None:
        """
        Установить значение в metadata контекста.
        
        Args:
            session_id: ID сессии
            key: Ключ metadata
            value: Значение
        """
        context = self.get_or_create_context(session_id)
        context.metadata[key] = value
        logger.debug(f"Set FSM metadata for session {session_id}: {key}={value}")
    
    def get_all_contexts(self) -> Dict[str, FSMContext]:
        """
        Получить все активные контексты.
        
        Полезно для мониторинга и отладки.
        
        Returns:
            Словарь {session_id: FSMContext}
        """
        return self._contexts.copy()
    
    def get_contexts_by_state(self, state: FSMState) -> Dict[str, FSMContext]:
        """
        Получить контексты в указанном состоянии.
        
        Args:
            state: Состояние FSM
            
        Returns:
            Словарь {session_id: FSMContext} для сессий в указанном состоянии
        """
        return {
            session_id: context
            for session_id, context in self._contexts.items()
            if context.current_state == state
        }

"""
FSM Orchestrator для управления состоянием задачи.

Координирует переходы между состояниями и управляет жизненным циклом.
UPDATED: Now uses Repository pattern for persistent storage.
"""

import logging
from typing import Dict, Optional, Any, TYPE_CHECKING

from app.domain.entities.fsm_state import (
    FSMState,
    FSMEvent,
    FSMContext,
    FSMTransitionRules
)

if TYPE_CHECKING:
    from app.domain.repositories.fsm_state_repository import FSMStateRepository

logger = logging.getLogger("agent-runtime.fsm_orchestrator")


class FSMOrchestrator:
    """
    Orchestrator для управления FSM состоянием задачи.
    
    UPDATED: Now uses Repository pattern for persistent storage.
    FSM states are stored in database to survive across HTTP requests.
    
    Управляет переходами между состояниями, валидирует их,
    и логирует все изменения для отладки и мониторинга.
    
    Атрибуты:
        _contexts: In-memory cache контекстов FSM по session_id
        _repository: Repository для персистентного хранения (optional)
    
    Пример:
        >>> orchestrator = FSMOrchestrator(repository=fsm_repo)
        >>> context = await orchestrator.get_or_create_context("session-123")
        >>> await orchestrator.transition("session-123", FSMEvent.RECEIVE_MESSAGE)
    """
    
    def __init__(self, repository: Optional["FSMStateRepository"] = None):
        """
        Инициализация FSM Orchestrator.
        
        Args:
            repository: Optional repository для персистентного хранения.
                       Если None, использует только in-memory storage (backward compatibility).
        """
        self._contexts: Dict[str, FSMContext] = {}
        self._repository = repository
        logger.info(
            f"FSM Orchestrator initialized "
            f"(persistence={'enabled' if repository else 'disabled'})"
        )
    
    async def get_or_create_context(self, session_id: str) -> FSMContext:
        """
        Получить или создать контекст FSM для сессии.
        
        Сначала проверяет in-memory cache, затем БД (если repository доступен).
        
        Args:
            session_id: ID сессии
            
        Returns:
            FSMContext для сессии
        """
        # Check in-memory cache first
        if session_id in self._contexts:
            return self._contexts[session_id]
        
        # Try to load from DB if repository available
        if self._repository:
            try:
                db_state = await self._repository.get_state(session_id)
                db_metadata = await self._repository.get_metadata(session_id)
                
                if db_state:
                    # Restore from DB
                    context = FSMContext(
                        session_id=session_id,
                        current_state=db_state,
                        metadata=db_metadata
                    )
                    self._contexts[session_id] = context
                    logger.debug(
                        f"Restored FSM context from DB for session {session_id}: "
                        f"state={db_state.value}"
                    )
                    return context
            except Exception as e:
                logger.warning(
                    f"Failed to load FSM state from DB for session {session_id}: {e}. "
                    f"Creating new context."
                )
        
        # Create new context
        context = FSMContext(session_id=session_id)
        self._contexts[session_id] = context
        logger.debug(f"Created new FSM context for session {session_id}")
        
        # Save to DB if repository available
        if self._repository:
            try:
                await self._repository.save_state(
                    session_id=session_id,
                    current_state=context.current_state,
                    metadata=context.metadata
                )
            except Exception as e:
                logger.warning(f"Failed to save new FSM state to DB: {e}")
        
        return context
    
    async def get_current_state(self, session_id: str) -> FSMState:
        """
        Получить текущее состояние FSM для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Текущее состояние (IDLE если контекст не существует)
        """
        context = await self.get_or_create_context(session_id)
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
        context = await self.get_or_create_context(session_id)
        
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
        
        # Save to DB if repository available
        if self._repository:
            try:
                await self._repository.save_state(
                    session_id=session_id,
                    current_state=new_state,
                    metadata=context.metadata
                )
                logger.debug(f"Saved FSM state to DB for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to save FSM state to DB: {e}")
        
        return new_state
    
    async def validate_transition(
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
        context = await self.get_or_create_context(session_id)
        return context.can_transition(event)
    
    async def reset(self, session_id: str) -> None:
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
            
            # Save to DB if repository available
            if self._repository:
                try:
                    await self._repository.save_state(
                        session_id=session_id,
                        current_state=FSMState.IDLE,
                        metadata=context.metadata
                    )
                except Exception as e:
                    logger.warning(f"Failed to save reset FSM state to DB: {e}")
        else:
            logger.debug(f"No FSM context to reset for session {session_id}")
    
    async def remove_context(self, session_id: str) -> None:
        """
        Удалить контекст FSM для сессии.
        
        Используется при завершении сессии для освобождения памяти и БД.
        
        Args:
            session_id: ID сессии
        """
        if session_id in self._contexts:
            del self._contexts[session_id]
            logger.debug(f"Removed FSM context from memory for session {session_id}")
        
        # Delete from DB if repository available
        if self._repository:
            try:
                await self._repository.delete_state(session_id)
                logger.debug(f"Deleted FSM state from DB for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to delete FSM state from DB: {e}")
    
    async def get_context_metadata(self, session_id: str) -> Dict:
        """
        Получить metadata контекста.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Словарь с metadata (пустой если контекст не существует)
        """
        context = await self.get_or_create_context(session_id)
        return context.metadata.copy()
    
    async def set_context_metadata(
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
        context = await self.get_or_create_context(session_id)
        context.metadata[key] = value
        logger.debug(f"Set FSM metadata for session {session_id}: {key}={value}")
        
        # Save to DB if repository available
        if self._repository:
            try:
                await self._repository.update_metadata(session_id, {key: value})
            except Exception as e:
                logger.warning(f"Failed to save FSM metadata to DB: {e}")
    
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

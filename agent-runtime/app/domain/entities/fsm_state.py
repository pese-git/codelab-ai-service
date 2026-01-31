"""
Доменные сущности для FSM (Finite State Machine) Orchestrator.

Представляют состояния и переходы в жизненном цикле задачи.
"""

from enum import Enum
from typing import Dict, Set, Optional, Any
from pydantic import BaseModel, Field


class FSMState(str, Enum):
    """
    Состояния FSM для управления жизненным циклом задачи.
    
    Определяет все возможные состояния, в которых может находиться
    задача в процессе обработки.
    
    Состояния:
        IDLE: Ожидание новой задачи
        CLASSIFY: Классификация задачи (atomic vs complex)
        PLAN_REQUIRED: Определено, что требуется планирование
        ARCHITECT_PLANNING: Architect создаёт план
        EXECUTION: Исполнение плана или атомарной задачи
        ERROR_HANDLING: Обработка ошибки выполнения
        COMPLETED: Задача завершена успешно
    """
    
    IDLE = "idle"
    CLASSIFY = "classify"
    PLAN_REQUIRED = "plan_required"
    ARCHITECT_PLANNING = "architect_planning"
    EXECUTION = "execution"
    ERROR_HANDLING = "error_handling"
    COMPLETED = "completed"


class FSMEvent(str, Enum):
    """
    События, которые вызывают переходы между состояниями.
    
    События представляют действия или результаты, которые
    триггерят изменение состояния FSM.
    """
    
    # События из IDLE
    RECEIVE_MESSAGE = "receive_message"
    
    # События из CLASSIFY
    IS_ATOMIC_TRUE = "is_atomic_true"
    IS_ATOMIC_FALSE = "is_atomic_false"
    CLASSIFY_ERROR = "classify_error"
    
    # События из PLAN_REQUIRED
    ROUTE_TO_ARCHITECT = "route_to_architect"
    
    # События из ARCHITECT_PLANNING
    PLAN_CREATED = "plan_created"
    PLANNING_FAILED = "planning_failed"
    
    # События из EXECUTION
    ALL_SUBTASKS_DONE = "all_subtasks_done"
    SUBTASK_FAILED = "subtask_failed"
    
    # События из ERROR_HANDLING
    REQUIRES_REPLANNING = "requires_replanning"
    RETRY_SUBTASK = "retry_subtask"
    PLAN_CANCELLED = "plan_cancelled"
    
    # События из COMPLETED
    RESET = "reset"


class FSMTransitionRules:
    """
    Правила переходов между состояниями FSM.
    
    Определяет допустимые переходы и валидирует их.
    Это критически важно для детерминированного поведения системы.
    """
    
    # Матрица переходов: {from_state: {event: to_state}}
    TRANSITIONS: Dict[FSMState, Dict[FSMEvent, FSMState]] = {
        FSMState.IDLE: {
            FSMEvent.RECEIVE_MESSAGE: FSMState.CLASSIFY,
        },
        FSMState.CLASSIFY: {
            FSMEvent.IS_ATOMIC_TRUE: FSMState.EXECUTION,
            FSMEvent.IS_ATOMIC_FALSE: FSMState.PLAN_REQUIRED,
            FSMEvent.CLASSIFY_ERROR: FSMState.IDLE,
        },
        FSMState.PLAN_REQUIRED: {
            FSMEvent.ROUTE_TO_ARCHITECT: FSMState.ARCHITECT_PLANNING,
        },
        FSMState.ARCHITECT_PLANNING: {
            FSMEvent.PLAN_CREATED: FSMState.EXECUTION,
            FSMEvent.PLANNING_FAILED: FSMState.ERROR_HANDLING,
        },
        FSMState.EXECUTION: {
            FSMEvent.ALL_SUBTASKS_DONE: FSMState.COMPLETED,
            FSMEvent.SUBTASK_FAILED: FSMState.ERROR_HANDLING,
        },
        FSMState.ERROR_HANDLING: {
            FSMEvent.REQUIRES_REPLANNING: FSMState.ARCHITECT_PLANNING,
            FSMEvent.RETRY_SUBTASK: FSMState.EXECUTION,
            FSMEvent.PLAN_CANCELLED: FSMState.COMPLETED,
        },
        FSMState.COMPLETED: {
            FSMEvent.RESET: FSMState.IDLE,
        },
    }
    
    @classmethod
    def is_valid_transition(
        cls,
        from_state: FSMState,
        event: FSMEvent
    ) -> bool:
        """
        Проверить, допустим ли переход.
        
        Args:
            from_state: Текущее состояние
            event: Событие для перехода
            
        Returns:
            True если переход допустим
            
        Example:
            >>> FSMTransitionRules.is_valid_transition(
            ...     FSMState.IDLE,
            ...     FSMEvent.RECEIVE_MESSAGE
            ... )
            True
        """
        if from_state not in cls.TRANSITIONS:
            return False
        
        return event in cls.TRANSITIONS[from_state]
    
    @classmethod
    def get_next_state(
        cls,
        from_state: FSMState,
        event: FSMEvent
    ) -> Optional[FSMState]:
        """
        Получить следующее состояние для перехода.
        
        Args:
            from_state: Текущее состояние
            event: Событие
            
        Returns:
            Следующее состояние или None если переход недопустим
            
        Example:
            >>> next_state = FSMTransitionRules.get_next_state(
            ...     FSMState.IDLE,
            ...     FSMEvent.RECEIVE_MESSAGE
            ... )
            >>> print(next_state)  # FSMState.CLASSIFY
        """
        if not cls.is_valid_transition(from_state, event):
            return None
        
        return cls.TRANSITIONS[from_state][event]
    
    @classmethod
    def get_allowed_events(cls, from_state: FSMState) -> Set[FSMEvent]:
        """
        Получить список допустимых событий для состояния.
        
        Args:
            from_state: Текущее состояние
            
        Returns:
            Множество допустимых событий
            
        Example:
            >>> events = FSMTransitionRules.get_allowed_events(FSMState.IDLE)
            >>> print(events)  # {FSMEvent.RECEIVE_MESSAGE}
        """
        if from_state not in cls.TRANSITIONS:
            return set()
        
        return set(cls.TRANSITIONS[from_state].keys())


class FSMContext(BaseModel):
    """
    Контекст FSM для отдельной сессии.
    
    Хранит текущее состояние и метаданные для управления
    жизненным циклом задачи в рамках одной сессии.
    
    Атрибуты:
        session_id: ID сессии
        current_state: Текущее состояние FSM
        metadata: Дополнительные данные (plan_id, error_count, etc.)
    """
    
    session_id: str = Field(
        ...,
        description="ID сессии"
    )
    
    current_state: FSMState = Field(
        default=FSMState.IDLE,
        description="Текущее состояние FSM"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные контекста"
    )
    
    def transition(self, event: FSMEvent) -> bool:
        """
        Выполнить переход по событию.
        
        Args:
            event: Событие для перехода
            
        Returns:
            True если переход выполнен, False если недопустим
            
        Raises:
            ValueError: Если переход недопустим
        """
        next_state = FSMTransitionRules.get_next_state(self.current_state, event)
        
        if next_state is None:
            raise ValueError(
                f"Invalid transition: {self.current_state.value} "
                f"-> {event.value}. "
                f"Allowed events: {[e.value for e in FSMTransitionRules.get_allowed_events(self.current_state)]}"
            )
        
        self.current_state = next_state
        return True
    
    def reset(self) -> None:
        """Сбросить FSM в начальное состояние"""
        self.current_state = FSMState.IDLE
        self.metadata.clear()
    
    def is_in_state(self, state: FSMState) -> bool:
        """Проверить, находится ли FSM в указанном состоянии"""
        return self.current_state == state
    
    def can_transition(self, event: FSMEvent) -> bool:
        """Проверить, возможен ли переход по событию"""
        return FSMTransitionRules.is_valid_transition(self.current_state, event)

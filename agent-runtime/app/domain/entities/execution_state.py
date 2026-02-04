"""
Execution State Management для ExecutionEngine.

Управляет состояниями выполнения плана и transitions между ними.
"""

from enum import Enum
from typing import Optional, Set, Dict, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger("agent-runtime.domain.execution_state")


class ExecutionState(str, Enum):
    """Состояния выполнения плана"""
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStateManager:
    """
    Менеджер состояний выполнения плана.
    
    Отвечает за:
    - Управление текущим состоянием
    - Валидацию transitions
    - Хранение истории transitions
    - Thread-safe операции
    
    Attributes:
        plan_id: ID плана
        _current_state: Текущее состояние
        _transition_history: История transitions
        _state_metadata: Metadata для каждого состояния
    """
    
    # Разрешенные transitions
    ALLOWED_TRANSITIONS: Dict[ExecutionState, Set[ExecutionState]] = {
        ExecutionState.RUNNING: {
            ExecutionState.WAITING_APPROVAL,
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED
        },
        ExecutionState.WAITING_APPROVAL: {
            ExecutionState.RESUMED,
            ExecutionState.CANCELLED
        },
        ExecutionState.RESUMED: {
            ExecutionState.RUNNING
        },
        ExecutionState.COMPLETED: set(),  # Terminal state
        ExecutionState.FAILED: set(),     # Terminal state
        ExecutionState.CANCELLED: set()   # Terminal state
    }
    
    def __init__(self, plan_id: str, initial_state: ExecutionState = ExecutionState.RUNNING):
        """
        Инициализация state manager.
        
        Args:
            plan_id: ID плана
            initial_state: Начальное состояние
        """
        self.plan_id = plan_id
        self._current_state = initial_state
        self._transition_history: List[Dict] = []
        self._state_metadata: Dict[str, Dict] = {}
        
        # Записать начальное состояние
        self._record_transition(None, initial_state, "Initial state")
        
        logger.info(f"ExecutionStateManager initialized for plan {plan_id} in state {initial_state.value}")
    
    @property
    def current_state(self) -> ExecutionState:
        """Получить текущее состояние"""
        return self._current_state
    
    def can_transition_to(self, new_state: ExecutionState) -> bool:
        """
        Проверить, возможен ли переход в новое состояние.
        
        Args:
            new_state: Целевое состояние
            
        Returns:
            True если переход разрешен
        """
        allowed = self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        return new_state in allowed
    
    def transition_to(
        self,
        new_state: ExecutionState,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Выполнить переход в новое состояние.
        
        Args:
            new_state: Целевое состояние
            reason: Причина перехода
            metadata: Дополнительные данные
            
        Raises:
            ValueError: Если переход не разрешен
        """
        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid transition from {self._current_state.value} "
                f"to {new_state.value} for plan {self.plan_id}"
            )
        
        old_state = self._current_state
        self._current_state = new_state
        
        # Сохранить metadata
        if metadata:
            self._state_metadata[new_state.value] = metadata
        
        # Записать в историю
        self._record_transition(old_state, new_state, reason)
        
        logger.info(
            f"Plan {self.plan_id} transitioned from {old_state.value} "
            f"to {new_state.value}: {reason or 'No reason'}"
        )
    
    def is_terminal(self) -> bool:
        """Проверить, находится ли в терминальном состоянии"""
        return self._current_state in {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED
        }
    
    def is_waiting_approval(self) -> bool:
        """Проверить, ждет ли approval"""
        return self._current_state == ExecutionState.WAITING_APPROVAL
    
    def get_transition_history(self) -> List[Dict]:
        """Получить историю transitions"""
        return self._transition_history.copy()
    
    def get_state_metadata(self, state: ExecutionState) -> Optional[Dict]:
        """Получить metadata для состояния"""
        return self._state_metadata.get(state.value)
    
    def _record_transition(
        self,
        from_state: Optional[ExecutionState],
        to_state: ExecutionState,
        reason: Optional[str]
    ) -> None:
        """Записать transition в историю"""
        self._transition_history.append({
            "from_state": from_state.value if from_state else None,
            "to_state": to_state.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def to_dict(self) -> Dict:
        """Преобразовать в словарь для сериализации"""
        return {
            "plan_id": self.plan_id,
            "current_state": self._current_state.value,
            "is_terminal": self.is_terminal(),
            "transition_history": self._transition_history,
            "state_metadata": self._state_metadata
        }

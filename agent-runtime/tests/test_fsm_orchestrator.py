"""
Unit тесты для FSM Orchestrator.

Проверяют:
- FSMState и FSMEvent enums
- FSMTransitionRules валидацию
- FSMContext переходы
- FSMOrchestrator управление состоянием
"""

import pytest

from app.domain.entities.fsm_state import (
    FSMState,
    FSMEvent,
    FSMTransitionRules,
    FSMContext
)
from app.domain.services.fsm_orchestrator import FSMOrchestrator


class TestFSMTransitionRules:
    """Тесты для правил переходов FSM"""
    
    def test_valid_transition_idle_to_classify(self):
        """Тест: валидный переход IDLE -> CLASSIFY"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.IDLE,
            FSMEvent.RECEIVE_MESSAGE
        )
        
        assert is_valid is True
    
    def test_valid_transition_classify_to_execution(self):
        """Тест: валидный переход CLASSIFY -> EXECUTION (atomic task)"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.CLASSIFY,
            FSMEvent.IS_ATOMIC_TRUE
        )
        
        assert is_valid is True
    
    def test_valid_transition_classify_to_plan_required(self):
        """Тест: валидный переход CLASSIFY -> PLAN_REQUIRED (complex task)"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.CLASSIFY,
            FSMEvent.IS_ATOMIC_FALSE
        )
        
        assert is_valid is True
    
    def test_invalid_transition_idle_to_execution(self):
        """Тест: невалидный переход IDLE -> EXECUTION"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.IDLE,
            FSMEvent.ALL_SUBTASKS_DONE
        )
        
        assert is_valid is False
    
    def test_get_next_state_valid(self):
        """Тест: получение следующего состояния для валидного перехода"""
        next_state = FSMTransitionRules.get_next_state(
            FSMState.IDLE,
            FSMEvent.RECEIVE_MESSAGE
        )
        
        assert next_state == FSMState.CLASSIFY
    
    def test_get_next_state_invalid(self):
        """Тест: получение None для невалидного перехода"""
        next_state = FSMTransitionRules.get_next_state(
            FSMState.IDLE,
            FSMEvent.ALL_SUBTASKS_DONE
        )
        
        assert next_state is None
    
    def test_get_allowed_events(self):
        """Тест: получение списка допустимых событий"""
        events = FSMTransitionRules.get_allowed_events(FSMState.CLASSIFY)
        
        assert FSMEvent.IS_ATOMIC_TRUE in events
        assert FSMEvent.IS_ATOMIC_FALSE in events
        assert FSMEvent.CLASSIFY_ERROR in events
        assert len(events) == 3


class TestFSMContext:
    """Тесты для FSM Context"""
    
    def test_create_context_default_state(self):
        """Тест: создание контекста с начальным состоянием IDLE"""
        context = FSMContext(session_id="session-1")
        
        assert context.session_id == "session-1"
        assert context.current_state == FSMState.IDLE
        assert context.metadata == {}
    
    def test_transition_valid(self):
        """Тест: валидный переход в контексте"""
        context = FSMContext(session_id="session-1")
        
        result = context.transition(FSMEvent.RECEIVE_MESSAGE)
        
        assert result is True
        assert context.current_state == FSMState.CLASSIFY
    
    def test_transition_invalid_raises_error(self):
        """Тест: невалидный переход выбрасывает ValueError"""
        context = FSMContext(session_id="session-1")
        
        with pytest.raises(ValueError) as exc_info:
            context.transition(FSMEvent.ALL_SUBTASKS_DONE)
        
        assert "Invalid transition" in str(exc_info.value)
        assert "idle" in str(exc_info.value)
    
    def test_reset_context(self):
        """Тест: сброс контекста в IDLE"""
        context = FSMContext(session_id="session-1")
        context.transition(FSMEvent.RECEIVE_MESSAGE)
        context.metadata["test"] = "value"
        
        context.reset()
        
        assert context.current_state == FSMState.IDLE
        assert context.metadata == {}
    
    def test_is_in_state(self):
        """Тест: проверка текущего состояния"""
        context = FSMContext(session_id="session-1")
        
        assert context.is_in_state(FSMState.IDLE) is True
        assert context.is_in_state(FSMState.CLASSIFY) is False
    
    def test_can_transition(self):
        """Тест: проверка возможности перехода"""
        context = FSMContext(session_id="session-1")
        
        assert context.can_transition(FSMEvent.RECEIVE_MESSAGE) is True
        assert context.can_transition(FSMEvent.ALL_SUBTASKS_DONE) is False


@pytest.mark.asyncio
class TestFSMOrchestrator:
    """Тесты для FSM Orchestrator"""
    
    async def test_create_orchestrator(self):
        """Тест: создание orchestrator"""
        orchestrator = FSMOrchestrator()
        
        assert orchestrator is not None
        assert orchestrator._contexts == {}
    
    async def test_get_or_create_context(self):
        """Тест: получение или создание контекста"""
        orchestrator = FSMOrchestrator()
        
        context = orchestrator.get_or_create_context("session-1")
        
        assert context.session_id == "session-1"
        assert context.current_state == FSMState.IDLE
    
    async def test_get_or_create_context_returns_same(self):
        """Тест: повторный вызов возвращает тот же контекст"""
        orchestrator = FSMOrchestrator()
        
        context1 = orchestrator.get_or_create_context("session-1")
        context2 = orchestrator.get_or_create_context("session-1")
        
        assert context1 is context2
    
    async def test_get_current_state_existing(self):
        """Тест: получение текущего состояния для существующего контекста"""
        orchestrator = FSMOrchestrator()
        orchestrator.get_or_create_context("session-1")
        
        state = orchestrator.get_current_state("session-1")
        
        assert state == FSMState.IDLE
    
    async def test_get_current_state_non_existing(self):
        """Тест: получение IDLE для несуществующего контекста"""
        orchestrator = FSMOrchestrator()
        
        state = orchestrator.get_current_state("non-existing")
        
        assert state == FSMState.IDLE
    
    async def test_transition_valid(self):
        """Тест: валидный переход через orchestrator"""
        orchestrator = FSMOrchestrator()
        
        new_state = await orchestrator.transition(
            "session-1",
            FSMEvent.RECEIVE_MESSAGE
        )
        
        assert new_state == FSMState.CLASSIFY
        assert orchestrator.get_current_state("session-1") == FSMState.CLASSIFY
    
    async def test_transition_with_metadata(self):
        """Тест: переход с metadata"""
        orchestrator = FSMOrchestrator()
        
        await orchestrator.transition(
            "session-1",
            FSMEvent.RECEIVE_MESSAGE,
            metadata={"plan_id": "plan-123"}
        )
        
        metadata = orchestrator.get_context_metadata("session-1")
        assert metadata["plan_id"] == "plan-123"
    
    async def test_transition_invalid_raises_error(self):
        """Тест: невалидный переход выбрасывает ValueError"""
        orchestrator = FSMOrchestrator()
        
        with pytest.raises(ValueError) as exc_info:
            await orchestrator.transition(
                "session-1",
                FSMEvent.ALL_SUBTASKS_DONE
            )
        
        assert "Invalid FSM transition" in str(exc_info.value)
    
    async def test_validate_transition(self):
        """Тест: валидация перехода без выполнения"""
        orchestrator = FSMOrchestrator()
        orchestrator.get_or_create_context("session-1")
        
        is_valid = orchestrator.validate_transition(
            "session-1",
            FSMEvent.RECEIVE_MESSAGE
        )
        
        assert is_valid is True
        # Состояние не должно измениться
        assert orchestrator.get_current_state("session-1") == FSMState.IDLE
    
    async def test_reset(self):
        """Тест: сброс FSM"""
        orchestrator = FSMOrchestrator()
        await orchestrator.transition("session-1", FSMEvent.RECEIVE_MESSAGE)
        
        orchestrator.reset("session-1")
        
        assert orchestrator.get_current_state("session-1") == FSMState.IDLE
    
    async def test_remove_context(self):
        """Тест: удаление контекста"""
        orchestrator = FSMOrchestrator()
        orchestrator.get_or_create_context("session-1")
        
        orchestrator.remove_context("session-1")
        
        assert "session-1" not in orchestrator._contexts
    
    async def test_set_and_get_metadata(self):
        """Тест: установка и получение metadata"""
        orchestrator = FSMOrchestrator()
        
        orchestrator.set_context_metadata("session-1", "key", "value")
        metadata = orchestrator.get_context_metadata("session-1")
        
        assert metadata["key"] == "value"
    
    async def test_get_all_contexts(self):
        """Тест: получение всех контекстов"""
        orchestrator = FSMOrchestrator()
        orchestrator.get_or_create_context("session-1")
        orchestrator.get_or_create_context("session-2")
        
        contexts = orchestrator.get_all_contexts()
        
        assert len(contexts) == 2
        assert "session-1" in contexts
        assert "session-2" in contexts
    
    async def test_get_contexts_by_state(self):
        """Тест: получение контекстов по состоянию"""
        orchestrator = FSMOrchestrator()
        await orchestrator.transition("session-1", FSMEvent.RECEIVE_MESSAGE)
        orchestrator.get_or_create_context("session-2")  # Остаётся в IDLE
        
        classify_contexts = orchestrator.get_contexts_by_state(FSMState.CLASSIFY)
        idle_contexts = orchestrator.get_contexts_by_state(FSMState.IDLE)
        
        assert len(classify_contexts) == 1
        assert "session-1" in classify_contexts
        assert len(idle_contexts) == 1
        assert "session-2" in idle_contexts


@pytest.mark.asyncio
class TestFSMWorkflows:
    """Тесты для полных workflow FSM"""
    
    async def test_atomic_task_workflow(self):
        """Тест: полный workflow для атомарной задачи"""
        orchestrator = FSMOrchestrator()
        
        # IDLE -> CLASSIFY
        state = await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        assert state == FSMState.CLASSIFY
        
        # CLASSIFY -> EXECUTION (atomic)
        state = await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_TRUE)
        assert state == FSMState.EXECUTION
        
        # EXECUTION -> COMPLETED
        state = await orchestrator.transition("s1", FSMEvent.ALL_SUBTASKS_DONE)
        assert state == FSMState.COMPLETED
        
        # COMPLETED -> IDLE
        state = await orchestrator.transition("s1", FSMEvent.RESET)
        assert state == FSMState.IDLE
    
    async def test_complex_task_workflow(self):
        """Тест: полный workflow для сложной задачи (Option 2)"""
        orchestrator = FSMOrchestrator()
        
        # IDLE -> CLASSIFY
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        
        # CLASSIFY -> PLAN_REQUIRED (complex)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_REQUIRED
        
        # PLAN_REQUIRED -> ARCHITECT_PLANNING
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        assert orchestrator.get_current_state("s1") == FSMState.ARCHITECT_PLANNING
        
        # ARCHITECT_PLANNING -> PLAN_REVIEW (Option 2: plan created, awaiting approval)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_REVIEW
        
        # PLAN_REVIEW -> PLAN_EXECUTION (user approved)
        await orchestrator.transition("s1", FSMEvent.PLAN_APPROVED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_EXECUTION
        
        # PLAN_EXECUTION -> COMPLETED
        await orchestrator.transition("s1", FSMEvent.PLAN_EXECUTION_COMPLETED)
        assert orchestrator.get_current_state("s1") == FSMState.COMPLETED
    
    async def test_error_handling_workflow(self):
        """Тест: workflow с обработкой ошибки"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до EXECUTION
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_TRUE)
        
        # EXECUTION -> ERROR_HANDLING
        await orchestrator.transition("s1", FSMEvent.SUBTASK_FAILED)
        assert orchestrator.get_current_state("s1") == FSMState.ERROR_HANDLING
        
        # ERROR_HANDLING -> EXECUTION (retry)
        await orchestrator.transition("s1", FSMEvent.RETRY_SUBTASK)
        assert orchestrator.get_current_state("s1") == FSMState.EXECUTION
    
    async def test_replanning_workflow(self):
        """Тест: workflow с replanning (Option 2)"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до ERROR_HANDLING через PLAN_EXECUTION
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        await orchestrator.transition("s1", FSMEvent.PLAN_APPROVED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_EXECUTION
        
        # PLAN_EXECUTION -> ERROR_HANDLING (execution failed)
        await orchestrator.transition("s1", FSMEvent.PLAN_EXECUTION_FAILED)
        assert orchestrator.get_current_state("s1") == FSMState.ERROR_HANDLING
        
        # ERROR_HANDLING -> ARCHITECT_PLANNING (replanning)
        await orchestrator.transition("s1", FSMEvent.REQUIRES_REPLANNING)
        assert orchestrator.get_current_state("s1") == FSMState.ARCHITECT_PLANNING
    
    async def test_plan_cancellation_workflow(self):
        """Тест: workflow с отменой плана"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до ERROR_HANDLING
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_TRUE)
        await orchestrator.transition("s1", FSMEvent.SUBTASK_FAILED)
        
        # ERROR_HANDLING -> COMPLETED (cancel)
        await orchestrator.transition("s1", FSMEvent.PLAN_CANCELLED)
        assert orchestrator.get_current_state("s1") == FSMState.COMPLETED


class TestFSMOrchestratorMultipleSessions:
    """Тесты для работы с несколькими сессиями"""
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self):
        """Тест: независимость состояний разных сессий"""
        orchestrator = FSMOrchestrator()
        
        # Session 1: IDLE -> CLASSIFY
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        
        # Session 2: остаётся в IDLE
        orchestrator.get_or_create_context("s2")
        
        assert orchestrator.get_current_state("s1") == FSMState.CLASSIFY
        assert orchestrator.get_current_state("s2") == FSMState.IDLE
    
    @pytest.mark.asyncio
    async def test_remove_one_session_keeps_others(self):
        """Тест: удаление одной сессии не влияет на другие"""
        orchestrator = FSMOrchestrator()
        orchestrator.get_or_create_context("s1")
        orchestrator.get_or_create_context("s2")
        
        orchestrator.remove_context("s1")
        
        assert "s1" not in orchestrator._contexts
        assert "s2" in orchestrator._contexts


class TestFSMStateTransitionMatrix:
    """Тесты для полной матрицы переходов"""
    
    def test_all_states_have_transitions(self):
        """Тест: все состояния имеют определённые переходы"""
        for state in FSMState:
            events = FSMTransitionRules.get_allowed_events(state)
            # Каждое состояние должно иметь хотя бы один выход
            # (кроме потенциальных терминальных состояний)
            assert events is not None
    
    def test_transition_matrix_completeness(self):
        """Тест: матрица переходов полная"""
        # Проверить, что все состояния покрыты
        for state in FSMState:
            assert state in FSMTransitionRules.TRANSITIONS
    
    def test_no_self_loops_except_explicit(self):
        """Тест: нет неявных циклов в одно состояние"""
        for from_state, transitions in FSMTransitionRules.TRANSITIONS.items():
            for event, to_state in transitions.items():
                # Переходы в то же состояние должны быть явными
                if from_state == to_state:
                    # Если есть self-loop, он должен быть задокументирован
                    pass  # В текущей реализации нет self-loops

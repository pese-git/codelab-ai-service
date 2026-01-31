"""
Unit тесты для новых FSM states Option 2.

Проверяют:
- PLAN_REVIEW state transitions
- PLAN_EXECUTION state transitions
- New FSM events (PLAN_APPROVED, PLAN_REJECTED, etc.)
- Option 2 specific workflows
"""

import pytest

from app.domain.entities.fsm_state import (
    FSMState,
    FSMEvent,
    FSMTransitionRules,
    FSMContext
)
from app.domain.services.fsm_orchestrator import FSMOrchestrator


class TestPlanReviewStateTransitions:
    """Тесты для PLAN_REVIEW state transitions"""
    
    def test_plan_review_to_plan_execution_on_approval(self):
        """Тест: PLAN_REVIEW → PLAN_EXECUTION при одобрении"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.PLAN_REVIEW,
            FSMEvent.PLAN_APPROVED
        )
        assert is_valid is True
        
        next_state = FSMTransitionRules.get_next_state(
            FSMState.PLAN_REVIEW,
            FSMEvent.PLAN_APPROVED
        )
        assert next_state == FSMState.PLAN_EXECUTION
    
    def test_plan_review_to_idle_on_rejection(self):
        """Тест: PLAN_REVIEW → IDLE при отклонении"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.PLAN_REVIEW,
            FSMEvent.PLAN_REJECTED
        )
        assert is_valid is True
        
        next_state = FSMTransitionRules.get_next_state(
            FSMState.PLAN_REVIEW,
            FSMEvent.PLAN_REJECTED
        )
        assert next_state == FSMState.IDLE
    
    def test_plan_review_to_architect_on_modification(self):
        """Тест: PLAN_REVIEW → ARCHITECT_PLANNING при запросе изменений"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.PLAN_REVIEW,
            FSMEvent.PLAN_MODIFICATION_REQUESTED
        )
        assert is_valid is True
        
        next_state = FSMTransitionRules.get_next_state(
            FSMState.PLAN_REVIEW,
            FSMEvent.PLAN_MODIFICATION_REQUESTED
        )
        assert next_state == FSMState.ARCHITECT_PLANNING
    
    def test_plan_review_allowed_events(self):
        """Тест: PLAN_REVIEW имеет 3 допустимых события"""
        events = FSMTransitionRules.get_allowed_events(FSMState.PLAN_REVIEW)
        
        assert len(events) == 3
        assert FSMEvent.PLAN_APPROVED in events
        assert FSMEvent.PLAN_REJECTED in events
        assert FSMEvent.PLAN_MODIFICATION_REQUESTED in events


class TestPlanExecutionStateTransitions:
    """Тесты для PLAN_EXECUTION state transitions"""
    
    def test_plan_execution_to_completed_on_success(self):
        """Тест: PLAN_EXECUTION → COMPLETED при успехе"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.PLAN_EXECUTION,
            FSMEvent.PLAN_EXECUTION_COMPLETED
        )
        assert is_valid is True
        
        next_state = FSMTransitionRules.get_next_state(
            FSMState.PLAN_EXECUTION,
            FSMEvent.PLAN_EXECUTION_COMPLETED
        )
        assert next_state == FSMState.COMPLETED
    
    def test_plan_execution_to_error_on_failure(self):
        """Тест: PLAN_EXECUTION → ERROR_HANDLING при ошибке"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.PLAN_EXECUTION,
            FSMEvent.PLAN_EXECUTION_FAILED
        )
        assert is_valid is True
        
        next_state = FSMTransitionRules.get_next_state(
            FSMState.PLAN_EXECUTION,
            FSMEvent.PLAN_EXECUTION_FAILED
        )
        assert next_state == FSMState.ERROR_HANDLING
    
    def test_plan_execution_allowed_events(self):
        """Тест: PLAN_EXECUTION имеет 2 допустимых события"""
        events = FSMTransitionRules.get_allowed_events(FSMState.PLAN_EXECUTION)
        
        assert len(events) == 2
        assert FSMEvent.PLAN_EXECUTION_COMPLETED in events
        assert FSMEvent.PLAN_EXECUTION_FAILED in events


class TestArchitectPlanningToReview:
    """Тесты для перехода ARCHITECT_PLANNING → PLAN_REVIEW"""
    
    def test_architect_planning_to_plan_review(self):
        """Тест: ARCHITECT_PLANNING → PLAN_REVIEW при создании плана"""
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.ARCHITECT_PLANNING,
            FSMEvent.PLAN_CREATED
        )
        assert is_valid is True
        
        next_state = FSMTransitionRules.get_next_state(
            FSMState.ARCHITECT_PLANNING,
            FSMEvent.PLAN_CREATED
        )
        assert next_state == FSMState.PLAN_REVIEW


@pytest.mark.asyncio
class TestOption2CompleteWorkflow:
    """Тесты для полного Option 2 workflow"""
    
    async def test_successful_plan_execution_workflow(self):
        """Тест: успешный полный workflow Option 2"""
        orchestrator = FSMOrchestrator()
        
        # 1. IDLE → CLASSIFY
        state = await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        assert state == FSMState.CLASSIFY
        
        # 2. CLASSIFY → PLAN_REQUIRED (complex task)
        state = await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        assert state == FSMState.PLAN_REQUIRED
        
        # 3. PLAN_REQUIRED → ARCHITECT_PLANNING
        state = await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        assert state == FSMState.ARCHITECT_PLANNING
        
        # 4. ARCHITECT_PLANNING → PLAN_REVIEW (plan created)
        state = await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        assert state == FSMState.PLAN_REVIEW
        
        # 5. PLAN_REVIEW → PLAN_EXECUTION (user approved)
        state = await orchestrator.transition("s1", FSMEvent.PLAN_APPROVED)
        assert state == FSMState.PLAN_EXECUTION
        
        # 6. PLAN_EXECUTION → COMPLETED (execution successful)
        state = await orchestrator.transition("s1", FSMEvent.PLAN_EXECUTION_COMPLETED)
        assert state == FSMState.COMPLETED
        
        # 7. COMPLETED → IDLE (reset)
        state = await orchestrator.transition("s1", FSMEvent.RESET)
        assert state == FSMState.IDLE
    
    async def test_plan_rejection_workflow(self):
        """Тест: workflow с отклонением плана"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до PLAN_REVIEW
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_REVIEW
        
        # User rejects plan → IDLE
        state = await orchestrator.transition("s1", FSMEvent.PLAN_REJECTED)
        assert state == FSMState.IDLE
    
    async def test_plan_modification_workflow(self):
        """Тест: workflow с запросом изменений плана"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до PLAN_REVIEW
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_REVIEW
        
        # User requests modifications → back to ARCHITECT_PLANNING
        state = await orchestrator.transition("s1", FSMEvent.PLAN_MODIFICATION_REQUESTED)
        assert state == FSMState.ARCHITECT_PLANNING
        
        # Architect creates new plan → PLAN_REVIEW again
        state = await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        assert state == FSMState.PLAN_REVIEW
    
    async def test_plan_execution_failure_workflow(self):
        """Тест: workflow с ошибкой выполнения плана"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до PLAN_EXECUTION
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        await orchestrator.transition("s1", FSMEvent.PLAN_APPROVED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_EXECUTION
        
        # Execution fails → ERROR_HANDLING
        state = await orchestrator.transition("s1", FSMEvent.PLAN_EXECUTION_FAILED)
        assert state == FSMState.ERROR_HANDLING
        
        # Can replan from ERROR_HANDLING
        state = await orchestrator.transition("s1", FSMEvent.REQUIRES_REPLANNING)
        assert state == FSMState.ARCHITECT_PLANNING


@pytest.mark.asyncio
class TestOption2StateMetadata:
    """Тесты для metadata в Option 2 states"""
    
    async def test_plan_review_metadata(self):
        """Тест: metadata сохраняется в PLAN_REVIEW"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до PLAN_REVIEW с metadata
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition(
            "s1",
            FSMEvent.PLAN_CREATED,
            metadata={"plan_id": "plan-123", "subtasks_count": 5}
        )
        
        metadata = orchestrator.get_context_metadata("s1")
        assert metadata["plan_id"] == "plan-123"
        assert metadata["subtasks_count"] == 5
    
    async def test_plan_execution_metadata(self):
        """Тест: metadata обновляется при выполнении"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до PLAN_EXECUTION
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED, metadata={"plan_id": "plan-123"})
        await orchestrator.transition(
            "s1",
            FSMEvent.PLAN_APPROVED,
            metadata={"approved_by": "user", "approved_at": "2026-01-31T12:00:00Z"}
        )
        
        metadata = orchestrator.get_context_metadata("s1")
        assert metadata["plan_id"] == "plan-123"
        assert metadata["approved_by"] == "user"
        assert metadata["approved_at"] == "2026-01-31T12:00:00Z"


class TestInvalidOption2Transitions:
    """Тесты для невалидных переходов в Option 2"""
    
    def test_cannot_execute_without_approval(self):
        """Тест: нельзя перейти к PLAN_EXECUTION без approval"""
        # PLAN_REVIEW не может перейти к PLAN_EXECUTION через другие события
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.PLAN_REVIEW,
            FSMEvent.PLAN_CREATED  # Wrong event
        )
        assert is_valid is False
    
    def test_cannot_skip_plan_review(self):
        """Тест: нельзя пропустить PLAN_REVIEW"""
        # ARCHITECT_PLANNING не может перейти напрямую к PLAN_EXECUTION
        is_valid = FSMTransitionRules.is_valid_transition(
            FSMState.ARCHITECT_PLANNING,
            FSMEvent.PLAN_APPROVED  # Wrong state
        )
        assert is_valid is False
    
    def test_plan_execution_only_from_plan_review(self):
        """Тест: PLAN_EXECUTION доступен только из PLAN_REVIEW"""
        # Проверить, что только PLAN_REVIEW может перейти к PLAN_EXECUTION
        states_to_plan_execution = []
        for state in FSMState:
            events = FSMTransitionRules.get_allowed_events(state)
            for event in events:
                next_state = FSMTransitionRules.get_next_state(state, event)
                if next_state == FSMState.PLAN_EXECUTION:
                    states_to_plan_execution.append(state)
        
        assert states_to_plan_execution == [FSMState.PLAN_REVIEW]


@pytest.mark.asyncio
class TestOption2EdgeCases:
    """Тесты для edge cases в Option 2"""
    
    async def test_multiple_plan_modifications(self):
        """Тест: множественные запросы на изменение плана"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до PLAN_REVIEW
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        
        # First modification request
        await orchestrator.transition("s1", FSMEvent.PLAN_MODIFICATION_REQUESTED)
        assert orchestrator.get_current_state("s1") == FSMState.ARCHITECT_PLANNING
        
        # Create new plan
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_REVIEW
        
        # Second modification request
        await orchestrator.transition("s1", FSMEvent.PLAN_MODIFICATION_REQUESTED)
        assert orchestrator.get_current_state("s1") == FSMState.ARCHITECT_PLANNING
    
    async def test_plan_execution_failure_then_replan(self):
        """Тест: ошибка выполнения → replanning → успех"""
        orchestrator = FSMOrchestrator()
        
        # Дойти до PLAN_EXECUTION
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_FALSE)
        await orchestrator.transition("s1", FSMEvent.ROUTE_TO_ARCHITECT)
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        await orchestrator.transition("s1", FSMEvent.PLAN_APPROVED)
        
        # Execution fails
        await orchestrator.transition("s1", FSMEvent.PLAN_EXECUTION_FAILED)
        assert orchestrator.get_current_state("s1") == FSMState.ERROR_HANDLING
        
        # Replan
        await orchestrator.transition("s1", FSMEvent.REQUIRES_REPLANNING)
        assert orchestrator.get_current_state("s1") == FSMState.ARCHITECT_PLANNING
        
        # New plan created and approved
        await orchestrator.transition("s1", FSMEvent.PLAN_CREATED)
        await orchestrator.transition("s1", FSMEvent.PLAN_APPROVED)
        assert orchestrator.get_current_state("s1") == FSMState.PLAN_EXECUTION
        
        # Success this time
        await orchestrator.transition("s1", FSMEvent.PLAN_EXECUTION_COMPLETED)
        assert orchestrator.get_current_state("s1") == FSMState.COMPLETED


@pytest.mark.asyncio
class TestOption2VsOption1Compatibility:
    """Тесты для совместимости Option 2 с Option 1 flow"""
    
    async def test_atomic_task_still_works(self):
        """Тест: атомарные задачи работают как раньше (Option 1)"""
        orchestrator = FSMOrchestrator()
        
        # Atomic task flow не изменился
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_TRUE)
        assert orchestrator.get_current_state("s1") == FSMState.EXECUTION
        
        await orchestrator.transition("s1", FSMEvent.ALL_SUBTASKS_DONE)
        assert orchestrator.get_current_state("s1") == FSMState.COMPLETED
    
    async def test_error_handling_still_works(self):
        """Тест: error handling работает для обоих вариантов"""
        orchestrator = FSMOrchestrator()
        
        # Atomic task with error
        await orchestrator.transition("s1", FSMEvent.RECEIVE_MESSAGE)
        await orchestrator.transition("s1", FSMEvent.IS_ATOMIC_TRUE)
        await orchestrator.transition("s1", FSMEvent.SUBTASK_FAILED)
        assert orchestrator.get_current_state("s1") == FSMState.ERROR_HANDLING
        
        # Can retry
        await orchestrator.transition("s1", FSMEvent.RETRY_SUBTASK)
        assert orchestrator.get_current_state("s1") == FSMState.EXECUTION

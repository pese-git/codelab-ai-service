"""
Integration tests для Plan Approval flow.

Тестирует полный workflow от создания плана до его выполнения
с user approval.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.domain.services.plan_approval_handler import PlanApprovalHandler, PlanApprovalDecision
from app.domain.services.approval_management import ApprovalManager
from app.domain.session_context.services.conversation_management_service import ConversationManagementService
from app.domain.services.fsm_orchestrator import FSMOrchestrator
from app.domain.entities.fsm_state import FSMState, FSMEvent
from app.domain.execution_context.entities.execution_plan import ExecutionPlan as Plan
from app.domain.execution_context.entities.subtask import Subtask
from app.domain.execution_context.value_objects import PlanStatus, SubtaskStatus
from app.agents.base_agent import AgentType
from app.domain.entities.approval import PendingApprovalState
from app.application.coordinators.execution_coordinator import ExecutionCoordinator
from app.domain.services.execution_engine import ExecutionResult
from app.models.schemas import StreamChunk


class TestPlanApprovalIntegration:
    """Integration tests для Plan Approval flow"""
    
    @pytest_asyncio.fixture
    async def mock_approval_repository(self):
        """Mock approval repository"""
        repo = AsyncMock()
        repo.save_pending = AsyncMock()
        repo.get_pending = AsyncMock()
        repo.update_status = AsyncMock()
        repo.delete_pending = AsyncMock()
        return repo
    
    @pytest_asyncio.fixture
    async def mock_session_repository(self):
        """Mock session repository"""
        repo = AsyncMock()
        repo.save = AsyncMock()
        repo.find_by_id = AsyncMock()
        return repo
    
    @pytest_asyncio.fixture
    async def mock_plan_repository(self):
        """Mock plan repository"""
        repo = AsyncMock()
        repo.save = AsyncMock()
        repo.find_by_id = AsyncMock()
        return repo
    
    @pytest_asyncio.fixture
    async def approval_manager(self, mock_approval_repository):
        """Create ApprovalManager with mock repository"""
        from app.domain.entities.approval import ApprovalPolicy
        
        return ApprovalManager(
            approval_repository=mock_approval_repository,
            approval_policy=ApprovalPolicy.default()
        )
    
    @pytest_asyncio.fixture
    async def session_service(self, mock_session_repository):
        """Create ConversationManagementService with mock repository"""
        return ConversationManagementService(
            conversation_repository=mock_session_repository,
            event_publisher=AsyncMock()
        )
    
    @pytest_asyncio.fixture
    async def fsm_orchestrator(self):
        """Create FSM Orchestrator"""
        return FSMOrchestrator()
    
    @pytest_asyncio.fixture
    async def execution_coordinator(self, mock_plan_repository):
        """Create ExecutionCoordinator with mocks"""
        mock_engine = AsyncMock()
        
        return ExecutionCoordinator(
            execution_engine=mock_engine,
            plan_repository=mock_plan_repository
        )
    
    @pytest_asyncio.fixture
    async def mock_stream_handler(self):
        """Mock stream handler"""
        return AsyncMock()
    
    @pytest_asyncio.fixture
    async def plan_approval_handler(
        self,
        approval_manager,
        session_service,
        fsm_orchestrator,
        execution_coordinator,
        mock_plan_repository,
        mock_stream_handler
    ):
        """Create PlanApprovalHandler with all dependencies"""
        return PlanApprovalHandler(
            approval_manager=approval_manager,
            session_service=session_service,
            fsm_orchestrator=fsm_orchestrator,
            execution_coordinator=execution_coordinator,
            plan_repository=mock_plan_repository,
            stream_handler=mock_stream_handler
        )
    
    @pytest.mark.asyncio
    async def test_plan_approval_approve_decision(
        self,
        plan_approval_handler,
        approval_manager,
        fsm_orchestrator,
        execution_coordinator,
        mock_plan_repository
    ):
        """Test plan approval with APPROVE decision"""
        session_id = "test-session-1"
        plan_id = "test-plan-1"
        approval_request_id = f"plan-approval-{plan_id}"
        
        # Setup FSM в PLAN_REVIEW state
        await fsm_orchestrator.get_or_create_context(session_id)
        await fsm_orchestrator.transition(session_id, FSMEvent.RECEIVE_MESSAGE)
        await fsm_orchestrator.transition(session_id, FSMEvent.IS_ATOMIC_FALSE)
        await fsm_orchestrator.transition(session_id, FSMEvent.ROUTE_TO_ARCHITECT)
        await fsm_orchestrator.transition(session_id, FSMEvent.PLAN_CREATED)
        
        # Verify в PLAN_REVIEW
        assert await fsm_orchestrator.get_current_state(session_id) == FSMState.PLAN_REVIEW
        
        # Mock pending approval
        pending_approval = PendingApprovalState(
            request_id=approval_request_id,
            request_type="plan",
            subject="Test plan",
            session_id=session_id,
            details={
                "plan_id": plan_id,
                "goal": "Test plan goal",
                "subtasks_count": 2
            },
            reason="Test approval"
        )
        approval_manager._repository.get_pending = AsyncMock(return_value=pending_approval)
        
        # Mock plan summary
        plan_summary = {
            "plan_id": plan_id,
            "goal": "Test plan",
            "subtasks_count": 2,
            "total_estimated_time": "10 min"
        }
        execution_coordinator.get_plan_summary = AsyncMock(return_value=plan_summary)
        
        # Mock execution result as async generator
        async def mock_execute_plan(*args, **kwargs):
            yield StreamChunk(
                type="status",
                content="Executing subtask 1..."
            )
            yield StreamChunk(
                type="execution_completed",
                content="Execution completed",
                metadata={
                    "plan_id": plan_id,
                    "status": "completed",
                    "completed_subtasks": 2,
                    "failed_subtasks": 0,
                    "total_subtasks": 2,
                    "duration_seconds": 10.5
                }
            )
        
        execution_coordinator.execute_plan = mock_execute_plan
        
        # Execute approval with APPROVE decision
        chunks = []
        async for chunk in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="approve"
        ):
            chunks.append(chunk)
        
        # Verify chunks
        assert len(chunks) > 0
        
        # Verify status chunk
        status_chunks = [c for c in chunks if c.type == "status"]
        assert len(status_chunks) >= 1
        assert "approved" in status_chunks[0].content.lower()
        
        # Verify execution_completed chunk
        completed_chunks = [c for c in chunks if c.type == "execution_completed"]
        assert len(completed_chunks) == 1
        
        # Verify approval manager called (может быть вызван дважды - в approve() и в handle())
        assert approval_manager._repository.get_pending.call_count >= 1
        approval_manager._repository.update_status.assert_called_once()
        
        # Verify FSM transition
        assert await fsm_orchestrator.get_current_state(session_id) == FSMState.COMPLETED
        
        # Verify execution was called (chunks were generated, so it was called)
        # Note: Can't use assert_called_once() on regular function
    
    @pytest.mark.asyncio
    async def test_plan_approval_reject_decision(
        self,
        plan_approval_handler,
        approval_manager,
        fsm_orchestrator
    ):
        """Test plan approval with REJECT decision"""
        session_id = "test-session-2"
        plan_id = "test-plan-2"
        approval_request_id = f"plan-approval-{plan_id}"
        
        # Setup FSM в PLAN_REVIEW state
        await fsm_orchestrator.get_or_create_context(session_id)
        await fsm_orchestrator.transition(session_id, FSMEvent.RECEIVE_MESSAGE)
        await fsm_orchestrator.transition(session_id, FSMEvent.IS_ATOMIC_FALSE)
        await fsm_orchestrator.transition(session_id, FSMEvent.ROUTE_TO_ARCHITECT)
        await fsm_orchestrator.transition(session_id, FSMEvent.PLAN_CREATED)
        
        # Mock pending approval
        pending_approval = PendingApprovalState(
            request_id=approval_request_id,
            request_type="plan",
            subject="Test plan",
            session_id=session_id,
            details={"plan_id": plan_id},
            reason="Test approval"
        )
        approval_manager._repository.get_pending = AsyncMock(return_value=pending_approval)
        
        # Execute approval with REJECT decision
        chunks = []
        async for chunk in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="reject",
            feedback="Plan is too complex"
        ):
            chunks.append(chunk)
        
        # Verify chunks
        assert len(chunks) > 0
        
        # Verify rejection chunk
        rejected_chunks = [c for c in chunks if c.type == "plan_rejected"]
        assert len(rejected_chunks) == 1
        
        # Verify approval manager update_status called for rejection
        approval_manager._repository.update_status.assert_called_once()
        
        # Verify FSM transition to IDLE
        assert await fsm_orchestrator.get_current_state(session_id) == FSMState.IDLE
    
    @pytest.mark.asyncio
    async def test_plan_approval_modify_decision(
        self,
        plan_approval_handler,
        approval_manager,
        fsm_orchestrator
    ):
        """Test plan approval with MODIFY decision"""
        session_id = "test-session-3"
        plan_id = "test-plan-3"
        approval_request_id = f"plan-approval-{plan_id}"
        
        # Setup FSM в PLAN_REVIEW state
        await fsm_orchestrator.get_or_create_context(session_id)
        await fsm_orchestrator.transition(session_id, FSMEvent.RECEIVE_MESSAGE)
        await fsm_orchestrator.transition(session_id, FSMEvent.IS_ATOMIC_FALSE)
        await fsm_orchestrator.transition(session_id, FSMEvent.ROUTE_TO_ARCHITECT)
        await fsm_orchestrator.transition(session_id, FSMEvent.PLAN_CREATED)
        
        # Mock pending approval
        pending_approval = PendingApprovalState(
            request_id=approval_request_id,
            request_type="plan",
            subject="Test plan",
            session_id=session_id,
            details={"plan_id": plan_id},
            reason="Test approval"
        )
        approval_manager._repository.get_pending = AsyncMock(return_value=pending_approval)
        
        # Execute approval with MODIFY decision
        chunks = []
        async for chunk in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="modify",
            feedback="Please add error handling"
        ):
            chunks.append(chunk)
        
        # Verify chunks
        assert len(chunks) > 0
        
        # Verify modification chunk
        modify_chunks = [c for c in chunks if c.type == "plan_modification_requested"]
        assert len(modify_chunks) == 1
        
        # Verify FSM transition to ARCHITECT_PLANNING
        assert await fsm_orchestrator.get_current_state(session_id) == FSMState.ARCHITECT_PLANNING
    
    @pytest.mark.asyncio
    async def test_plan_approval_invalid_decision(
        self,
        plan_approval_handler,
        approval_manager
    ):
        """Test plan approval with invalid decision"""
        session_id = "test-session-4"
        approval_request_id = "plan-approval-test"
        
        # Mock pending approval
        pending_approval = PendingApprovalState(
            request_id=approval_request_id,
            request_type="plan",
            subject="Test plan",
            session_id=session_id,
            details={"plan_id": "test-plan"},
            reason="Test"
        )
        approval_manager._repository.get_pending = AsyncMock(return_value=pending_approval)
        
        # Execute with invalid decision
        chunks = []
        async for chunk in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="invalid_decision"
        ):
            chunks.append(chunk)
        
        # Verify error chunk
        assert len(chunks) == 1
        assert chunks[0].type == "error"
        assert "Invalid plan approval decision" in chunks[0].error
    
    @pytest.mark.asyncio
    async def test_plan_approval_not_found(
        self,
        plan_approval_handler,
        approval_manager
    ):
        """Test plan approval when approval request not found"""
        session_id = "test-session-5"
        approval_request_id = "nonexistent-approval"
        
        # Mock no pending approval
        approval_manager._repository.get_pending = AsyncMock(return_value=None)
        
        # Execute approval
        chunks = []
        async for chunk in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="approve"
        ):
            chunks.append(chunk)
        
        # Verify error chunk
        assert len(chunks) == 1
        assert chunks[0].type == "error"
        assert "No pending approval found" in chunks[0].error
    
    @pytest.mark.asyncio
    async def test_plan_approval_missing_plan_id(
        self,
        plan_approval_handler,
        approval_manager
    ):
        """Test plan approval when plan_id missing in details"""
        session_id = "test-session-6"
        approval_request_id = "plan-approval-test"
        
        # Mock pending approval without plan_id
        pending_approval = PendingApprovalState(
            request_id=approval_request_id,
            request_type="plan",
            subject="Test plan",
            session_id=session_id,
            details={},  # No plan_id
            reason="Test"
        )
        approval_manager._repository.get_pending = AsyncMock(return_value=pending_approval)
        
        # Execute approval
        chunks = []
        async for chunk in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="approve"
        ):
            chunks.append(chunk)
        
        # Verify error chunk
        assert len(chunks) == 1
        assert chunks[0].type == "error"
        assert "Plan ID not found" in chunks[0].error
    
    @pytest.mark.asyncio
    async def test_fsm_transitions_on_approval(
        self,
        plan_approval_handler,
        approval_manager,
        fsm_orchestrator,
        execution_coordinator,
        mock_plan_repository
    ):
        """Test FSM transitions during approval flow"""
        session_id = "test-session-7"
        plan_id = "test-plan-7"
        approval_request_id = f"plan-approval-{plan_id}"
        
        # Setup FSM в PLAN_REVIEW
        await fsm_orchestrator.get_or_create_context(session_id)
        await fsm_orchestrator.transition(session_id, FSMEvent.RECEIVE_MESSAGE)
        await fsm_orchestrator.transition(session_id, FSMEvent.IS_ATOMIC_FALSE)
        await fsm_orchestrator.transition(session_id, FSMEvent.ROUTE_TO_ARCHITECT)
        await fsm_orchestrator.transition(session_id, FSMEvent.PLAN_CREATED)
        
        initial_state = await fsm_orchestrator.get_current_state(session_id)
        assert initial_state == FSMState.PLAN_REVIEW
        
        # Mock pending approval
        pending_approval = PendingApprovalState(
            request_id=approval_request_id,
            request_type="plan",
            subject="Test plan",
            session_id=session_id,
            details={"plan_id": plan_id},
            reason="Test"
        )
        approval_manager._repository.get_pending = AsyncMock(return_value=pending_approval)
        
        # Mock execution
        execution_coordinator.get_plan_summary = AsyncMock(return_value={
            "plan_id": plan_id,
            "goal": "Test",
            "subtasks_count": 1,
            "total_estimated_time": "5 min"
        })
        
        # Mock execution as async generator
        async def mock_execute_plan(*args, **kwargs):
            yield StreamChunk(
                type="status",
                content="Executing..."
            )
            yield StreamChunk(
                type="execution_completed",
                content="Completed",
                metadata={
                    "plan_id": plan_id,
                    "status": "completed",
                    "completed_subtasks": 1,
                    "failed_subtasks": 0,
                    "total_subtasks": 1,
                    "duration_seconds": 5.0
                }
            )
        
        execution_coordinator.execute_plan = mock_execute_plan
        
        # Execute approval
        chunks = list([c async for c in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="approve"
        )])
        
        # Verify FSM transitions
        # PLAN_REVIEW → PLAN_APPROVED → PLAN_EXECUTION → COMPLETED
        final_state = await fsm_orchestrator.get_current_state(session_id)
        assert final_state == FSMState.COMPLETED
    
    @pytest.mark.asyncio
    async def test_approval_events_published(
        self,
        plan_approval_handler,
        approval_manager,
        fsm_orchestrator
    ):
        """Test that approval events are published"""
        session_id = "test-session-8"
        plan_id = "test-plan-8"
        approval_request_id = f"plan-approval-{plan_id}"
        
        # Setup FSM
        await fsm_orchestrator.get_or_create_context(session_id)
        await fsm_orchestrator.transition(session_id, FSMEvent.RECEIVE_MESSAGE)
        await fsm_orchestrator.transition(session_id, FSMEvent.IS_ATOMIC_FALSE)
        await fsm_orchestrator.transition(session_id, FSMEvent.ROUTE_TO_ARCHITECT)
        await fsm_orchestrator.transition(session_id, FSMEvent.PLAN_CREATED)
        
        # Mock pending approval
        pending_approval = PendingApprovalState(
            request_id=approval_request_id,
            request_type="plan",
            subject="Test plan",
            session_id=session_id,
            details={"plan_id": plan_id},
            reason="Test"
        )
        approval_manager._repository.get_pending = AsyncMock(return_value=pending_approval)
        
        # Execute rejection
        chunks = list([c async for c in plan_approval_handler.handle(
            session_id=session_id,
            approval_request_id=approval_request_id,
            decision="reject",
            feedback="Not needed"
        )])
        
        # Verify approval manager reject called
        approval_manager._repository.update_status.assert_called_once()
        
        # Verify chunks generated
        assert len(chunks) > 0


class TestPlanApprovalDecisionEnum:
    """Tests для PlanApprovalDecision enum"""
    
    def test_valid_decisions(self):
        """Test valid decision values"""
        assert PlanApprovalDecision.APPROVE.value == "approve"
        assert PlanApprovalDecision.REJECT.value == "reject"
        assert PlanApprovalDecision.MODIFY.value == "modify"
    
    def test_decision_from_string(self):
        """Test creating decision from string"""
        assert PlanApprovalDecision("approve") == PlanApprovalDecision.APPROVE
        assert PlanApprovalDecision("reject") == PlanApprovalDecision.REJECT
        assert PlanApprovalDecision("modify") == PlanApprovalDecision.MODIFY
    
    def test_invalid_decision(self):
        """Test invalid decision raises ValueError"""
        with pytest.raises(ValueError):
            PlanApprovalDecision("invalid")

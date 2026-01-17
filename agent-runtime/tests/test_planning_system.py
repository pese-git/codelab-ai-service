"""
Tests for the planning system (ExecutionPlan, Subtask, SessionManager plan methods).
"""
import pytest
from datetime import datetime, timezone

from app.models.schemas import ExecutionPlan, Subtask, SubtaskStatus
from app.services.session_manager_async import AsyncSessionManager


class TestPlanningModels:
    """Test planning data models"""
    
    def test_subtask_creation(self):
        """Test creating a subtask"""
        subtask = Subtask(
            id="subtask_1",
            description="Add dependency to pubspec.yaml",
            agent="coder",
            estimated_time="2 min"
        )
        
        assert subtask.id == "subtask_1"
        assert subtask.description == "Add dependency to pubspec.yaml"
        assert subtask.agent == "coder"
        assert subtask.estimated_time == "2 min"
        assert subtask.status == SubtaskStatus.PENDING
        assert subtask.result is None
        assert subtask.error is None
        assert subtask.dependencies == []
    
    def test_subtask_with_dependencies(self):
        """Test creating a subtask with dependencies"""
        subtask = Subtask(
            id="subtask_2",
            description="Create providers",
            agent="coder",
            estimated_time="5 min",
            dependencies=["subtask_1"]
        )
        
        assert subtask.dependencies == ["subtask_1"]
    
    def test_execution_plan_creation(self):
        """Test creating an execution plan"""
        subtasks = [
            Subtask(
                id="subtask_1",
                description="Add dependency",
                agent="coder",
                estimated_time="2 min"
            ),
            Subtask(
                id="subtask_2",
                description="Create providers",
                agent="coder",
                estimated_time="5 min",
                dependencies=["subtask_1"]
            )
        ]
        
        plan = ExecutionPlan(
            plan_id="plan_123",
            session_id="session_456",
            original_task="Migrate to Riverpod",
            subtasks=subtasks
        )
        
        assert plan.plan_id == "plan_123"
        assert plan.session_id == "session_456"
        assert plan.original_task == "Migrate to Riverpod"
        assert len(plan.subtasks) == 2
        assert plan.current_subtask_index == 0
        assert plan.is_complete is False
    
    def test_subtask_status_transitions(self):
        """Test subtask status changes"""
        subtask = Subtask(
            id="subtask_1",
            description="Test task",
            agent="coder"
        )
        
        # Initial status
        assert subtask.status == SubtaskStatus.PENDING
        
        # Mark as in progress
        subtask.status = SubtaskStatus.IN_PROGRESS
        assert subtask.status == SubtaskStatus.IN_PROGRESS
        
        # Mark as completed
        subtask.status = SubtaskStatus.COMPLETED
        subtask.result = "Task completed successfully"
        assert subtask.status == SubtaskStatus.COMPLETED
        assert subtask.result == "Task completed successfully"
        
        # Test failed status
        failed_subtask = Subtask(
            id="subtask_2",
            description="Failed task",
            agent="coder"
        )
        failed_subtask.status = SubtaskStatus.FAILED
        failed_subtask.error = "Something went wrong"
        assert failed_subtask.status == SubtaskStatus.FAILED
        assert failed_subtask.error == "Something went wrong"


@pytest.mark.asyncio
class TestSessionManagerPlanning:
    """Test SessionManager plan management methods"""
    
    async def test_set_and_get_plan(self):
        """Test storing and retrieving a plan"""
        session_mgr = AsyncSessionManager()
        await session_mgr.initialize()
        
        session_id = "test_session_plan"
        
        # Create a plan
        subtasks = [
            Subtask(
                id="subtask_1",
                description="First task",
                agent="coder"
            )
        ]
        
        plan = ExecutionPlan(
            plan_id="plan_test",
            session_id=session_id,
            original_task="Test task",
            subtasks=subtasks
        )
        
        # Store plan
        session_mgr.set_plan(session_id, plan)
        
        # Retrieve plan
        retrieved_plan = session_mgr.get_plan(session_id)
        
        assert retrieved_plan is not None
        assert retrieved_plan.plan_id == "plan_test"
        assert retrieved_plan.session_id == session_id
        assert len(retrieved_plan.subtasks) == 1
        
        await session_mgr.shutdown()
    
    async def test_has_plan(self):
        """Test checking if session has a plan"""
        session_mgr = AsyncSessionManager()
        await session_mgr.initialize()
        
        session_id = "test_session_has_plan"
        
        # Initially no plan
        assert session_mgr.has_plan(session_id) is False
        
        # Add a plan
        plan = ExecutionPlan(
            plan_id="plan_test",
            session_id=session_id,
            original_task="Test",
            subtasks=[
                Subtask(id="st1", description="Task", agent="coder")
            ]
        )
        session_mgr.set_plan(session_id, plan)
        
        # Now has plan
        assert session_mgr.has_plan(session_id) is True
        
        await session_mgr.shutdown()
    
    async def test_mark_subtask_complete(self):
        """Test marking a subtask as complete"""
        session_mgr = AsyncSessionManager()
        await session_mgr.initialize()
        
        session_id = "test_session_complete"
        
        # Create plan with subtasks
        subtasks = [
            Subtask(id="subtask_1", description="Task 1", agent="coder"),
            Subtask(id="subtask_2", description="Task 2", agent="coder")
        ]
        
        plan = ExecutionPlan(
            plan_id="plan_test",
            session_id=session_id,
            original_task="Test",
            subtasks=subtasks
        )
        session_mgr.set_plan(session_id, plan)
        
        # Mark first subtask as complete
        result = session_mgr.mark_subtask_complete(
            session_id,
            "subtask_1",
            "Task completed successfully"
        )
        
        assert result is True
        
        # Verify status changed
        updated_plan = session_mgr.get_plan(session_id)
        assert updated_plan.subtasks[0].status == SubtaskStatus.COMPLETED
        assert updated_plan.subtasks[0].result == "Task completed successfully"
        assert updated_plan.subtasks[1].status == SubtaskStatus.PENDING
        
        await session_mgr.shutdown()
    
    async def test_mark_subtask_failed(self):
        """Test marking a subtask as failed"""
        session_mgr = AsyncSessionManager()
        await session_mgr.initialize()
        
        session_id = "test_session_failed"
        
        # Create plan
        plan = ExecutionPlan(
            plan_id="plan_test",
            session_id=session_id,
            original_task="Test",
            subtasks=[
                Subtask(id="subtask_1", description="Task", agent="coder")
            ]
        )
        session_mgr.set_plan(session_id, plan)
        
        # Mark as failed
        result = session_mgr.mark_subtask_failed(
            session_id,
            "subtask_1",
            "Task failed due to error"
        )
        
        assert result is True
        
        # Verify status
        updated_plan = session_mgr.get_plan(session_id)
        assert updated_plan.subtasks[0].status == SubtaskStatus.FAILED
        assert updated_plan.subtasks[0].error == "Task failed due to error"
        
        await session_mgr.shutdown()
    
    async def test_get_next_subtask(self):
        """Test getting the next pending subtask"""
        session_mgr = AsyncSessionManager()
        await session_mgr.initialize()
        
        session_id = "test_session_next"
        
        # Create plan with multiple subtasks
        subtasks = [
            Subtask(id="subtask_1", description="Task 1", agent="coder"),
            Subtask(id="subtask_2", description="Task 2", agent="coder"),
            Subtask(id="subtask_3", description="Task 3", agent="coder")
        ]
        
        plan = ExecutionPlan(
            plan_id="plan_test",
            session_id=session_id,
            original_task="Test",
            subtasks=subtasks
        )
        session_mgr.set_plan(session_id, plan)
        
        # Get first subtask
        next_subtask = session_mgr.get_next_subtask(session_id)
        assert next_subtask is not None
        assert next_subtask.id == "subtask_1"
        assert next_subtask.status == SubtaskStatus.IN_PROGRESS
        
        # Complete first subtask
        session_mgr.mark_subtask_complete(session_id, "subtask_1")
        
        # Get second subtask
        next_subtask = session_mgr.get_next_subtask(session_id)
        assert next_subtask is not None
        assert next_subtask.id == "subtask_2"
        
        await session_mgr.shutdown()
    
    async def test_get_next_subtask_with_dependencies(self):
        """Test getting next subtask respects dependencies"""
        session_mgr = AsyncSessionManager()
        await session_mgr.initialize()
        
        session_id = "test_session_deps"
        
        # Create plan with dependencies
        subtasks = [
            Subtask(id="subtask_1", description="Task 1", agent="coder"),
            Subtask(
                id="subtask_2",
                description="Task 2",
                agent="coder",
                dependencies=["subtask_1"]  # Depends on subtask_1
            )
        ]
        
        plan = ExecutionPlan(
            plan_id="plan_test",
            session_id=session_id,
            original_task="Test",
            subtasks=subtasks
        )
        session_mgr.set_plan(session_id, plan)
        
        # Get first subtask
        next_subtask = session_mgr.get_next_subtask(session_id)
        assert next_subtask.id == "subtask_1"
        
        # Try to get next before completing first - should skip subtask_2
        # because its dependency is not met
        session_mgr.mark_subtask_failed(session_id, "subtask_1", "Failed")
        next_subtask = session_mgr.get_next_subtask(session_id)
        # Should be None because subtask_2 depends on subtask_1 which failed
        assert next_subtask is None or next_subtask.id != "subtask_2"
        
        await session_mgr.shutdown()
    
    async def test_clear_plan(self):
        """Test clearing a plan"""
        session_mgr = AsyncSessionManager()
        await session_mgr.initialize()
        
        session_id = "test_session_clear"
        
        # Create and store plan
        plan = ExecutionPlan(
            plan_id="plan_test",
            session_id=session_id,
            original_task="Test",
            subtasks=[
                Subtask(id="subtask_1", description="Task", agent="coder")
            ]
        )
        session_mgr.set_plan(session_id, plan)
        
        # Verify plan exists
        assert session_mgr.has_plan(session_id) is True
        
        # Clear plan
        session_mgr.clear_plan(session_id)
        
        # Verify plan is gone
        assert session_mgr.has_plan(session_id) is False
        assert session_mgr.get_plan(session_id) is None
        
        await session_mgr.shutdown()


class TestCreatePlanTool:
    """Test create_plan tool"""
    
    def test_create_plan_tool_execution(self):
        """Test create_plan tool returns correct marker"""
        from app.services.tool_registry import create_plan_tool
        import json
        
        subtasks = [
            {
                "id": "subtask_1",
                "description": "Add dependency",
                "agent": "coder",
                "estimated_time": "2 min"
            },
            {
                "id": "subtask_2",
                "description": "Create providers",
                "agent": "coder",
                "estimated_time": "5 min",
                "dependencies": ["subtask_1"]
            }
        ]
        
        result = create_plan_tool(subtasks)
        
        # Should return marker with JSON data
        assert result.startswith("__CREATE_PLAN__|")
        
        # Extract and parse JSON
        json_data = result.split("__CREATE_PLAN__|")[1]
        parsed = json.loads(json_data)
        
        assert len(parsed) == 2
        assert parsed[0]["id"] == "subtask_1"
        assert parsed[1]["dependencies"] == ["subtask_1"]

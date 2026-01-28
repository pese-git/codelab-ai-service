"""
Integration tests for ApprovalManager with real database.

Tests cover:
- Full workflow with SQLAlchemy database
- Transaction management
- Concurrent access scenarios
- Database constraints and indexes
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.domain.services.approval_management import ApprovalManager
from app.domain.entities.approval import (
    ApprovalPolicy,
    ApprovalPolicyRule,
    ApprovalRequestType
)
from app.infrastructure.persistence.repositories.approval_repository_impl import ApprovalRepositoryImpl
from app.infrastructure.persistence.models import Base, PendingApproval


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine (in-memory SQLite)"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create test database session"""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def approval_repository(test_session):
    """Create approval repository with test session"""
    return ApprovalRepositoryImpl(test_session)


@pytest_asyncio.fixture
async def approval_manager(approval_repository):
    """Create approval manager with test repository"""
    policy = ApprovalPolicy(
        enabled=True,
        rules=[
            ApprovalPolicyRule(
                request_type=ApprovalRequestType.TOOL,
                subject_pattern="write_file|execute_command",
                requires_approval=True,
                reason="Dangerous operation"
            ),
        ],
        default_requires_approval=False
    )
    return ApprovalManager(
        approval_repository=approval_repository,
        approval_policy=policy
    )


@pytest.mark.asyncio
class TestApprovalManagerIntegration:
    """Integration tests with real database"""
    
    async def test_full_approval_workflow(self, approval_manager, test_session):
        """Test complete approval workflow: create -> approve -> verify"""
        # 1. Add pending approval
        await approval_manager.add_pending(
            request_id="req-integration-1",
            request_type="tool",
            subject="write_file",
            session_id="session-test",
            details={"arguments": {"path": "test.py", "content": "print('hello')"}},
            reason="File modification"
        )
        await test_session.commit()
        
        # 2. Verify saved to database
        result = await test_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == "req-integration-1")
        )
        db_approval = result.scalar_one_or_none()
        assert db_approval is not None
        assert db_approval.request_type == "tool"
        assert db_approval.subject == "write_file"
        assert db_approval.status == "pending"
        
        # 3. Get pending approval
        approval = await approval_manager.get_pending("req-integration-1")
        assert approval is not None
        assert approval.request_id == "req-integration-1"
        
        # 4. Approve it
        await approval_manager.approve("req-integration-1")
        await test_session.commit()
        
        # 5. Verify status updated in database
        result = await test_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == "req-integration-1")
        )
        db_approval = result.scalar_one_or_none()
        assert db_approval.status == "approved"
        
        # 6. Verify no longer in pending
        approval = await approval_manager.get_pending("req-integration-1")
        assert approval is None  # Not pending anymore
    
    async def test_rejection_workflow(self, approval_manager, test_session):
        """Test rejection workflow"""
        # Add pending
        await approval_manager.add_pending(
            request_id="req-reject-1",
            request_type="tool",
            subject="execute_command",
            session_id="session-test",
            details={"arguments": {"command": "rm -rf /"}},
            reason="Dangerous command"
        )
        await test_session.commit()
        
        # Reject with reason
        await approval_manager.reject("req-reject-1", reason="Too dangerous")
        await test_session.commit()
        
        # Verify status in database
        result = await test_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == "req-reject-1")
        )
        db_approval = result.scalar_one_or_none()
        assert db_approval.status == "rejected"
        assert db_approval.decision_reason == "Too dangerous"
    
    async def test_multiple_sessions_isolation(self, approval_manager, test_session):
        """Test that approvals are properly isolated by session"""
        # Add approvals for different sessions
        await approval_manager.add_pending(
            request_id="req-s1-1",
            request_type="tool",
            subject="write_file",
            session_id="session-1",
            details={},
            reason="Test"
        )
        await approval_manager.add_pending(
            request_id="req-s1-2",
            request_type="tool",
            subject="write_file",
            session_id="session-1",
            details={},
            reason="Test"
        )
        await approval_manager.add_pending(
            request_id="req-s2-1",
            request_type="tool",
            subject="write_file",
            session_id="session-2",
            details={},
            reason="Test"
        )
        await test_session.commit()
        
        # Get approvals for each session
        session1_approvals = await approval_manager.get_all_pending("session-1")
        session2_approvals = await approval_manager.get_all_pending("session-2")
        
        assert len(session1_approvals) == 2
        assert len(session2_approvals) == 1
        assert all(a.session_id == "session-1" for a in session1_approvals)
        assert all(a.session_id == "session-2" for a in session2_approvals)
    
    async def test_filter_by_request_type(self, approval_manager, test_session):
        """Test filtering approvals by request type"""
        # Add different types
        await approval_manager.add_pending(
            request_id="req-tool-1",
            request_type="tool",
            subject="write_file",
            session_id="session-test",
            details={},
            reason="Test"
        )
        await approval_manager.add_pending(
            request_id="req-plan-1",
            request_type="plan",
            subject="Migration plan",
            session_id="session-test",
            details={},
            reason="Test"
        )
        await test_session.commit()
        
        # Get all
        all_approvals = await approval_manager.get_all_pending("session-test")
        assert len(all_approvals) == 2
        
        # Get only tools
        tool_approvals = await approval_manager.get_all_pending("session-test", request_type="tool")
        assert len(tool_approvals) == 1
        assert tool_approvals[0].request_type == "tool"
        
        # Get only plans
        plan_approvals = await approval_manager.get_all_pending("session-test", request_type="plan")
        assert len(plan_approvals) == 1
        assert plan_approvals[0].request_type == "plan"
    
    async def test_database_constraints(self, approval_repository, test_session):
        """Test database constraints (unique request_id)"""
        # Add first approval
        await approval_repository.save_pending(
            request_id="req-unique",
            request_type="tool",
            subject="write_file",
            session_id="session-test",
            details={},
            reason="Test"
        )
        await test_session.commit()
        
        # Try to add duplicate (should not raise, just log warning)
        await approval_repository.save_pending(
            request_id="req-unique",
            request_type="tool",
            subject="write_file",
            session_id="session-test",
            details={},
            reason="Test"
        )
        await test_session.commit()
        
        # Verify only one exists
        result = await test_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == "req-unique")
        )
        approvals = result.scalars().all()
        assert len(approvals) == 1
    
    async def test_transaction_rollback(self, approval_manager, test_session):
        """Test that rollback properly reverts changes"""
        # Add approval
        await approval_manager.add_pending(
            request_id="req-rollback",
            request_type="tool",
            subject="write_file",
            session_id="session-test",
            details={},
            reason="Test"
        )
        
        # Rollback instead of commit
        await test_session.rollback()
        
        # Verify not in database
        result = await test_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == "req-rollback")
        )
        db_approval = result.scalar_one_or_none()
        assert db_approval is None
    
    async def test_legacy_fields_compatibility(self, approval_repository, test_session):
        """Test that legacy fields are properly populated for tool approvals"""
        # Add tool approval
        await approval_repository.save_pending(
            request_id="req-legacy",
            request_type="tool",
            subject="write_file",
            session_id="session-test",
            details={"arguments": {"path": "test.py"}},
            reason="Test"
        )
        await test_session.commit()
        
        # Verify legacy fields in database
        result = await test_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == "req-legacy")
        )
        db_approval = result.scalar_one_or_none()
        
        # Legacy fields should be populated
        assert db_approval.call_id == "req-legacy"
        assert db_approval.tool_name == "write_file"
        # arguments extracts from details["arguments"]
        assert db_approval.arguments == {"path": "test.py"}
    
    async def test_count_pending(self, approval_manager, approval_repository, test_session):
        """Test counting pending approvals"""
        # Add multiple approvals
        for i in range(5):
            await approval_manager.add_pending(
                request_id=f"req-count-{i}",
                request_type="tool",
                subject="write_file",
                session_id="session-count",
                details={},
                reason="Test"
            )
        await test_session.commit()
        
        # Count pending
        count = await approval_repository.count_pending("session-count")
        assert count == 5
        
        # Approve one
        await approval_manager.approve("req-count-0")
        await test_session.commit()
        
        # Count should decrease
        count = await approval_repository.count_pending("session-count")
        assert count == 4

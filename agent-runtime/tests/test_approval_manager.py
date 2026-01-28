"""
Unit tests for ApprovalManager (Unified Approval System).

Tests cover:
- request_approval() - создание запроса на одобрение
- get_pending_approval() - получение pending approval
- approve() - одобрение
- reject() - отклонение
- cleanup_old_approvals() - очистка старых записей
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional, List

from app.domain.services.approval_management import ApprovalManager
from app.domain.entities.approval import (
    PendingApprovalState,
    ApprovalPolicy,
    ApprovalPolicyRule,
    ApprovalRequestType
)
from app.domain.repositories.approval_repository import ApprovalRepository


class MockApprovalRepository(ApprovalRepository):
    """Mock implementation of ApprovalRepository for testing"""
    
    def __init__(self):
        self._storage: dict[str, PendingApprovalState] = {}
    
    async def save_pending(
        self,
        request_id: str,
        request_type: str,
        subject: str,
        session_id: str,
        details: dict,
        reason: Optional[str] = None
    ) -> None:
        """Save pending approval to mock storage"""
        approval = PendingApprovalState(
            request_id=request_id,
            request_type=request_type,
            subject=subject,
            session_id=session_id,
            details=details,
            reason=reason,
            created_at=datetime.now(timezone.utc),
            status='pending'
        )
        self._storage[request_id] = approval
    
    async def get_pending(self, request_id: str) -> Optional[PendingApprovalState]:
        """Get pending approval from mock storage"""
        approval = self._storage.get(request_id)
        if approval and approval.status == 'pending':
            return approval
        return None
    
    async def get_all_pending(
        self,
        session_id: str,
        request_type: Optional[str] = None
    ) -> List[PendingApprovalState]:
        """Get all pending approvals for session"""
        result = []
        for approval in self._storage.values():
            if approval.session_id == session_id and approval.status == 'pending':
                if request_type is None or approval.request_type == request_type:
                    result.append(approval)
        return result
    
    async def update_status(
        self,
        request_id: str,
        status: str,
        decision_at: datetime,
        decision_reason: Optional[str] = None
    ) -> bool:
        """Update approval status"""
        if request_id in self._storage:
            approval = self._storage[request_id]
            # Create updated approval (Pydantic models are immutable)
            updated = PendingApprovalState(
                request_id=approval.request_id,
                request_type=approval.request_type,
                subject=approval.subject,
                session_id=approval.session_id,
                details=approval.details,
                reason=approval.reason,
                created_at=approval.created_at,
                status=status
            )
            self._storage[request_id] = updated
            return True
        return False
    
    async def delete_pending(self, request_id: str) -> bool:
        """Delete pending approval"""
        if request_id in self._storage:
            del self._storage[request_id]
            return True
        return False
    
    async def count_pending(self, session_id: str) -> int:
        """Count pending approvals for session"""
        count = 0
        for approval in self._storage.values():
            if approval.session_id == session_id and approval.status == 'pending':
                count += 1
        return count
    
    # Base Repository methods (required by interface)
    async def get(self, id: str) -> Optional[PendingApprovalState]:
        """Get approval by ID (any status)"""
        return self._storage.get(id)
    
    async def save(self, entity: PendingApprovalState) -> None:
        self._storage[entity.request_id] = entity
    
    async def delete(self, id: str) -> bool:
        return await self.delete_pending(id)
    
    async def list(self, limit: int = 100, offset: int = 0) -> List[PendingApprovalState]:
        return list(self._storage.values())[offset:offset + limit]
    
    async def exists(self, id: str) -> bool:
        return id in self._storage
    
    async def count(self) -> int:
        return len(self._storage)


@pytest_asyncio.fixture
async def mock_repository():
    """Fixture providing mock approval repository"""
    return MockApprovalRepository()


@pytest_asyncio.fixture
async def approval_manager(mock_repository):
    """Fixture providing ApprovalManager with mock repository"""
    policy = ApprovalPolicy(
        enabled=True,
        rules=[
            ApprovalPolicyRule(
                request_type=ApprovalRequestType.TOOL,
                subject_pattern="write_file",
                requires_approval=True,
                reason="File modification requires approval"
            ),
            ApprovalPolicyRule(
                request_type=ApprovalRequestType.TOOL,
                subject_pattern="read_file",
                requires_approval=False
            ),
        ],
        default_requires_approval=False
    )
    return ApprovalManager(
        approval_repository=mock_repository,
        approval_policy=policy
    )


@pytest.mark.asyncio
class TestApprovalManager:
    """Test suite for ApprovalManager"""
    
    async def test_should_require_approval_matching_rule(self, approval_manager):
        """Test that approval is required when rule matches"""
        requires, reason = await approval_manager.should_require_approval(
            request_type="tool",
            subject="write_file",
            details={"path": "test.py"}
        )
        
        assert requires is True
        assert reason == "File modification requires approval"
    
    async def test_should_require_approval_no_match(self, approval_manager):
        """Test that approval uses default when no rule matches"""
        requires, reason = await approval_manager.should_require_approval(
            request_type="tool",
            subject="unknown_tool",
            details={}
        )
        
        assert requires is False
        assert reason is None
    
    async def test_should_require_approval_explicit_no_approval(self, approval_manager):
        """Test that approval is not required when rule explicitly says so"""
        requires, reason = await approval_manager.should_require_approval(
            request_type="tool",
            subject="read_file",
            details={"path": "test.py"}
        )
        
        assert requires is False
        assert reason is None
    
    async def test_should_require_approval_disabled_globally(self, mock_repository):
        """Test that approval is not required when disabled globally"""
        policy = ApprovalPolicy(enabled=False, rules=[], default_requires_approval=True)
        manager = ApprovalManager(
            approval_repository=mock_repository,
            approval_policy=policy
        )
        
        requires, reason = await manager.should_require_approval(
            request_type="tool",
            subject="write_file",
            details={}
        )
        
        assert requires is False
        assert reason is None
    
    @patch('app.domain.services.approval_management.event_bus')
    async def test_add_pending(self, mock_event_bus, approval_manager, mock_repository):
        """Test adding a pending approval request"""
        mock_event_bus.publish = AsyncMock()
        
        await approval_manager.add_pending(
            request_id="req-123",
            request_type="tool",
            subject="write_file",
            session_id="session-abc",
            details={"path": "test.py", "content": "print('hello')"},
            reason="File modification requires approval"
        )
        
        # Verify saved to repository
        approval = await mock_repository.get_pending("req-123")
        assert approval is not None
        assert approval.request_id == "req-123"
        assert approval.request_type == "tool"
        assert approval.subject == "write_file"
        assert approval.session_id == "session-abc"
        assert approval.status == "pending"
        
        # Verify event published
        mock_event_bus.publish.assert_called_once()
    
    async def test_get_pending_existing(self, approval_manager, mock_repository):
        """Test getting an existing pending approval"""
        # Add approval first
        await mock_repository.save_pending(
            request_id="req-456",
            request_type="tool",
            subject="execute_command",
            session_id="session-xyz",
            details={"command": "ls -la"},
            reason="Command execution requires approval"
        )
        
        # Get it back
        approval = await approval_manager.get_pending("req-456")
        
        assert approval is not None
        assert approval.request_id == "req-456"
        assert approval.subject == "execute_command"
    
    async def test_get_pending_not_found(self, approval_manager):
        """Test getting a non-existent pending approval"""
        approval = await approval_manager.get_pending("non-existent")
        assert approval is None
    
    async def test_get_all_pending(self, approval_manager, mock_repository):
        """Test getting all pending approvals for a session"""
        # Add multiple approvals
        await mock_repository.save_pending(
            request_id="req-1",
            request_type="tool",
            subject="write_file",
            session_id="session-1",
            details={},
            reason="Test"
        )
        await mock_repository.save_pending(
            request_id="req-2",
            request_type="tool",
            subject="execute_command",
            session_id="session-1",
            details={},
            reason="Test"
        )
        await mock_repository.save_pending(
            request_id="req-3",
            request_type="plan",
            subject="Migration plan",
            session_id="session-1",
            details={},
            reason="Test"
        )
        
        # Get all for session
        all_approvals = await approval_manager.get_all_pending("session-1")
        assert len(all_approvals) == 3
        
        # Get filtered by type
        tool_approvals = await approval_manager.get_all_pending("session-1", request_type="tool")
        assert len(tool_approvals) == 2
    
    @patch('app.domain.services.approval_management.event_bus')
    async def test_approve(self, mock_event_bus, approval_manager, mock_repository):
        """Test approving a pending approval"""
        mock_event_bus.publish = AsyncMock()
        
        # Add approval first
        await mock_repository.save_pending(
            request_id="req-approve",
            request_type="tool",
            subject="write_file",
            session_id="session-test",
            details={},
            reason="Test"
        )
        
        # Approve it
        await approval_manager.approve("req-approve")
        
        # Verify status updated
        approval = await mock_repository.get("req-approve")
        assert approval is not None
        assert approval.status == "approved"
        
        # Verify event published
        mock_event_bus.publish.assert_called_once()
    
    async def test_approve_not_found(self, approval_manager):
        """Test approving a non-existent approval raises error"""
        with pytest.raises(ValueError, match="not found"):
            await approval_manager.approve("non-existent")
    
    @patch('app.domain.services.approval_management.event_bus')
    async def test_reject(self, mock_event_bus, approval_manager, mock_repository):
        """Test rejecting a pending approval"""
        mock_event_bus.publish = AsyncMock()
        
        # Add approval first
        await mock_repository.save_pending(
            request_id="req-reject",
            request_type="tool",
            subject="execute_command",
            session_id="session-test",
            details={},
            reason="Test"
        )
        
        # Reject it
        await approval_manager.reject("req-reject", reason="User declined")
        
        # Verify status updated
        approval = await mock_repository.get("req-reject")
        assert approval is not None
        assert approval.status == "rejected"
        
        # Verify event published
        mock_event_bus.publish.assert_called_once()
    
    async def test_reject_not_found(self, approval_manager):
        """Test rejecting a non-existent approval raises error"""
        with pytest.raises(ValueError, match="not found"):
            await approval_manager.reject("non-existent")
    
    async def test_update_policy(self, approval_manager):
        """Test updating approval policy"""
        new_policy = ApprovalPolicy(
            enabled=False,
            rules=[],
            default_requires_approval=True
        )
        
        approval_manager.update_policy(new_policy)
        
        assert approval_manager.get_policy() == new_policy
        assert approval_manager.is_enabled() is False
    
    async def test_is_enabled(self, approval_manager):
        """Test checking if approval system is enabled"""
        assert approval_manager.is_enabled() is True
        
        # Disable and check again
        new_policy = ApprovalPolicy(enabled=False, rules=[], default_requires_approval=False)
        approval_manager.update_policy(new_policy)
        
        assert approval_manager.is_enabled() is False
    
    async def test_condition_matching_greater_than(self, mock_repository):
        """Test condition matching with greater than operator"""
        policy = ApprovalPolicy(
            enabled=True,
            rules=[
                ApprovalPolicyRule(
                    request_type=ApprovalRequestType.TOOL,
                    subject_pattern="write_file",
                    conditions={"size_gt": 1000},
                    requires_approval=True,
                    reason="Large file requires approval"
                ),
            ],
            default_requires_approval=False
        )
        manager = ApprovalManager(
            approval_repository=mock_repository,
            approval_policy=policy
        )
        
        # Should require approval for large file
        requires, reason = await manager.should_require_approval(
            request_type="tool",
            subject="write_file",
            details={"size": 2000}
        )
        assert requires is True
        
        # Should not require approval for small file
        requires, reason = await manager.should_require_approval(
            request_type="tool",
            subject="write_file",
            details={"size": 500}
        )
        assert requires is False
    
    async def test_multiple_sessions_isolation(self, approval_manager, mock_repository):
        """Test that approvals are isolated by session"""
        # Add approvals for different sessions
        await mock_repository.save_pending(
            request_id="req-session1",
            request_type="tool",
            subject="write_file",
            session_id="session-1",
            details={},
            reason="Test"
        )
        await mock_repository.save_pending(
            request_id="req-session2",
            request_type="tool",
            subject="write_file",
            session_id="session-2",
            details={},
            reason="Test"
        )
        
        # Get approvals for each session
        session1_approvals = await approval_manager.get_all_pending("session-1")
        session2_approvals = await approval_manager.get_all_pending("session-2")
        
        assert len(session1_approvals) == 1
        assert len(session2_approvals) == 1
        assert session1_approvals[0].request_id == "req-session1"
        assert session2_approvals[0].request_id == "req-session2"

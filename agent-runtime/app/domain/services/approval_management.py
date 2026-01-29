"""
Unified Approval Manager for all approval requests (tools, plans, etc).

Replaces separate HITLManager and future PlanApprovalManager.

UPDATED: Now uses Repository pattern for database operations.

Responsibilities:
- Check if request requires approval using ApprovalPolicy
- Add requests to pending queue
- Retrieve pending requests
- Approve/reject requests
- Publish approval events
"""
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

from app.domain.entities.approval import (
    PendingApprovalState,
    ApprovalPolicy,
    ApprovalRequestType
)
from app.domain.repositories.approval_repository import ApprovalRepository
from app.events.event_bus import event_bus
from app.events.approval_events import (
    ApprovalRequestedEvent,
    ApprovalApprovedEvent,
    ApprovalRejectedEvent
)

logger = logging.getLogger("agent-runtime.approval_management")


class ApprovalManager:
    """
    Unified manager for all approval requests (tools, plans, etc).
    
    ARCHITECTURE: Uses Repository pattern - domain layer doesn't know about DB.
    
    Replaces separate HITLManager and PlanApprovalManager.
    
    Responsibilities:
    - Check if request requires approval using ApprovalPolicy
    - Add requests to pending queue
    - Retrieve pending requests
    - Approve/reject requests
    - Publish approval events
    """
    
    def __init__(
        self,
        approval_repository: ApprovalRepository,
        approval_policy: Optional[ApprovalPolicy] = None
    ):
        self._repository = approval_repository
        self._policy = approval_policy or ApprovalPolicy.default()
        logger.info("ApprovalManager initialized with repository")
    
    async def should_require_approval(
        self,
        request_type: str,
        subject: str,
        details: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a request requires approval based on policy.
        
        Args:
            request_type: Type of request ("tool", "plan", etc.)
            subject: Subject identifier (tool name, plan description)
            details: Request details for condition matching
        
        Returns:
            (requires_approval: bool, reason: Optional[str])
        
        Example:
            requires, reason = await manager.should_require_approval(
                request_type="tool",
                subject="write_file",
                details={"path": "test.py", "size": 1024}
            )
        """
        # If disabled globally
        if not self._policy.enabled:
            logger.debug(f"Approval disabled globally")
            return False, None
        
        # Check rules
        for rule in self._policy.rules:
            # Check request type
            if rule.request_type != request_type:
                continue
            
            # Check subject pattern
            if not re.match(rule.subject_pattern, subject):
                continue
            
            # Check conditions
            if rule.conditions:
                if not self._check_conditions(rule.conditions, details):
                    continue
            
            # Rule matched
            logger.debug(
                f"Approval rule matched: "
                f"type={request_type}, subject={subject}, "
                f"requires_approval={rule.requires_approval}"
            )
            return rule.requires_approval, rule.reason
        
        # No rule matched, use default
        logger.debug(
            f"No approval rule matched for type={request_type}, "
            f"subject={subject}, using default={self._policy.default_requires_approval}"
        )
        return self._policy.default_requires_approval, None
    
    def _check_conditions(
        self,
        conditions: Dict[str, Any],
        details: Dict[str, Any]
    ) -> bool:
        """Check if details match all conditions"""
        for key, value in conditions.items():
            if key.endswith("_gt"):
                # Greater than
                detail_key = key[:-3]  # Remove "_gt"
                if detail_key not in details or details[detail_key] <= value:
                    return False
            elif key.endswith("_lt"):
                # Less than
                detail_key = key[:-3]
                if detail_key not in details or details[detail_key] >= value:
                    return False
            elif key.endswith("_eq"):
                # Equal
                detail_key = key[:-3]
                if detail_key not in details or details[detail_key] != value:
                    return False
            # Add more condition types as needed
        
        return True
    
    async def add_pending(
        self,
        request_id: str,
        request_type: str,
        subject: str,
        session_id: str,
        details: Dict[str, Any],
        reason: Optional[str] = None
    ) -> None:
        """
        Add an approval request to pending queue.
        
        Called when a request requires user confirmation.
        
        Args:
            request_id: Unique identifier for this request
            request_type: Type ("tool", "plan")
            subject: Subject (tool name, plan description)
            session_id: Related session
            details: Request details (format depends on type)
            reason: Why approval is required
        """
        try:
            # ✅ Save via repository (no get_db() call)
            await self._repository.save_pending(
                request_id=request_id,
                request_type=request_type,
                subject=subject,
                session_id=session_id,
                details=details,
                reason=reason
            )
            
            logger.info(
                f"Added pending approval: "
                f"id={request_id}, type={request_type}, subject={subject}"
            )
            
            # ✅ Publish event synchronously (after DB flush, before commit)
            await event_bus.publish(
                ApprovalRequestedEvent(
                    aggregate_id=request_id,
                    session_id=session_id,
                    request_id=request_id,
                    request_type=request_type,
                    subject=subject,
                    reason=reason
                )
            )
        
        except Exception as e:
            logger.error(f"Failed to add pending approval: {e}", exc_info=True)
            raise
    
    async def get_pending(
        self,
        request_id: str
    ) -> Optional[PendingApprovalState]:
        """
        Get a specific pending approval by ID.
        
        Args:
            request_id: Request identifier
        
        Returns:
            PendingApprovalState if found, None otherwise
        """
        try:
            # ✅ Use repository (no get_db() call)
            approval = await self._repository.get_pending(request_id)
            
            if not approval:
                logger.debug(f"No pending approval found: {request_id}")
                return None
            
            return approval
        
        except Exception as e:
            logger.error(f"Failed to get pending approval: {e}", exc_info=True)
            raise
    
    async def get_all_pending(
        self,
        session_id: str,
        request_type: Optional[str] = None
    ) -> List[PendingApprovalState]:
        """
        Get all pending approvals for a session.
        
        Used by IDE to recover pending requests after restart.
        
        Args:
            session_id: Session identifier
            request_type: Optional filter by type
        
        Returns:
            List of PendingApprovalState objects
        """
        try:
            # ✅ Use repository (no get_db() call)
            return await self._repository.get_all_pending(
                session_id=session_id,
                request_type=request_type
            )
        
        except Exception as e:
            logger.error(f"Failed to get pending approvals: {e}", exc_info=True)
            raise
    
    async def approve(
        self,
        request_id: str
    ) -> None:
        """
        Approve an approval request.
        
        Called when user confirms they want to proceed.
        
        Args:
            request_id: Request identifier to approve
        """
        try:
            logger.info(f"[DEBUG] ApprovalManager.approve() called for request_id={request_id}")
            
            # ✅ Get approval via repository
            approval = await self._repository.get_pending(request_id)
            
            if not approval:
                logger.error(f"[DEBUG] Approval {request_id} not found in get_pending()")
                raise ValueError(f"Approval {request_id} not found")
            
            logger.info(f"[DEBUG] Found pending approval: {request_id}, status={approval.status}")
            
            # ✅ Update status via repository
            await self._repository.update_status(
                request_id=request_id,
                status='approved',
                decision_at=datetime.now(timezone.utc)
            )
            
            logger.info(f"[DEBUG] Approval approved: {request_id} - update_status() completed")
            
            # ✅ Publish event synchronously (after DB flush, before commit)
            await event_bus.publish(
                ApprovalApprovedEvent(
                    aggregate_id=request_id,
                    session_id=approval.session_id,
                    request_id=request_id,
                    request_type=approval.request_type
                )
            )
        
        except Exception as e:
            logger.error(f"Failed to approve: {e}", exc_info=True)
            raise
    
    async def reject(
        self,
        request_id: str,
        reason: Optional[str] = None
    ) -> None:
        """
        Reject an approval request.
        
        Called when user declines to proceed.
        
        Args:
            request_id: Request identifier to reject
            reason: Why user rejected (optional)
        """
        try:
            logger.info(f"[DEBUG] ApprovalManager.reject() called for request_id={request_id}, reason={reason}")
            
            # ✅ Get approval via repository
            approval = await self._repository.get_pending(request_id)
            
            if not approval:
                logger.error(f"[DEBUG] Approval {request_id} not found in get_pending()")
                raise ValueError(f"Approval {request_id} not found")
            
            logger.info(f"[DEBUG] Found pending approval: {request_id}, status={approval.status}")
            
            # ✅ Update status via repository
            await self._repository.update_status(
                request_id=request_id,
                status='rejected',
                decision_at=datetime.now(timezone.utc),
                decision_reason=reason
            )
            
            logger.info(f"[DEBUG] Approval rejected: {request_id}{f', reason: {reason}' if reason else ''} - update_status() completed")
            
            # ✅ Publish event synchronously (after DB flush, before commit)
            await event_bus.publish(
                ApprovalRejectedEvent(
                    aggregate_id=request_id,
                    session_id=approval.session_id,
                    request_id=request_id,
                    request_type=approval.request_type,
                    reason=reason
                )
            )
        
        except Exception as e:
            logger.error(f"Failed to reject approval: {e}", exc_info=True)
            raise
    
    def update_policy(self, policy: ApprovalPolicy) -> None:
        """
        Update the current policy configuration.
        
        Args:
            policy: New approval policy
        """
        self._policy = policy
        logger.info(
            f"Policy updated: enabled={policy.enabled}, "
            f"rules={len(policy.rules)}"
        )
    
    def get_policy(self) -> ApprovalPolicy:
        """
        Get current policy configuration.
        
        Returns:
            Current ApprovalPolicy
        """
        return self._policy
    
    def is_enabled(self) -> bool:
        """
        Check if approval system is globally enabled.
        
        Returns:
            True if approval is enabled
        """
        return self._policy.enabled


# NOTE: Singleton pattern removed - ApprovalManager now requires Repository
# Use get_approval_manager_with_db() dependency function instead


def get_approval_manager_with_db(approval_repository: ApprovalRepository) -> ApprovalManager:
    """
    Create ApprovalManager instance with repository.
    
    This is a factory function for creating ApprovalManager with proper dependencies.
    Should be used with FastAPI Depends() for dependency injection.
    
    Args:
        approval_repository: ApprovalRepository implementation
    
    Returns:
        ApprovalManager instance
        
    Example:
        >>> # In FastAPI endpoint
        >>> async def get_manager(db: AsyncSession = Depends(get_db)):
        ...     repo = ApprovalRepositoryImpl(db)
        ...     return get_approval_manager_with_db(repo)
    """
    return ApprovalManager(approval_repository=approval_repository)


# DEPRECATED: Global singleton for backward compatibility
# This will be removed in future versions
_global_approval_manager: Optional[ApprovalManager] = None


def _get_global_approval_manager() -> ApprovalManager:
    """
    Get global approval manager (DEPRECATED).
    
    This creates a manager that manages its own DB sessions.
    Use get_approval_manager_with_db() with dependency injection instead.
    
    Returns:
        ApprovalManager instance
    """
    global _global_approval_manager
    if _global_approval_manager is None:
        # Create a special repository that manages its own sessions
        from app.infrastructure.persistence.repositories.approval_repository_impl import (
            ApprovalRepositoryImpl
        )
        from app.services.database import get_db
        
        class SelfManagedRepository(ApprovalRepository):
            """
            Repository that creates its own DB sessions (for backward compatibility).
            
            IMPORTANT: This repository manages its own database sessions and commits.
            Each method creates a new session, performs the operation, and commits
            the transaction before closing the session.
            """
            
            async def save_pending(self, request_id, request_type, subject, session_id, details, reason=None):
                async for db in get_db():
                    repo = ApprovalRepositoryImpl(db)
                    await repo.save_pending(request_id, request_type, subject, session_id, details, reason)
                    await db.commit()  # Explicit commit after flush
            
            async def get_pending(self, request_id):
                async for db in get_db():
                    repo = ApprovalRepositoryImpl(db)
                    return await repo.get_pending(request_id)
            
            async def get_all_pending(self, session_id, request_type=None):
                async for db in get_db():
                    repo = ApprovalRepositoryImpl(db)
                    return await repo.get_all_pending(session_id, request_type)
            
            async def update_status(self, request_id, status, decision_at, decision_reason=None):
                async for db in get_db():
                    repo = ApprovalRepositoryImpl(db)
                    result = await repo.update_status(request_id, status, decision_at, decision_reason)
                    await db.commit()  # Explicit commit after flush
                    return result
            
            async def delete_pending(self, request_id):
                async for db in get_db():
                    repo = ApprovalRepositoryImpl(db)
                    result = await repo.delete_pending(request_id)
                    await db.commit()  # Explicit commit after flush
                    return result
            
            async def count_pending(self, session_id):
                async for db in get_db():
                    repo = ApprovalRepositoryImpl(db)
                    return await repo.count_pending(session_id)
            
            # Base Repository methods (not used, but required by interface)
            async def get(self, id): return await self.get_pending(id)
            async def save(self, entity): pass
            async def delete(self, id): return await self.delete_pending(id)
            async def list(self, limit=100, offset=0): return []
            async def exists(self, id): return (await self.get_pending(id)) is not None
            async def count(self): return 0
        
        _global_approval_manager = ApprovalManager(
            approval_repository=SelfManagedRepository()
        )
    
    return _global_approval_manager


# Global singleton instance (DEPRECATED - for backward compatibility only)
# New code should use dependency injection with get_approval_manager_with_db()
approval_manager = _get_global_approval_manager()

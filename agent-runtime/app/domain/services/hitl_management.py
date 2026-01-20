"""
HITL Manager for managing pending tool calls and user decisions.

Uses database as the source of truth for pending approvals.
No longer depends on AgentContext for caching.

UPDATED: Migrated to domain/services layer
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.domain.entities.hitl import (
    HITLPendingState,
    HITLUserDecision,
    HITLDecision,
    HITLAuditLog
)
from app.services.database import get_db, get_database_service

# Event-Driven Architecture imports
from app.events.event_bus import event_bus
from app.events.tool_events import (
    HITLApprovalRequestedEvent,
    HITLDecisionMadeEvent
)

logger = logging.getLogger("agent-runtime.hitl_manager")


class HITLManager:
    """
    Manager for HITL pending states and user decisions.
    
    Uses both AgentContext.metadata (for fast access) and Database (for persistence):
    - hitl_pending_calls: Dict[call_id, HITLPendingState] (in memory)
    - hitl_audit_logs: List[HITLAuditLog] (in memory)
    - pending_approvals table: Persistent storage (in database)
    """
    
    def __init__(self):
        """Initialize HITL Manager with async database service"""
        self.db_service = get_database_service()
    
    async def add_pending(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: Dict,
        reason: Optional[str] = None,
        timeout_seconds: int = 300
    ) -> HITLPendingState:
        """
        Add a tool call to pending HITL approval.
        Saves to both database (persistent) and AgentContext (fast access).
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            tool_name: Name of the tool
            arguments: Tool arguments
            reason: Reason for requiring approval
            timeout_seconds: Timeout for user decision (deprecated, kept for compatibility)
            
        Returns:
            Created HITLPendingState
        """
        # Create pending state
        pending_state = HITLPendingState(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            timeout_seconds=timeout_seconds
        )
        
        # Store in database (source of truth)
        await self._save_pending_async(
            session_id, call_id, tool_name, arguments, reason
        )
        
        # Note: No longer caching in AgentContext.metadata
        # Database is the single source of truth for pending approvals
        
        logger.info(
            f"Added pending HITL approval: session={session_id}, "
            f"call_id={call_id}, tool={tool_name}"
        )
        
        # Publish HITL approval requested event
        await event_bus.publish(
            HITLApprovalRequestedEvent(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
                reason=reason or "",
                timeout_seconds=timeout_seconds
            )
        )
        
        return pending_state
    
    async def get_pending(self, session_id: str, call_id: str) -> Optional[HITLPendingState]:
        """
        Get pending HITL state for a tool call from database.
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            
        Returns:
            HITLPendingState if found, None otherwise
        """
        # Load from database
        async for db in get_db():
            from sqlalchemy import select
            from app.services.database import PendingApproval
            
            result = await db.execute(
                select(PendingApproval).where(
                    PendingApproval.call_id == call_id,
                    PendingApproval.session_id == session_id,
                    PendingApproval.status == 'pending'
                )
            )
            approval = result.scalar_one_or_none()
            
            if not approval:
                logger.debug(f"No pending HITL state for call_id={call_id}")
                return None
            
            return HITLPendingState(
                call_id=approval.call_id,
                tool_name=approval.tool_name,
                arguments=approval.arguments,
                reason=approval.reason,
                timeout_seconds=300  # Default
            )
        
        return None
    
    async def get_all_pending(self, session_id: str) -> List[HITLPendingState]:
        """
        Get all pending HITL states for a session from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of HITLPendingState objects
        """
        # Load from database
        async for db in get_db():
            pending_approvals = await self.db_service.get_pending_approvals(db, session_id)
            
            return [
                HITLPendingState(
                    call_id=approval['call_id'],
                    tool_name=approval['tool_name'],
                    arguments=approval['arguments'],
                    reason=approval.get('reason'),
                    timeout_seconds=300  # Default
                )
                for approval in pending_approvals
            ]
        
        return []
    
    async def remove_pending(self, session_id: str, call_id: str) -> bool:
        """
        Remove a pending HITL state.
        Removes from both database and AgentContext.
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            
        Returns:
            True if removed, False if not found
        """
        # Remove from database
        removed = await self._delete_pending_async(call_id)
        
        if removed:
            logger.info(f"Removed pending HITL state: call_id={call_id}")
        
        return removed
    
    async def cleanup_expired(self, session_id: str) -> int:
        """
        Clean up expired pending HITL states from database.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of expired states removed
        """
        # Load all pending from database
        pending_states = await self.get_all_pending(session_id)
        
        expired_count = 0
        for pending_state in pending_states:
            if pending_state.is_expired():
                await self._delete_pending_async(pending_state.call_id)
                expired_count += 1
        
        if expired_count > 0:
            logger.info(
                f"Cleaned up {expired_count} expired HITL states "
                f"for session {session_id}"
            )
        
        return expired_count
    
    async def log_decision(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        original_arguments: Dict,
        decision: HITLDecision,
        modified_arguments: Optional[Dict] = None,
        feedback: Optional[str] = None
    ) -> HITLAuditLog:
        """
        Log a user decision to audit log.
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            tool_name: Tool name
            original_arguments: Original tool arguments
            decision: User decision
            modified_arguments: Modified arguments (for EDIT)
            feedback: User feedback (for REJECT)
            
        Returns:
            Created HITLAuditLog
        """
        # Create audit log entry
        audit_log = HITLAuditLog(
            session_id=session_id,
            call_id=call_id,
            tool_name=tool_name,
            original_arguments=original_arguments,
            decision=decision,
            modified_arguments=modified_arguments,
            feedback=feedback
        )
        
        # Note: Audit logs are now only logged via events, not stored in memory
        # For persistent audit trail, use event-driven audit logger
        
        logger.info(
            f"Logged HITL decision: session={session_id}, call_id={call_id}, "
            f"decision={decision.value}, tool={tool_name}"
        )
        
        # Publish HITL decision made event
        await event_bus.publish(
            HITLDecisionMadeEvent(
                session_id=session_id,
                call_id=call_id,
                decision=decision.value,
                tool_name=tool_name,
                original_args=original_arguments,
                modified_args=modified_arguments
            )
        )
        
        return audit_log
    
    def get_audit_logs(self, session_id: str) -> List[HITLAuditLog]:
        """
        Get all audit logs for a session.
        
        Note: Audit logs are now tracked via event-driven audit logger,
              not stored in memory. This method returns empty list.
              Use audit logger events for persistent audit trail.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Empty list (audit logs tracked via events)
        """
        logger.debug(
            f"get_audit_logs called for {session_id} - "
            f"audit logs tracked via event-driven audit logger"
        )
        return []
    
    def has_pending(self, session_id: str, call_id: str) -> bool:
        """
        Check if a tool call has pending HITL approval.
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            
        Returns:
            True if pending approval exists
        """
        return self.get_pending(session_id, call_id) is not None


    async def _save_pending_async(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: Dict,
        reason: Optional[str]
    ):
        """Async helper to save pending approval to database"""
        try:
            async for db in get_db():
                await self.db_service.save_pending_approval(
                    db=db,
                    session_id=session_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    reason=reason
                )
                break
        except Exception as e:
            logger.error(f"Failed to save pending approval to database: {e}", exc_info=True)
    
    async def _delete_pending_async(self, call_id: str) -> bool:
        """Async helper to delete pending approval from database"""
        try:
            async for db in get_db():
                result = await self.db_service.delete_pending_approval(db, call_id)
                return result
        except Exception as e:
            logger.error(f"Failed to delete pending approval from database: {e}", exc_info=True)
            return False


# Singleton instance for global use
hitl_manager = HITLManager()

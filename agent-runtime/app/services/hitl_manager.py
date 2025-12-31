"""
HITL Manager for managing pending tool calls and user decisions.

Integrates with AgentContext to store pending states and provides
methods for adding, retrieving, and resolving HITL approvals.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

from app.models.hitl_models import (
    HITLPendingState,
    HITLUserDecision,
    HITLDecision,
    HITLAuditLog
)

# Lazy import to avoid circular dependency
if TYPE_CHECKING:
    from app.services.agent_context import AgentContextManager

logger = logging.getLogger("agent-runtime.hitl_manager")

# Key for storing HITL pending calls in AgentContext.metadata
HITL_PENDING_KEY = "hitl_pending_calls"
HITL_AUDIT_KEY = "hitl_audit_logs"


def _get_agent_context_manager():
    """Lazy import to avoid circular dependency"""
    from app.services.agent_context import agent_context_manager
    return agent_context_manager


class HITLManager:
    """
    Manager for HITL pending states and user decisions.
    
    Uses AgentContext.metadata to store:
    - hitl_pending_calls: Dict[call_id, HITLPendingState]
    - hitl_audit_logs: List[HITLAuditLog]
    """
    
    def add_pending(
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
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            tool_name: Name of the tool
            arguments: Tool arguments
            reason: Reason for requiring approval
            timeout_seconds: Timeout for user decision
            
        Returns:
            Created HITLPendingState
        """
        context = _get_agent_context_manager().get_or_create(session_id)
        
        # Initialize pending calls dict if not exists
        if HITL_PENDING_KEY not in context.metadata:
            context.metadata[HITL_PENDING_KEY] = {}
        
        # Create pending state
        pending_state = HITLPendingState(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            timeout_seconds=timeout_seconds
        )
        
        # Store in context metadata
        context.metadata[HITL_PENDING_KEY][call_id] = pending_state.model_dump()
        
        logger.info(
            f"Added pending HITL approval: session={session_id}, "
            f"call_id={call_id}, tool={tool_name}"
        )
        
        return pending_state
    
    def get_pending(self, session_id: str, call_id: str) -> Optional[HITLPendingState]:
        """
        Get pending HITL state for a tool call.
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            
        Returns:
            HITLPendingState if found, None otherwise
        """
        context = _get_agent_context_manager().get(session_id)
        if not context:
            logger.warning(f"Session not found: {session_id}")
            return None
        
        pending_calls = context.metadata.get(HITL_PENDING_KEY, {})
        pending_data = pending_calls.get(call_id)
        
        if not pending_data:
            logger.debug(f"No pending HITL state for call_id={call_id}")
            return None
        
        return HITLPendingState(**pending_data)
    
    def get_all_pending(self, session_id: str) -> List[HITLPendingState]:
        """
        Get all pending HITL states for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of HITLPendingState objects
        """
        context = _get_agent_context_manager().get(session_id)
        if not context:
            return []
        
        pending_calls = context.metadata.get(HITL_PENDING_KEY, {})
        return [HITLPendingState(**data) for data in pending_calls.values()]
    
    def remove_pending(self, session_id: str, call_id: str) -> bool:
        """
        Remove a pending HITL state.
        
        Args:
            session_id: Session identifier
            call_id: Tool call identifier
            
        Returns:
            True if removed, False if not found
        """
        context = _get_agent_context_manager().get(session_id)
        if not context:
            return False
        
        pending_calls = context.metadata.get(HITL_PENDING_KEY, {})
        if call_id in pending_calls:
            del pending_calls[call_id]
            logger.info(f"Removed pending HITL state: call_id={call_id}")
            return True
        
        return False
    
    def cleanup_expired(self, session_id: str) -> int:
        """
        Clean up expired pending HITL states.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of expired states removed
        """
        context = _get_agent_context_manager().get(session_id)
        if not context:
            return 0
        
        pending_calls = context.metadata.get(HITL_PENDING_KEY, {})
        expired_ids = []
        
        for call_id, pending_data in pending_calls.items():
            pending_state = HITLPendingState(**pending_data)
            if pending_state.is_expired():
                expired_ids.append(call_id)
        
        for call_id in expired_ids:
            del pending_calls[call_id]
        
        if expired_ids:
            logger.info(
                f"Cleaned up {len(expired_ids)} expired HITL states "
                f"for session {session_id}"
            )
        
        return len(expired_ids)
    
    def log_decision(
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
        context = _get_agent_context_manager().get_or_create(session_id)
        
        # Initialize audit logs list if not exists
        if HITL_AUDIT_KEY not in context.metadata:
            context.metadata[HITL_AUDIT_KEY] = []
        
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
        
        # Store in context metadata
        context.metadata[HITL_AUDIT_KEY].append(audit_log.model_dump())
        
        logger.info(
            f"Logged HITL decision: session={session_id}, call_id={call_id}, "
            f"decision={decision.value}, tool={tool_name}"
        )
        
        return audit_log
    
    def get_audit_logs(self, session_id: str) -> List[HITLAuditLog]:
        """
        Get all audit logs for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of HITLAuditLog objects
        """
        context = _get_agent_context_manager().get(session_id)
        if not context:
            return []
        
        audit_logs_data = context.metadata.get(HITL_AUDIT_KEY, [])
        return [HITLAuditLog(**data) for data in audit_logs_data]
    
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


# Singleton instance for global use
hitl_manager = HITLManager()

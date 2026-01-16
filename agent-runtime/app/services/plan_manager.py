"""
Plan Manager for managing execution plans and user decisions.

Similar to HITL Manager but for execution plans.
Stores audit logs in AgentContext.metadata for session-level tracking.
"""
import logging
from typing import Dict, List, Optional, TYPE_CHECKING

from app.models.plan_models import PlanAuditLog, PlanDecision

if TYPE_CHECKING:
    pass

logger = logging.getLogger("agent-runtime.plan_manager")

# Key for storing plan audit logs in AgentContext.metadata
PLAN_AUDIT_KEY = "plan_audit_logs"


def _get_agent_context_manager():
    """Lazy import to avoid circular dependency"""
    from app.services.agent_context_async import agent_context_manager
    return agent_context_manager


class PlanManager:
    """
    Manager for execution plans and user decisions.
    
    Stores audit logs in AgentContext.metadata for session-level tracking.
    Plans themselves are stored in SessionManager.
    """
    
    async def log_decision(
        self,
        session_id: str,
        plan_id: str,
        original_task: str,
        decision: PlanDecision,
        modified_subtasks: Optional[List[Dict]] = None,
        feedback: Optional[str] = None
    ) -> PlanAuditLog:
        """
        Log a user decision to audit log.
        
        Args:
            session_id: Session identifier
            plan_id: Plan identifier
            original_task: Original user task
            decision: User decision
            modified_subtasks: Modified subtasks (for EDIT)
            feedback: User feedback (for REJECT)
            
        Returns:
            Created PlanAuditLog
        """
        # Get or create context (async)
        context = await _get_agent_context_manager().get_or_create(session_id)
        
        # Initialize audit logs list if not exists
        if PLAN_AUDIT_KEY not in context.metadata:
            context.metadata[PLAN_AUDIT_KEY] = []
        
        # Create audit log entry
        audit_log = PlanAuditLog(
            session_id=session_id,
            plan_id=plan_id,
            original_task=original_task,
            decision=decision,
            modified_subtasks=modified_subtasks,
            feedback=feedback
        )
        
        # Store in context metadata
        context.metadata[PLAN_AUDIT_KEY].append(audit_log.model_dump())
        
        logger.info(
            f"Logged plan decision: session={session_id}, plan_id={plan_id}, "
            f"decision={decision.value}"
        )
        
        return audit_log
    
    def get_audit_logs(self, session_id: str) -> List[PlanAuditLog]:
        """
        Get all audit logs for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of PlanAuditLog objects
        """
        context = _get_agent_context_manager().get(session_id)
        if not context:
            return []
        
        audit_logs_data = context.metadata.get(PLAN_AUDIT_KEY, [])
        return [PlanAuditLog(**data) for data in audit_logs_data]


# Singleton instance for global use
plan_manager = PlanManager()

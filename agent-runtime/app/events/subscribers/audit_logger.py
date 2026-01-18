"""
Audit logger subscriber that logs critical events.
"""

import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..event_bus import event_bus
from ..base_event import BaseEvent
from ..event_types import EventType

logger = structlog.get_logger(__name__)


class AuditLogger:
    """
    Logs critical events for audit purposes.
    
    This subscriber listens to important events and logs them with full context:
    - Agent switches
    - HITL decisions
    - Errors
    - Tool executions
    """
    
    def __init__(self):
        self._audit_log: List[Dict[str, Any]] = []
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        """Subscribe to critical events."""
        
        # Agent switches
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=self._log_agent_switch,
            priority=10  # High priority for audit logging
        )
        
        # HITL decisions
        event_bus.subscribe(
            event_type=EventType.HITL_DECISION_MADE,
            handler=self._log_hitl_decision,
            priority=10
        )
        
        # Errors
        event_bus.subscribe(
            event_type=EventType.AGENT_ERROR_OCCURRED,
            handler=self._log_error,
            priority=10
        )
        
        event_bus.subscribe(
            event_type=EventType.TOOL_EXECUTION_FAILED,
            handler=self._log_tool_failure,
            priority=10
        )
        
        # Tool approvals
        event_bus.subscribe(
            event_type=EventType.TOOL_APPROVAL_REQUIRED,
            handler=self._log_approval_required,
            priority=10
        )
        
        logger.info("AuditLogger initialized and subscribed to events")
    
    async def _log_agent_switch(self, event: BaseEvent):
        """Log agent switch event."""
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": "agent_switched",
            "event_id": event.event_id,
            "session_id": event.session_id,
            "correlation_id": event.correlation_id,
            "from_agent": event.data["from_agent"],
            "to_agent": event.data["to_agent"],
            "reason": event.data["reason"],
            "confidence": event.data.get("confidence")
        }
        
        self._audit_log.append(log_entry)
        
        logger.info(
            "agent_switched",
            session_id=event.session_id,
            from_agent=event.data["from_agent"],
            to_agent=event.data["to_agent"],
            reason=event.data["reason"],
            correlation_id=event.correlation_id,
            event_id=event.event_id
        )
    
    async def _log_hitl_decision(self, event: BaseEvent):
        """Log HITL decision event."""
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": "hitl_decision_made",
            "event_id": event.event_id,
            "session_id": event.session_id,
            "correlation_id": event.correlation_id,
            "call_id": event.data["call_id"],
            "decision": event.data["decision"],
            "tool_name": event.data["tool_name"],
            "original_args": event.data["original_args"],
            "modified_args": event.data.get("modified_args")
        }
        
        self._audit_log.append(log_entry)
        
        logger.info(
            "hitl_decision_made",
            session_id=event.session_id,
            call_id=event.data["call_id"],
            decision=event.data["decision"],
            tool_name=event.data["tool_name"],
            correlation_id=event.correlation_id,
            event_id=event.event_id
        )
    
    async def _log_error(self, event: BaseEvent):
        """Log agent error event."""
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": "agent_error",
            "event_id": event.event_id,
            "session_id": event.session_id,
            "correlation_id": event.correlation_id,
            "agent": event.data["agent"],
            "error_message": event.data["error_message"],
            "error_type": event.data["error_type"]
        }
        
        self._audit_log.append(log_entry)
        
        logger.error(
            "agent_error",
            session_id=event.session_id,
            agent=event.data["agent"],
            error_message=event.data["error_message"],
            error_type=event.data["error_type"],
            correlation_id=event.correlation_id,
            event_id=event.event_id
        )
    
    async def _log_tool_failure(self, event: BaseEvent):
        """Log tool execution failure."""
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": "tool_execution_failed",
            "event_id": event.event_id,
            "session_id": event.session_id,
            "correlation_id": event.correlation_id,
            "tool_name": event.data["tool_name"],
            "call_id": event.data["call_id"],
            "error_message": event.data["error_message"],
            "error_type": event.data["error_type"]
        }
        
        self._audit_log.append(log_entry)
        
        logger.error(
            "tool_execution_failed",
            session_id=event.session_id,
            tool_name=event.data["tool_name"],
            call_id=event.data["call_id"],
            error_message=event.data["error_message"],
            error_type=event.data["error_type"],
            correlation_id=event.correlation_id,
            event_id=event.event_id
        )
    
    async def _log_approval_required(self, event: BaseEvent):
        """Log tool approval required event."""
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": "tool_approval_required",
            "event_id": event.event_id,
            "session_id": event.session_id,
            "correlation_id": event.correlation_id,
            "tool_name": event.data["tool_name"],
            "call_id": event.data["call_id"],
            "reason": event.data["reason"],
            "arguments": event.data["arguments"]
        }
        
        self._audit_log.append(log_entry)
        
        logger.warning(
            "tool_approval_required",
            session_id=event.session_id,
            tool_name=event.data["tool_name"],
            call_id=event.data["call_id"],
            reason=event.data["reason"],
            correlation_id=event.correlation_id,
            event_id=event.event_id
        )
    
    def get_audit_log(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries with optional filtering.
        
        Args:
            session_id: Filter by session ID
            event_type: Filter by event type
            limit: Maximum number of entries to return
        
        Returns:
            List of audit log entries
        """
        filtered_log = self._audit_log
        
        if session_id:
            filtered_log = [
                entry for entry in filtered_log
                if entry.get("session_id") == session_id
            ]
        
        if event_type:
            filtered_log = [
                entry for entry in filtered_log
                if entry.get("event_type") == event_type
            ]
        
        if limit:
            filtered_log = filtered_log[-limit:]
        
        return filtered_log
    
    def clear_audit_log(self):
        """Clear audit log (for testing)."""
        self._audit_log.clear()
        logger.info("Audit log cleared")


# Global singleton instance
audit_logger = AuditLogger()

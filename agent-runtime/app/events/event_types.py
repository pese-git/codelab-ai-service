"""
Event types and categories for the Event-Driven Architecture.
"""

from enum import Enum


class EventCategory(str, Enum):
    """Categories of events in the system."""
    
    AGENT = "agent"
    SESSION = "session"
    TOOL = "tool"
    HITL = "hitl"
    APPROVAL = "approval"
    SYSTEM = "system"
    METRICS = "metrics"


class EventType(str, Enum):
    """Specific event types in the system."""
    
    # Agent Events
    AGENT_SWITCHED = "agent.switched"
    AGENT_PROCESSING_STARTED = "agent.processing.started"
    AGENT_PROCESSING_COMPLETED = "agent.processing.completed"
    AGENT_ERROR_OCCURRED = "agent.error.occurred"
    
    # Session Events
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    SESSION_DELETED = "session.deleted"
    MESSAGE_ADDED = "session.message.added"
    
    # Tool Events
    TOOL_EXECUTION_REQUESTED = "tool.execution.requested"
    TOOL_EXECUTION_STARTED = "tool.execution.started"
    TOOL_EXECUTION_COMPLETED = "tool.execution.completed"
    TOOL_EXECUTION_FAILED = "tool.execution.failed"
    TOOL_APPROVAL_REQUIRED = "tool.approval.required"
    
    # HITL Events
    HITL_APPROVAL_REQUESTED = "hitl.approval.requested"
    HITL_DECISION_MADE = "hitl.decision.made"
    HITL_TIMEOUT_OCCURRED = "hitl.timeout.occurred"
    
    # Approval Events (Unified Approval System)
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    
    # System Events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    BACKGROUND_TASK_STARTED = "system.background_task.started"
    BACKGROUND_TASK_COMPLETED = "system.background_task.completed"
    
    # Metrics Events
    METRICS_COLLECTED = "metrics.collected"
    PERFORMANCE_MEASURED = "metrics.performance.measured"
    
    # LLM Events
    LLM_REQUEST_STARTED = "llm.request.started"
    LLM_REQUEST_COMPLETED = "llm.request.completed"
    LLM_REQUEST_FAILED = "llm.request.failed"

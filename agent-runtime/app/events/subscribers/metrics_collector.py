"""
Metrics collector subscriber that collects metrics from events.
"""

import logging
from typing import Dict, Any

from ..event_bus import event_bus
from ..base_event import BaseEvent
from ..event_types import EventType, EventCategory

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects metrics from events.
    
    This subscriber listens to all events and collects various metrics:
    - Agent switches
    - Processing durations
    - Tool executions
    - HITL decisions
    - Errors
    """
    
    def __init__(self):
        self._metrics: Dict[str, Any] = {
            "agent_switches": {},
            "agent_processing": {},
            "tool_executions": {},
            "hitl_decisions": {},
            "errors": {},
        }
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        """Subscribe to relevant events."""
        
        # Subscribe to all agent events
        event_bus.subscribe(
            event_category=EventCategory.AGENT,
            handler=self._collect_agent_metrics,
            priority=5
        )
        
        # Subscribe to all tool events
        event_bus.subscribe(
            event_category=EventCategory.TOOL,
            handler=self._collect_tool_metrics,
            priority=5
        )
        
        # Subscribe to all HITL events
        event_bus.subscribe(
            event_category=EventCategory.HITL,
            handler=self._collect_hitl_metrics,
            priority=5
        )
        
        logger.info("MetricsCollector initialized and subscribed to events")
    
    async def _collect_agent_metrics(self, event: BaseEvent):
        """Collect metrics from agent events."""
        
        if event.event_type == EventType.AGENT_SWITCHED:
            # Count agent switches
            from_agent = event.data["from_agent"]
            to_agent = event.data["to_agent"]
            key = f"{from_agent}_to_{to_agent}"
            
            if key not in self._metrics["agent_switches"]:
                self._metrics["agent_switches"][key] = 0
            self._metrics["agent_switches"][key] += 1
            
            logger.debug(f"Recorded agent switch: {from_agent} -> {to_agent}")
        
        elif event.event_type == EventType.AGENT_PROCESSING_COMPLETED:
            # Record processing duration
            agent = event.data["agent"]
            duration = event.data["duration_ms"]
            success = event.data["success"]
            
            if agent not in self._metrics["agent_processing"]:
                self._metrics["agent_processing"][agent] = {
                    "count": 0,
                    "total_duration_ms": 0,
                    "success_count": 0,
                    "failure_count": 0
                }
            
            self._metrics["agent_processing"][agent]["count"] += 1
            self._metrics["agent_processing"][agent]["total_duration_ms"] += duration
            
            if success:
                self._metrics["agent_processing"][agent]["success_count"] += 1
            else:
                self._metrics["agent_processing"][agent]["failure_count"] += 1
            
            logger.debug(
                f"Recorded agent processing: {agent}, "
                f"duration={duration}ms, success={success}"
            )
        
        elif event.event_type == EventType.AGENT_ERROR_OCCURRED:
            # Count errors by agent
            agent = event.data["agent"]
            error_type = event.data["error_type"]
            
            if agent not in self._metrics["errors"]:
                self._metrics["errors"][agent] = {}
            
            if error_type not in self._metrics["errors"][agent]:
                self._metrics["errors"][agent][error_type] = 0
            
            self._metrics["errors"][agent][error_type] += 1
            
            logger.debug(f"Recorded error: {agent}, type={error_type}")
    
    async def _collect_tool_metrics(self, event: BaseEvent):
        """Collect metrics from tool events."""
        
        if event.event_type == EventType.TOOL_EXECUTION_REQUESTED:
            tool_name = event.data["tool_name"]
            
            if tool_name not in self._metrics["tool_executions"]:
                self._metrics["tool_executions"][tool_name] = {
                    "requested": 0,
                    "completed": 0,
                    "failed": 0,
                    "requires_approval": 0
                }
            
            self._metrics["tool_executions"][tool_name]["requested"] += 1
        
        elif event.event_type == EventType.TOOL_EXECUTION_COMPLETED:
            tool_name = event.data["tool_name"]
            
            if tool_name in self._metrics["tool_executions"]:
                self._metrics["tool_executions"][tool_name]["completed"] += 1
        
        elif event.event_type == EventType.TOOL_EXECUTION_FAILED:
            tool_name = event.data["tool_name"]
            
            if tool_name in self._metrics["tool_executions"]:
                self._metrics["tool_executions"][tool_name]["failed"] += 1
        
        elif event.event_type == EventType.TOOL_APPROVAL_REQUIRED:
            tool_name = event.data["tool_name"]
            
            if tool_name in self._metrics["tool_executions"]:
                self._metrics["tool_executions"][tool_name]["requires_approval"] += 1
    
    async def _collect_hitl_metrics(self, event: BaseEvent):
        """Collect metrics from HITL events."""
        
        if event.event_type == EventType.HITL_DECISION_MADE:
            decision = event.data["decision"]
            tool_name = event.data["tool_name"]
            
            if tool_name not in self._metrics["hitl_decisions"]:
                self._metrics["hitl_decisions"][tool_name] = {
                    "APPROVE": 0,
                    "EDIT": 0,
                    "REJECT": 0
                }
            
            self._metrics["hitl_decisions"][tool_name][decision] += 1
            
            logger.debug(f"Recorded HITL decision: {tool_name}, decision={decision}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        return self._metrics.copy()
    
    def get_agent_switch_count(self, from_agent: str, to_agent: str) -> int:
        """Get count of specific agent switch."""
        key = f"{from_agent}_to_{to_agent}"
        return self._metrics["agent_switches"].get(key, 0)
    
    def get_agent_avg_duration(self, agent: str) -> float:
        """Get average processing duration for an agent."""
        if agent not in self._metrics["agent_processing"]:
            return 0.0
        
        metrics = self._metrics["agent_processing"][agent]
        if metrics["count"] == 0:
            return 0.0
        
        return metrics["total_duration_ms"] / metrics["count"]
    
    def get_tool_success_rate(self, tool_name: str) -> float:
        """Get success rate for a tool."""
        if tool_name not in self._metrics["tool_executions"]:
            return 0.0
        
        metrics = self._metrics["tool_executions"][tool_name]
        total = metrics["completed"] + metrics["failed"]
        
        if total == 0:
            return 0.0
        
        return metrics["completed"] / total
    
    def reset_metrics(self):
        """Reset all metrics (for testing)."""
        self._metrics = {
            "agent_switches": {},
            "agent_processing": {},
            "tool_executions": {},
            "hitl_decisions": {},
            "errors": {},
        }
        logger.info("Metrics reset")


# Global singleton instance
metrics_collector = MetricsCollector()

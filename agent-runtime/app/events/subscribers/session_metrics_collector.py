"""
Session Metrics Collector Subscriber.

Collects LLM metrics per session for detailed analytics.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.events.llm_events import (
    LLMRequestStartedEvent,
    LLMRequestCompletedEvent,
    LLMRequestFailedEvent
)

logger = logging.getLogger("agent-runtime.session_metrics")


@dataclass
class LLMRequestMetrics:
    """Metrics for a single LLM request."""
    timestamp: datetime
    model: str
    duration_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    has_tool_calls: bool
    success: bool
    error: Optional[str] = None


@dataclass
class SessionMetrics:
    """Aggregated metrics for a session."""
    session_id: str
    requests: List[LLMRequestMetrics] = field(default_factory=list)
    
    # Aggregated stats
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_ms: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    requests_with_tools: int = 0
    
    def add_request(self, metrics: LLMRequestMetrics):
        """Add request metrics and update aggregates."""
        self.requests.append(metrics)
        self.total_requests += 1
        
        if metrics.success:
            self.successful_requests += 1
            self.total_duration_ms += metrics.duration_ms
            self.total_prompt_tokens += metrics.prompt_tokens
            self.total_completion_tokens += metrics.completion_tokens
            self.total_tokens += metrics.total_tokens
            if metrics.has_tool_calls:
                self.requests_with_tools += 1
        else:
            self.failed_requests += 1
    
    def get_average_duration_ms(self) -> float:
        """Calculate average request duration."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_duration_ms / self.successful_requests
    
    def get_average_tokens_per_request(self) -> float:
        """Calculate average tokens per request."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_tokens / self.successful_requests
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_duration_ms": self.total_duration_ms,
            "average_duration_ms": round(self.get_average_duration_ms(), 2),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "average_tokens_per_request": round(self.get_average_tokens_per_request(), 2),
            "requests_with_tools": self.requests_with_tools,
            "requests": [
                {
                    "timestamp": req.timestamp.isoformat(),
                    "model": req.model,
                    "duration_ms": req.duration_ms,
                    "prompt_tokens": req.prompt_tokens,
                    "completion_tokens": req.completion_tokens,
                    "total_tokens": req.total_tokens,
                    "has_tool_calls": req.has_tool_calls,
                    "success": req.success,
                    "error": req.error
                }
                for req in self.requests
            ]
        }


class SessionMetricsCollector:
    """
    Collects LLM metrics per session.
    
    Subscribes to LLM events and maintains per-session metrics.
    """
    
    def __init__(self):
        self._session_metrics: Dict[str, SessionMetrics] = {}
        self._pending_requests: Dict[str, Dict] = {}  # session_id -> request data
        logger.info("SessionMetricsCollector initialized")
    
    async def start(self):
        """Subscribe to LLM events."""
        await event_bus.subscribe(EventType.LLM_REQUEST_STARTED, self._on_request_started)
        await event_bus.subscribe(EventType.LLM_REQUEST_COMPLETED, self._on_request_completed)
        await event_bus.subscribe(EventType.LLM_REQUEST_FAILED, self._on_request_failed)
        logger.info("SessionMetricsCollector subscribed to LLM events")
    
    async def _on_request_started(self, event: LLMRequestStartedEvent):
        """Handle LLM request started event."""
        logger.debug(f"LLM request started for session {event.session_id}")
        
        # Store pending request data
        self._pending_requests[event.session_id] = {
            "model": event.model,
            "timestamp": event.timestamp
        }
    
    async def _on_request_completed(self, event: LLMRequestCompletedEvent):
        """Handle LLM request completed event."""
        logger.debug(
            f"LLM request completed for session {event.session_id}: "
            f"{event.duration_ms}ms, {event.total_tokens} tokens"
        )
        
        # Get pending request data
        pending = self._pending_requests.pop(event.session_id, {})
        timestamp = pending.get("timestamp", event.timestamp)
        
        # Create request metrics
        metrics = LLMRequestMetrics(
            timestamp=timestamp,
            model=event.model,
            duration_ms=event.duration_ms,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
            total_tokens=event.total_tokens,
            has_tool_calls=event.has_tool_calls,
            success=True
        )
        
        # Get or create session metrics
        if event.session_id not in self._session_metrics:
            self._session_metrics[event.session_id] = SessionMetrics(
                session_id=event.session_id
            )
        
        # Add request metrics
        self._session_metrics[event.session_id].add_request(metrics)
        
        logger.info(
            f"Session {event.session_id} metrics updated: "
            f"{self._session_metrics[event.session_id].total_requests} requests, "
            f"{self._session_metrics[event.session_id].total_tokens} tokens"
        )
    
    async def _on_request_failed(self, event: LLMRequestFailedEvent):
        """Handle LLM request failed event."""
        logger.debug(f"LLM request failed for session {event.session_id}: {event.error}")
        
        # Get pending request data
        pending = self._pending_requests.pop(event.session_id, {})
        timestamp = pending.get("timestamp", event.timestamp)
        
        # Create request metrics
        metrics = LLMRequestMetrics(
            timestamp=timestamp,
            model=event.model,
            duration_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            has_tool_calls=False,
            success=False,
            error=event.error
        )
        
        # Get or create session metrics
        if event.session_id not in self._session_metrics:
            self._session_metrics[event.session_id] = SessionMetrics(
                session_id=event.session_id
            )
        
        # Add request metrics
        self._session_metrics[event.session_id].add_request(metrics)
        
        logger.warning(
            f"Session {event.session_id} failed request recorded: {event.error}"
        )
    
    def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """Get metrics for a specific session."""
        return self._session_metrics.get(session_id)
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all session IDs with metrics."""
        return list(self._session_metrics.keys())
    
    def clear_session_metrics(self, session_id: str):
        """Clear metrics for a specific session."""
        if session_id in self._session_metrics:
            del self._session_metrics[session_id]
            logger.info(f"Cleared metrics for session {session_id}")


# Global instance
session_metrics_collector = SessionMetricsCollector()

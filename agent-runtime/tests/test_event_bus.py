"""
Unit tests for Event Bus and Event-Driven Architecture components.
"""

import pytest
import asyncio
from datetime import datetime

from app.events.event_bus import EventBus, EventBusStats
from app.events.base_event import BaseEvent
from app.events.event_types import EventType, EventCategory
from app.events.agent_events import (
    AgentSwitchedEvent,
    AgentProcessingStartedEvent,
    AgentProcessingCompletedEvent,
    AgentErrorOccurredEvent
)
from app.events.tool_events import (
    ToolExecutionRequestedEvent,
    ToolApprovalRequiredEvent,
    HITLDecisionMadeEvent
)
from app.events.session_events import (
    SessionCreatedEvent,
    MessageAddedEvent
)


class TestEventBus:
    """Tests for EventBus class."""
    
    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus for each test."""
        bus = EventBus()
        yield bus
        # Cleanup
        asyncio.run(bus.clear())
    
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus):
        """Test basic subscribe and publish functionality."""
        received_events = []
        
        async def handler(event: BaseEvent):
            received_events.append(event)
        
        # Subscribe
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=handler
        )
        
        # Publish event
        event = AgentSwitchedEvent(
            session_id="test-session",
            from_agent="orchestrator",
            to_agent="coder",
            reason="Test switch"
        )
        
        await event_bus.publish(event, wait_for_handlers=True)
        
        # Verify
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.AGENT_SWITCHED
        assert received_events[0].session_id == "test-session"
    
    @pytest.mark.asyncio
    async def test_category_subscription(self, event_bus):
        """Test subscription by event category."""
        received_events = []
        
        async def handler(event: BaseEvent):
            received_events.append(event)
        
        # Subscribe to all AGENT events
        event_bus.subscribe(
            event_category=EventCategory.AGENT,
            handler=handler
        )
        
        # Publish different agent events
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        await event_bus.publish(
            AgentProcessingStartedEvent(
                session_id="test",
                agent_type="coder",
                message="test message"
            ),
            wait_for_handlers=True
        )
        
        # Verify both events received
        assert len(received_events) == 2
        assert received_events[0].event_type == EventType.AGENT_SWITCHED
        assert received_events[1].event_type == EventType.AGENT_PROCESSING_STARTED
    
    @pytest.mark.asyncio
    async def test_wildcard_subscription(self, event_bus):
        """Test wildcard subscription (all events)."""
        received_events = []
        
        async def handler(event: BaseEvent):
            received_events.append(event)
        
        # Subscribe to all events
        event_bus.subscribe(handler=handler)
        
        # Publish events from different categories
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        await event_bus.publish(
            SessionCreatedEvent(
                session_id="test",
                system_prompt="test prompt"
            ),
            wait_for_handlers=True
        )
        
        # Verify all events received
        assert len(received_events) == 2
    
    @pytest.mark.asyncio
    async def test_handler_priority(self, event_bus):
        """Test that handlers are executed in priority order."""
        execution_order = []
        
        async def low_priority_handler(event: BaseEvent):
            execution_order.append("low")
        
        async def high_priority_handler(event: BaseEvent):
            execution_order.append("high")
        
        async def medium_priority_handler(event: BaseEvent):
            execution_order.append("medium")
        
        # Subscribe with different priorities
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=low_priority_handler,
            priority=1
        )
        
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=high_priority_handler,
            priority=10
        )
        
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=medium_priority_handler,
            priority=5
        )
        
        # Publish event
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Verify execution order
        assert execution_order == ["high", "medium", "low"]
    
    @pytest.mark.asyncio
    async def test_error_handling_in_handlers(self, event_bus):
        """Test that errors in handlers don't break event bus."""
        received_events = []
        
        async def failing_handler(event: BaseEvent):
            raise ValueError("Test error")
        
        async def working_handler(event: BaseEvent):
            received_events.append(event)
        
        # Subscribe both handlers
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=failing_handler
        )
        
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=working_handler
        )
        
        # Publish event
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Verify working handler still executed
        assert len(received_events) == 1
        
        # Verify stats show failure
        stats = event_bus.get_stats()
        assert stats.failed_handlers == 1
        assert stats.successful_handlers == 1
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus):
        """Test unsubscribing from events."""
        received_events = []
        
        async def handler(event: BaseEvent):
            received_events.append(event)
        
        # Subscribe
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=handler
        )
        
        # Publish first event
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        assert len(received_events) == 1
        
        # Unsubscribe
        event_bus.unsubscribe(
            handler=handler,
            event_type=EventType.AGENT_SWITCHED
        )
        
        # Publish second event
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="coder",
                to_agent="debug",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Verify handler not called
        assert len(received_events) == 1
    
    @pytest.mark.asyncio
    async def test_middleware(self, event_bus):
        """Test middleware functionality."""
        middleware_called = []
        
        async def test_middleware(event: BaseEvent) -> BaseEvent:
            middleware_called.append(event.event_type)
            # Modify event
            event.data["middleware_processed"] = True
            return event
        
        async def cancelling_middleware(event: BaseEvent) -> None:
            # Cancel events with specific session_id
            if event.session_id == "cancel-me":
                return None
            return event
        
        # Add middleware
        event_bus.add_middleware(test_middleware)
        event_bus.add_middleware(cancelling_middleware)
        
        received_events = []
        
        async def handler(event: BaseEvent):
            received_events.append(event)
        
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=handler
        )
        
        # Publish normal event
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Verify middleware processed
        assert len(middleware_called) == 1
        assert len(received_events) == 1
        assert received_events[0].data["middleware_processed"] is True
        
        # Publish cancelled event
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="cancel-me",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Verify event was cancelled
        assert len(received_events) == 1  # Still only 1
    
    @pytest.mark.asyncio
    async def test_decorator_subscription(self, event_bus):
        """Test decorator-style subscription."""
        received_events = []
        
        @event_bus.subscribe(event_type=EventType.AGENT_SWITCHED)
        async def handler(event: BaseEvent):
            received_events.append(event)
        
        # Publish event
        await event_bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Verify
        assert len(received_events) == 1
    
    @pytest.mark.asyncio
    async def test_stats(self, event_bus):
        """Test event bus statistics."""
        async def handler(event: BaseEvent):
            pass
        
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=handler
        )
        
        # Publish events
        for i in range(5):
            await event_bus.publish(
                AgentSwitchedEvent(
                    session_id=f"test-{i}",
                    from_agent="orchestrator",
                    to_agent="coder",
                    reason="test"
                ),
                wait_for_handlers=True
            )
        
        # Check stats
        stats = event_bus.get_stats()
        assert stats.total_published == 5
        assert stats.successful_handlers == 5
        assert stats.failed_handlers == 0
        assert stats.last_event_time is not None


class TestAgentEvents:
    """Tests for agent-specific events."""
    
    def test_agent_switched_event_creation(self):
        """Test AgentSwitchedEvent creation."""
        event = AgentSwitchedEvent(
            session_id="test-session",
            from_agent="orchestrator",
            to_agent="coder",
            reason="Code modification required",
            confidence="high",
            correlation_id="corr-123"
        )
        
        assert event.event_type == EventType.AGENT_SWITCHED
        assert event.event_category == EventCategory.AGENT
        assert event.session_id == "test-session"
        assert event.correlation_id == "corr-123"
        assert event.data["from_agent"] == "orchestrator"
        assert event.data["to_agent"] == "coder"
        assert event.data["reason"] == "Code modification required"
        assert event.data["confidence"] == "high"
        assert event.source == "multi_agent_orchestrator"
    
    def test_agent_processing_started_event(self):
        """Test AgentProcessingStartedEvent creation."""
        event = AgentProcessingStartedEvent(
            session_id="test-session",
            agent_type="coder",
            message="Create a function"
        )
        
        assert event.event_type == EventType.AGENT_PROCESSING_STARTED
        assert event.data["agent"] == "coder"
        assert event.data["message_length"] == len("Create a function")
    
    def test_agent_processing_completed_event(self):
        """Test AgentProcessingCompletedEvent creation."""
        event = AgentProcessingCompletedEvent(
            session_id="test-session",
            agent_type="coder",
            duration_ms=1500.5,
            success=True
        )
        
        assert event.event_type == EventType.AGENT_PROCESSING_COMPLETED
        assert event.data["duration_ms"] == 1500.5
        assert event.data["success"] is True
    
    def test_agent_error_occurred_event(self):
        """Test AgentErrorOccurredEvent creation."""
        event = AgentErrorOccurredEvent(
            session_id="test-session",
            agent_type="coder",
            error_message="File not found",
            error_type="FileNotFoundError"
        )
        
        assert event.event_type == EventType.AGENT_ERROR_OCCURRED
        assert event.data["error_message"] == "File not found"
        assert event.data["error_type"] == "FileNotFoundError"


class TestToolEvents:
    """Tests for tool and HITL events."""
    
    def test_tool_execution_requested_event(self):
        """Test ToolExecutionRequestedEvent creation."""
        event = ToolExecutionRequestedEvent(
            session_id="test-session",
            tool_name="write_file",
            arguments={"path": "test.py", "content": "print('hello')"},
            call_id="call-123",
            agent="coder"
        )
        
        assert event.event_type == EventType.TOOL_EXECUTION_REQUESTED
        assert event.event_category == EventCategory.TOOL
        assert event.data["tool_name"] == "write_file"
        assert event.data["call_id"] == "call-123"
    
    def test_tool_approval_required_event(self):
        """Test ToolApprovalRequiredEvent creation."""
        event = ToolApprovalRequiredEvent(
            session_id="test-session",
            tool_name="execute_command",
            arguments={"command": "rm -rf /tmp"},
            call_id="call-123",
            reason="Dangerous command"
        )
        
        assert event.event_type == EventType.TOOL_APPROVAL_REQUIRED
        assert event.event_category == EventCategory.HITL
        assert event.data["reason"] == "Dangerous command"
    
    def test_hitl_decision_made_event(self):
        """Test HITLDecisionMadeEvent creation."""
        event = HITLDecisionMadeEvent(
            session_id="test-session",
            call_id="call-123",
            decision="APPROVE",
            tool_name="write_file",
            original_args={"path": "test.py"},
            modified_args=None
        )
        
        assert event.event_type == EventType.HITL_DECISION_MADE
        assert event.data["decision"] == "APPROVE"
        assert event.data["tool_name"] == "write_file"


class TestSessionEvents:
    """Tests for session events."""
    
    def test_session_created_event(self):
        """Test SessionCreatedEvent creation."""
        event = SessionCreatedEvent(
            session_id="test-session",
            system_prompt="You are a helpful assistant"
        )
        
        assert event.event_type == EventType.SESSION_CREATED
        assert event.event_category == EventCategory.SESSION
        assert event.data["system_prompt_length"] == len("You are a helpful assistant")
    
    def test_message_added_event(self):
        """Test MessageAddedEvent creation."""
        event = MessageAddedEvent(
            session_id="test-session",
            role="user",
            content_length=100,
            agent_name="coder"
        )
        
        assert event.event_type == EventType.MESSAGE_ADDED
        assert event.data["role"] == "user"
        assert event.data["content_length"] == 100
        assert event.data["agent_name"] == "coder"


class TestMetricsCollector:
    """Tests for MetricsCollector subscriber."""
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Test that metrics are collected from events."""
        from app.events.subscribers.metrics_collector import MetricsCollector
        from app.events.event_bus import EventBus
        
        # Create fresh instances
        bus = EventBus()
        collector = MetricsCollector()
        collector._metrics = {
            "agent_switches": {},
            "agent_processing": {},
            "tool_executions": {},
            "hitl_decisions": {},
            "errors": {},
        }
        
        # Subscribe collector to bus
        bus.subscribe(
            event_category=EventCategory.AGENT,
            handler=collector._collect_agent_metrics
        )
        
        # Publish agent switch event
        await bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Verify metrics
        metrics = collector.get_metrics()
        assert "orchestrator_to_coder" in metrics["agent_switches"]
        assert metrics["agent_switches"]["orchestrator_to_coder"] == 1
    
    @pytest.mark.asyncio
    async def test_agent_processing_metrics(self):
        """Test agent processing duration metrics."""
        from app.events.subscribers.metrics_collector import MetricsCollector
        from app.events.event_bus import EventBus
        
        bus = EventBus()
        collector = MetricsCollector()
        collector._metrics = {
            "agent_switches": {},
            "agent_processing": {},
            "tool_executions": {},
            "hitl_decisions": {},
            "errors": {},
        }
        
        bus.subscribe(
            event_category=EventCategory.AGENT,
            handler=collector._collect_agent_metrics
        )
        
        # Publish processing completed event
        await bus.publish(
            AgentProcessingCompletedEvent(
                session_id="test",
                agent_type="coder",
                duration_ms=1500.0,
                success=True
            ),
            wait_for_handlers=True
        )
        
        # Verify metrics
        avg_duration = collector.get_agent_avg_duration("coder")
        assert avg_duration == 1500.0


class TestAuditLogger:
    """Tests for AuditLogger subscriber."""
    
    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test that critical events are logged."""
        from app.events.subscribers.audit_logger import AuditLogger
        from app.events.event_bus import EventBus
        
        bus = EventBus()
        audit = AuditLogger()
        audit._audit_log = []
        
        # Subscribe audit logger
        bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=audit._log_agent_switch
        )
        
        # Publish event
        await bus.publish(
            AgentSwitchedEvent(
                session_id="test-session",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test reason"
            ),
            wait_for_handlers=True
        )
        
        # Verify audit log
        log = audit.get_audit_log()
        assert len(log) == 1
        assert log[0]["event_type"] == "agent_switched"
        assert log[0]["session_id"] == "test-session"
        assert log[0]["from_agent"] == "orchestrator"
        assert log[0]["to_agent"] == "coder"
    
    @pytest.mark.asyncio
    async def test_audit_log_filtering(self):
        """Test audit log filtering."""
        from app.events.subscribers.audit_logger import AuditLogger
        from app.events.event_bus import EventBus
        
        bus = EventBus()
        audit = AuditLogger()
        audit._audit_log = []
        
        bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=audit._log_agent_switch
        )
        
        # Publish events for different sessions
        await bus.publish(
            AgentSwitchedEvent(
                session_id="session-1",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        await bus.publish(
            AgentSwitchedEvent(
                session_id="session-2",
                from_agent="orchestrator",
                to_agent="debug",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        # Filter by session
        session1_log = audit.get_audit_log(session_id="session-1")
        assert len(session1_log) == 1
        assert session1_log[0]["session_id"] == "session-1"
        
        # Filter by event type
        switch_log = audit.get_audit_log(event_type="agent_switched")
        assert len(switch_log) == 2


class TestBaseEvent:
    """Tests for BaseEvent model."""
    
    def test_base_event_creation(self):
        """Test BaseEvent creation with all fields."""
        event = BaseEvent(
            event_type=EventType.AGENT_SWITCHED,
            event_category=EventCategory.AGENT,
            session_id="test-session",
            correlation_id="corr-123",
            causation_id="cause-456",
            data={"key": "value"},
            source="test_component"
        )
        
        assert event.event_id is not None
        assert event.event_type == EventType.AGENT_SWITCHED
        assert event.event_category == EventCategory.AGENT
        assert event.session_id == "test-session"
        assert event.correlation_id == "corr-123"
        assert event.causation_id == "cause-456"
        assert event.data == {"key": "value"}
        assert event.source == "test_component"
        assert event.version == "1.0"
        assert isinstance(event.timestamp, datetime)
    
    def test_base_event_serialization(self):
        """Test BaseEvent JSON serialization."""
        event = BaseEvent(
            event_type=EventType.AGENT_SWITCHED,
            event_category=EventCategory.AGENT,
            data={"test": "data"},
            source="test"
        )
        
        # Serialize to dict
        event_dict = event.dict()
        assert "event_id" in event_dict
        assert "timestamp" in event_dict
        assert isinstance(event_dict["timestamp"], str)  # ISO format
        
        # Serialize to JSON
        event_json = event.json()
        assert isinstance(event_json, str)
        assert "event_id" in event_json

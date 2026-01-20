"""
Integration tests for Event-Driven Architecture Phase 2.

Tests that events are properly published from services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.events.event_bus import EventBus
from app.events.event_types import EventType, EventCategory
from app.events.agent_events import AgentSwitchedEvent
from app.events.session_events import SessionCreatedEvent, MessageAddedEvent
from app.events.tool_events import HITLApprovalRequestedEvent, HITLDecisionMadeEvent
from app.models.hitl_models import HITLDecision


class TestMultiAgentOrchestratorEvents:
    """Test event publishing from MultiAgentOrchestrator."""
    
    @pytest.mark.asyncio
    async def test_agent_switch_event_structure(self):
        """Test AgentSwitchedEvent structure and publishing."""
        bus = EventBus()
        received_events = []
        
        @bus.subscribe(event_type=EventType.AGENT_SWITCHED)
        async def collector(event):
            received_events.append(event)
        
        # Publish event directly (simulating what orchestrator does)
        await bus.publish(
            AgentSwitchedEvent(
                session_id="test-session",
                from_agent="orchestrator",
                to_agent="coder",
                reason="Code modification required",
                confidence="high"
            ),
            wait_for_handlers=True
        )
        
        # Verify event was published and received
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.AGENT_SWITCHED
        assert received_events[0].data["from_agent"] == "orchestrator"
        assert received_events[0].data["to_agent"] == "coder"


class TestSessionManagerEvents:
    """Test event publishing from SessionManager."""
    
    @pytest.mark.asyncio
    async def test_session_created_publishes_event(self):
        """Test that session creation publishes SessionCreatedEvent."""
        # Skip test - AsyncSessionManager module doesn't exist in new architecture
        pytest.skip("AsyncSessionManager не существует в новой архитектуре")
    
    @pytest.mark.asyncio
    async def test_message_added_publishes_event(self):
        """Test that appending message publishes MessageAddedEvent."""
        # Skip test - AsyncSessionManager module doesn't exist in new architecture
        pytest.skip("AsyncSessionManager не существует в новой архитектуре")


class TestHITLManagerEvents:
    """Test event publishing from HITLManager."""
    
    @pytest.mark.asyncio
    async def test_add_pending_publishes_event(self):
        """Test that adding pending approval publishes HITLApprovalRequestedEvent."""
        from app.services.hitl_manager import HITLManager
        
        # Create event bus and collector
        bus = EventBus()
        received_events = []
        
        @bus.subscribe(event_type=EventType.HITL_APPROVAL_REQUESTED)
        async def collector(event):
            received_events.append(event)
        
        # Mock the event_bus in the module
        with patch('app.services.hitl_manager.event_bus', bus):
            # Create manager
            manager = HITLManager()
            manager._save_pending_async = AsyncMock()
            
            # Add pending approval
            await manager.add_pending(
                session_id="test-session",
                call_id="call-123",
                tool_name="write_file",
                arguments={"path": "test.py"},
                reason="File modification"
            )
            
            # Wait for event handlers
            import asyncio
            await asyncio.sleep(0.1)
            
            # Verify event was published
            assert len(received_events) == 1
            assert received_events[0].event_type == EventType.HITL_APPROVAL_REQUESTED
            assert received_events[0].data["call_id"] == "call-123"
            assert received_events[0].data["tool_name"] == "write_file"
    
    @pytest.mark.asyncio
    async def test_log_decision_publishes_event(self):
        """Test that logging decision publishes HITLDecisionMadeEvent."""
        from app.services.hitl_manager import HITLManager
        
        # Create event bus and collector
        bus = EventBus()
        received_events = []
        
        @bus.subscribe(event_type=EventType.HITL_DECISION_MADE)
        async def collector(event):
            received_events.append(event)
        
        # Mock the event_bus in the module
        with patch('app.services.hitl_manager.event_bus', bus):
            # Create manager
            manager = HITLManager()
            
            # Log decision
            await manager.log_decision(
                session_id="test-session",
                call_id="call-123",
                tool_name="write_file",
                original_arguments={"path": "test.py"},
                decision=HITLDecision.APPROVE,
                modified_arguments=None
            )
            
            # Wait for event handlers
            import asyncio
            await asyncio.sleep(0.1)
            
            # Verify event was published
            assert len(received_events) == 1
            assert received_events[0].event_type == EventType.HITL_DECISION_MADE
            assert received_events[0].data["decision"] == "approve"  # Lowercase from enum value
            assert received_events[0].data["tool_name"] == "write_file"


class TestEndToEndEventFlow:
    """Test end-to-end event flow through the system."""
    
    @pytest.mark.asyncio
    async def test_complete_event_flow(self):
        """Test that a complete workflow publishes all expected events."""
        from app.events.event_bus import EventBus
        from app.events.subscribers.metrics_collector import MetricsCollector
        from app.events.subscribers.audit_logger import AuditLogger
        
        # Create fresh instances
        bus = EventBus()
        collector = MetricsCollector()
        auditor = AuditLogger()
        
        # Reset their state
        collector._metrics = {
            "agent_switches": {},
            "agent_processing": {},
            "tool_executions": {},
            "hitl_decisions": {},
            "errors": {},
        }
        auditor._audit_log = []
        
        # Subscribe to bus
        bus.subscribe(
            event_category=EventCategory.AGENT,
            handler=collector._collect_agent_metrics
        )
        bus.subscribe(
            event_category=EventCategory.TOOL,
            handler=collector._collect_tool_metrics
        )
        bus.subscribe(
            event_category=EventCategory.HITL,
            handler=collector._collect_hitl_metrics
        )
        
        bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=auditor._log_agent_switch
        )
        bus.subscribe(
            event_type=EventType.HITL_DECISION_MADE,
            handler=auditor._log_hitl_decision
        )
        
        # Simulate workflow
        from app.events.agent_events import AgentSwitchedEvent, AgentProcessingCompletedEvent
        from app.events.tool_events import (
            ToolExecutionRequestedEvent,
            ToolApprovalRequiredEvent,
            HITLDecisionMadeEvent
        )
        
        # 1. Agent switch
        await bus.publish(
            AgentSwitchedEvent(
                session_id="test-session",
                from_agent="orchestrator",
                to_agent="coder",
                reason="Code modification required"
            ),
            wait_for_handlers=True
        )
        
        # 2. Tool execution requested
        await bus.publish(
            ToolExecutionRequestedEvent(
                session_id="test-session",
                tool_name="write_file",
                arguments={"path": "test.py"},
                call_id="call-123",
                agent="coder"
            ),
            wait_for_handlers=True
        )
        
        # 3. Tool approval required
        await bus.publish(
            ToolApprovalRequiredEvent(
                session_id="test-session",
                tool_name="write_file",
                arguments={"path": "test.py"},
                call_id="call-123",
                reason="File modification"
            ),
            wait_for_handlers=True
        )
        
        # 4. HITL decision made
        await bus.publish(
            HITLDecisionMadeEvent(
                session_id="test-session",
                call_id="call-123",
                decision="APPROVE",
                tool_name="write_file",
                original_args={"path": "test.py"},
                modified_args=None
            ),
            wait_for_handlers=True
        )
        
        # 5. Agent processing completed
        await bus.publish(
            AgentProcessingCompletedEvent(
                session_id="test-session",
                agent_type="coder",
                duration_ms=1500.0,
                success=True
            ),
            wait_for_handlers=True
        )
        
        # Verify metrics collected
        metrics = collector.get_metrics()
        assert metrics["agent_switches"]["orchestrator_to_coder"] == 1
        assert metrics["tool_executions"]["write_file"]["requested"] == 1
        # Note: ToolApprovalRequiredEvent is HITL category, not TOOL
        assert metrics["hitl_decisions"]["write_file"]["APPROVE"] == 1
        assert metrics["agent_processing"]["coder"]["count"] == 1
        assert metrics["agent_processing"]["coder"]["success_count"] == 1
        
        # Verify audit log
        audit_log = auditor.get_audit_log()
        assert len(audit_log) >= 2  # At least agent_switched and hitl_decision
        
        switch_logs = [log for log in audit_log if log["event_type"] == "agent_switched"]
        assert len(switch_logs) == 1
        assert switch_logs[0]["from_agent"] == "orchestrator"
        assert switch_logs[0]["to_agent"] == "coder"
        
        decision_logs = [log for log in audit_log if log["event_type"] == "hitl_decision_made"]
        assert len(decision_logs) == 1
        assert decision_logs[0]["decision"] == "APPROVE"


class TestEventBusStats:
    """Test event bus statistics tracking."""
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test that event bus tracks statistics correctly."""
        from app.events.event_bus import EventBus
        from app.events.agent_events import AgentSwitchedEvent
        
        bus = EventBus()
        
        # Subscribe handler
        @bus.subscribe(event_type=EventType.AGENT_SWITCHED)
        async def handler(event):
            pass
        
        # Publish multiple events
        for i in range(5):
            await bus.publish(
                AgentSwitchedEvent(
                    session_id=f"session-{i}",
                    from_agent="orchestrator",
                    to_agent="coder",
                    reason="test"
                ),
                wait_for_handlers=True
            )
        
        # Check stats
        stats = bus.get_stats()
        assert stats.total_published == 5
        assert stats.successful_handlers == 5
        assert stats.failed_handlers == 0
        assert stats.last_event_time is not None


class TestCorrelationIDTracking:
    """Test correlation ID tracking across events."""
    
    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self):
        """Test that correlation_id is properly propagated."""
        from app.events.event_bus import EventBus
        from app.events.agent_events import AgentSwitchedEvent, AgentProcessingStartedEvent
        
        bus = EventBus()
        received_events = []
        
        @bus.subscribe()  # Wildcard
        async def collector(event):
            received_events.append(event)
        
        correlation_id = "test-correlation-123"
        
        # Publish related events with same correlation_id
        await bus.publish(
            AgentProcessingStartedEvent(
                session_id="test-session",
                agent_type="coder",
                message="test",
                correlation_id=correlation_id
            ),
            wait_for_handlers=True
        )
        
        await bus.publish(
            AgentSwitchedEvent(
                session_id="test-session",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test",
                correlation_id=correlation_id
            ),
            wait_for_handlers=True
        )
        
        # Verify all events have same correlation_id
        assert len(received_events) == 2
        assert all(e.correlation_id == correlation_id for e in received_events)


class TestMetricsCollectorIntegration:
    """Test MetricsCollector integration with real events."""
    
    @pytest.mark.asyncio
    async def test_metrics_from_multiple_events(self):
        """Test metrics collection from multiple event types."""
        from app.events.event_bus import EventBus
        from app.events.subscribers.metrics_collector import MetricsCollector
        from app.events.agent_events import (
            AgentSwitchedEvent,
            AgentProcessingCompletedEvent,
            AgentErrorOccurredEvent
        )
        
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
        
        # Publish various events
        await bus.publish(
            AgentSwitchedEvent(
                session_id="test",
                from_agent="orchestrator",
                to_agent="coder",
                reason="test"
            ),
            wait_for_handlers=True
        )
        
        await bus.publish(
            AgentProcessingCompletedEvent(
                session_id="test",
                agent_type="coder",
                duration_ms=1000.0,
                success=True
            ),
            wait_for_handlers=True
        )
        
        await bus.publish(
            AgentProcessingCompletedEvent(
                session_id="test",
                agent_type="coder",
                duration_ms=2000.0,
                success=False
            ),
            wait_for_handlers=True
        )
        
        await bus.publish(
            AgentErrorOccurredEvent(
                session_id="test",
                agent_type="coder",
                error_message="Test error",
                error_type="ValueError"
            ),
            wait_for_handlers=True
        )
        
        # Verify metrics
        metrics = collector.get_metrics()
        
        # Agent switches
        assert metrics["agent_switches"]["orchestrator_to_coder"] == 1
        
        # Agent processing
        assert metrics["agent_processing"]["coder"]["count"] == 2
        assert metrics["agent_processing"]["coder"]["success_count"] == 1
        assert metrics["agent_processing"]["coder"]["failure_count"] == 1
        assert metrics["agent_processing"]["coder"]["total_duration_ms"] == 3000.0
        
        # Average duration
        avg = collector.get_agent_avg_duration("coder")
        assert avg == 1500.0  # (1000 + 2000) / 2
        
        # Errors
        assert metrics["errors"]["coder"]["ValueError"] == 1


class TestAuditLoggerIntegration:
    """Test AuditLogger integration with real events."""
    
    @pytest.mark.asyncio
    async def test_audit_logging_from_events(self):
        """Test audit logging from various events."""
        from app.events.event_bus import EventBus
        from app.events.subscribers.audit_logger import AuditLogger
        from app.events.agent_events import AgentSwitchedEvent, AgentErrorOccurredEvent
        from app.events.tool_events import HITLDecisionMadeEvent
        
        bus = EventBus()
        auditor = AuditLogger()
        auditor._audit_log = []
        
        bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=auditor._log_agent_switch
        )
        bus.subscribe(
            event_type=EventType.HITL_DECISION_MADE,
            handler=auditor._log_hitl_decision
        )
        bus.subscribe(
            event_type=EventType.AGENT_ERROR_OCCURRED,
            handler=auditor._log_error
        )
        
        # Publish events
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
            HITLDecisionMadeEvent(
                session_id="session-1",
                call_id="call-123",
                decision="APPROVE",
                tool_name="write_file",
                original_args={"path": "test.py"},
                modified_args=None
            ),
            wait_for_handlers=True
        )
        
        await bus.publish(
            AgentErrorOccurredEvent(
                session_id="session-2",
                agent_type="coder",
                error_message="Test error",
                error_type="ValueError"
            ),
            wait_for_handlers=True
        )
        
        # Verify audit log
        log = auditor.get_audit_log()
        assert len(log) == 3
        
        # Filter by session
        session1_log = auditor.get_audit_log(session_id="session-1")
        assert len(session1_log) == 2
        
        # Filter by event type
        switch_log = auditor.get_audit_log(event_type="agent_switched")
        assert len(switch_log) == 1
        
        error_log = auditor.get_audit_log(event_type="agent_error")
        assert len(error_log) == 1

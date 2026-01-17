"""
Agent Context subscriber that updates agent context based on events.

Phase 4: Fully event-driven - always enabled.
"""

import logging

from ..event_bus import event_bus
from ..base_event import BaseEvent
from ..event_types import EventType

logger = logging.getLogger(__name__)


class AgentContextSubscriber:
    """
    Subscribes to agent events and updates agent context accordingly.
    
    Event-driven context management (Phase 4 - always enabled):
    - Listens to AgentSwitchedEvent
    - Updates AgentContext automatically
    - No feature flag - always active
    """
    
    def __init__(self):
        """Initialize agent context subscriber."""
        self._setup_subscriptions()
        logger.info("AgentContextSubscriber initialized (event-driven mode)")
    
    def _setup_subscriptions(self):
        """Subscribe to agent events."""
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=self._on_agent_switched,
            priority=15  # High priority - context should be updated first
        )
    
    async def _on_agent_switched(self, event: BaseEvent):
        """
        Handle agent switched event.
        
        Updates the agent context when an agent switch occurs.
        """
        
        session_id = event.session_id
        if not session_id:
            logger.warning("AgentSwitchedEvent without session_id, skipping context update")
            return
        
        from_agent = event.data.get("from_agent")
        to_agent = event.data.get("to_agent")
        reason = event.data.get("reason", "")
        
        logger.debug(
            f"Event-driven context update: {from_agent} -> {to_agent} "
            f"for session {session_id}"
        )
        
        # Get agent context manager
        from app.services.agent_context_async import agent_context_manager
        
        if not agent_context_manager:
            logger.error("AgentContextManager not initialized")
            return
        
        # Get context
        context = agent_context_manager.get(session_id)
        if not context:
            logger.warning(f"Context not found for session {session_id}")
            return
        
        # Update context through event
        # Note: This is event-driven update, so we DON'T call context.switch_agent()
        # directly to avoid duplicate event publishing
        from app.agents.base_agent import AgentType
        
        try:
            new_agent = AgentType(to_agent)
            
            # Manually update context fields (bypassing switch_agent to avoid event loop)
            context.agent_history.append({
                "from_agent": from_agent,
                "to_agent": to_agent,
                "reason": reason,
                "timestamp": event.timestamp.isoformat()
            })
            
            context.current_agent = new_agent
            context.last_switch_at = event.timestamp
            context.switch_count += 1
            context._needs_persist = True
            
            logger.info(
                f"Context updated via event: session={session_id}, "
                f"agent={to_agent}, switch_count={context.switch_count}"
            )
            
        except ValueError as e:
            logger.error(f"Invalid agent type in event: {to_agent}, error: {e}")
    
# Global singleton instance
agent_context_subscriber = AgentContextSubscriber()

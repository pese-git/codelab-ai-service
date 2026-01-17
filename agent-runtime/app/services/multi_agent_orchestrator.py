"""
Multi-Agent Orchestrator - coordinates work between specialized agents.

Manages agent switching, context preservation, and message routing.
"""
import logging
import time
import uuid
from typing import AsyncGenerator, Optional
from app.agents.base_agent import AgentType
from app.models.schemas import StreamChunk
from app.services.agent_router import agent_router
from app.services.agent_context_async import agent_context_manager
from app.services.session_manager_async import session_manager

# Event-Driven Architecture imports
from app.events.event_bus import event_bus
from app.events.agent_events import (
    AgentSwitchedEvent,
    AgentProcessingStartedEvent,
    AgentProcessingCompletedEvent,
    AgentErrorOccurredEvent
)

logger = logging.getLogger("agent-runtime.multi_agent_orchestrator")


class MultiAgentOrchestrator:
    """
    Orchestrates the multi-agent system.
    
    Responsibilities:
    - Route messages to appropriate agents
    - Handle agent switching
    - Preserve context across switches
    - Manage agent lifecycle
    """
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through the multi-agent system.
        
        Args:
            session_id: Session identifier
            message: User message to process
            agent_type: Explicitly requested agent type (optional)
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        # Generate correlation ID for tracing
        correlation_id = str(uuid.uuid4())
        
        logger.info(f"MultiAgentOrchestrator processing message for session {session_id}")
        
        # Get or create agent context (async)
        # Import here to avoid circular dependency and get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        
        if async_ctx_mgr is None:
            raise RuntimeError("AgentContextManager not initialized")
        
        context = await async_ctx_mgr.get_or_create(session_id)
        
        # Track processing start time
        start_time = time.time()
        processing_success = True
        current_agent_for_tracking = context.current_agent
        
        # Handle explicit agent switch request
        if agent_type:
            if context.current_agent != agent_type:
                from_agent = context.current_agent
                
                context.switch_agent(agent_type, "User requested agent switch")
                logger.info(
                    f"Explicit agent switch for session {session_id}: "
                    f"{from_agent.value} -> {agent_type.value}"
                )
                
                # Publish agent switched event
                await event_bus.publish(
                    AgentSwitchedEvent(
                        session_id=session_id,
                        from_agent=from_agent.value,
                        to_agent=agent_type.value,
                        reason="User requested agent switch",
                        correlation_id=correlation_id
                    )
                )
                
                # Notify about the switch
                yield StreamChunk(
                    type="agent_switched",
                    content=f"Switched to {agent_type.value} agent",
                    metadata={
                        "from_agent": from_agent.value,
                        "to_agent": agent_type.value,
                        "reason": "User requested"
                    },
                    is_final=False
                )
        
        # Get session manager for passing to agents
        from app.services.session_manager_async import session_manager as async_session_mgr
        
        if async_session_mgr is None:
            raise RuntimeError("SessionManager not initialized")
        
        # Publish processing started event
        await event_bus.publish(
            AgentProcessingStartedEvent(
                session_id=session_id,
                agent_type=context.current_agent.value,
                message=message,
                correlation_id=correlation_id
            )
        )
        
        # If current agent is Orchestrator and we have a message, let it route
        if context.current_agent == AgentType.ORCHESTRATOR and message:
            logger.debug("Current agent is Orchestrator, will route to specialist")
            orchestrator = agent_router.get_agent(AgentType.ORCHESTRATOR)
            
            # Orchestrator will analyze and return switch_agent chunk
            async for chunk in orchestrator.process(
                session_id=session_id,
                message=message,
                context=context.model_dump(),
                session_mgr=async_session_mgr
            ):
                if chunk.type == "switch_agent":
                    # Extract target agent from metadata
                    target_agent_str = chunk.metadata.get("target_agent")
                    target_agent = AgentType(target_agent_str)
                    reason = chunk.metadata.get("reason", "Orchestrator routing")
                    confidence = chunk.metadata.get("confidence", "medium")
                    
                    # Switch to target agent
                    context.switch_agent(target_agent, reason)
                    
                    logger.info(
                        f"Orchestrator routed to {target_agent.value} "
                        f"for session {session_id}"
                    )
                    
                    # Publish agent switched event
                    await event_bus.publish(
                        AgentSwitchedEvent(
                            session_id=session_id,
                            from_agent=AgentType.ORCHESTRATOR.value,
                            to_agent=target_agent.value,
                            reason=reason,
                            confidence=confidence,
                            correlation_id=correlation_id
                        )
                    )
                    
                    # Notify about the switch
                    yield StreamChunk(
                        type="agent_switched",
                        content=f"Switched to {target_agent.value} agent",
                        metadata={
                            "from_agent": AgentType.ORCHESTRATOR.value,
                            "to_agent": target_agent.value,
                            "reason": reason,
                            "confidence": confidence
                        },
                        is_final=False
                    )
                    break
                else:
                    # Forward other chunks (shouldn't happen with Orchestrator)
                    yield chunk
        
        # Get current agent and process message
        current_agent = agent_router.get_agent(context.current_agent)
        
        logger.info(
            f"Processing with {context.current_agent.value} agent "
            f"for session {session_id}"
        )
        
        try:
            # Process message through current agent
            async for chunk in current_agent.process(
                session_id=session_id,
                message=message,
                context=context.model_dump(),
                session_mgr=async_session_mgr
            ):
                # Check for agent switch requests from the agent itself
                if chunk.type == "switch_agent":
                    target_agent_str = chunk.metadata.get("target_agent")
                    target_agent = AgentType(target_agent_str)
                    reason = chunk.metadata.get("reason", "Agent requested switch")
                    from_agent = context.current_agent
                    
                    # Switch to new agent
                    context.switch_agent(target_agent, reason)
                    
                    logger.info(
                        f"Agent switch requested: {from_agent.value} -> {target_agent.value}"
                    )
                    
                    # Publish agent switched event
                    await event_bus.publish(
                        AgentSwitchedEvent(
                            session_id=session_id,
                            from_agent=from_agent.value,
                            to_agent=target_agent.value,
                            reason=reason,
                            correlation_id=correlation_id
                        )
                    )
                    
                    # Notify about the switch
                    yield StreamChunk(
                        type="agent_switched",
                        content=f"Switched to {target_agent.value} agent",
                        metadata={
                            "from_agent": from_agent.value,
                            "to_agent": target_agent.value,
                            "reason": reason
                        },
                        is_final=False
                    )
                    
                    # Continue processing with new agent
                    new_agent = agent_router.get_agent(target_agent)
                    async for new_chunk in new_agent.process(
                        session_id=session_id,
                        message=message,
                        context=context.model_dump(),
                        session_mgr=async_session_mgr
                    ):
                        yield new_chunk
                    
                    return
                
                # Forward chunk
                yield chunk
        
        except Exception as e:
            processing_success = False
            
            # Publish error event
            await event_bus.publish(
                AgentErrorOccurredEvent(
                    session_id=session_id,
                    agent_type=current_agent_for_tracking.value,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    correlation_id=correlation_id
                )
            )
            
            logger.error(f"Error in agent processing: {e}", exc_info=True)
            raise
        
        finally:
            # Publish processing completed event
            duration_ms = (time.time() - start_time) * 1000
            await event_bus.publish(
                AgentProcessingCompletedEvent(
                    session_id=session_id,
                    agent_type=current_agent_for_tracking.value,
                    duration_ms=duration_ms,
                    success=processing_success,
                    correlation_id=correlation_id
                )
            )
    
    def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Get current active agent for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Current agent type or None if session doesn't exist
        """
        # Import here to get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        context = async_ctx_mgr.get(session_id) if async_ctx_mgr else None
        return context.current_agent if context else None
    
    def get_agent_history(self, session_id: str) -> list:
        """
        Get agent switch history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of agent switch records
        """
        # Import here to get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        context = async_ctx_mgr.get(session_id) if async_ctx_mgr else None
        return context.get_agent_history() if context else []
    
    def reset_session(self, session_id: str) -> None:
        """
        Reset session to initial state (Orchestrator).
        
        Args:
            session_id: Session identifier
        """
        # Import here to get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        context = async_ctx_mgr.get(session_id) if async_ctx_mgr else None
        if context:
            context.switch_agent(AgentType.ORCHESTRATOR, "Session reset")
            logger.info(f"Reset session {session_id} to Orchestrator agent")


# Singleton instance
multi_agent_orchestrator = MultiAgentOrchestrator()
